"""Inventory changes; lock order: production, material, unit."""

import re
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.productions.models import Production

from .models import (
    DefectReport,
    Material,
    MaterialUnit,
    PlannedMaterial,
    ProductionTeardown,
    TeardownException,
    UnitIssue,
    UnitReservation,
)


def normalize_code(raw):
    code = raw.strip()
    if "/" in code:
        match = re.fullmatch(r"/geraet/([^/]+)/?", urlsplit(code).path)
        code = unquote(match[1]) if match else ""
    code = code.upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,99}", code):
        raise ValidationError("Ungültiger Inventarcode.")
    return code


def lock_production(production):
    return Production.objects.select_for_update().get(
        pk=production.pk, organization=production.organization
    )


def lock_unit(unit):
    Material.objects.select_for_update().get(pk=unit.material_id)
    return MaterialUnit.objects.select_for_update().select_related("material").get(pk=unit.pk)


def check_open(production):
    if ProductionTeardown.objects.filter(
        production=production, completed_at__isnull=False
    ).exists():
        raise ValidationError(
            "Der Abbau ist abgeschlossen; neue Ausgaben und Reservierungen sind gesperrt."
        )


def check_available(unit):
    if unit.archived_at or unit.material.is_archived:
        raise ValidationError("Gerät oder Material ist archiviert.")
    if unit.defects.filter(status__in=DefectReport.OPEN).exists():
        raise ValidationError("Dieses Gerät ist defekt oder in Reparatur.")
    if unit.material.defects.filter(unit__isnull=True, status__in=DefectReport.OPEN).exists():
        raise ValidationError("Für diese Materialart liegt eine offene Defektmeldung vor.")
    if unit.issues.filter(returned_at__isnull=True).exists():
        raise ValidationError("Dieses Gerät ist noch ausgegeben oder vermisst.")


def reservations(unit):
    # Use current production dates, so moving an event cannot silently leave stale dates.
    return unit.reservations.filter(released_at__isnull=True, production__deleted_at__isnull=True)


@transaction.atomic
def reserve(production, unit, user):
    production = lock_production(production)
    unit = lock_unit(unit)
    if production.organization_id != unit.organization_id:
        raise ValidationError("Gerät gehört nicht zu dieser AG.")
    check_open(production)
    check_available(unit)
    if production.end_date < production.start_date:
        raise ValidationError("Ungültiger Produktionszeitraum.")
    if (
        reservations(unit)
        .filter(
            production__start_date__lte=production.end_date,
            production__end_date__gte=production.start_date,
        )
        .exists()
    ):
        raise ValidationError("Das Gerät ist im Produktionszeitraum bereits reserviert.")
    plan = PlannedMaterial.objects.filter(production=production, material=unit.material).first()
    count = UnitReservation.objects.filter(
        production=production, unit__material=unit.material, released_at__isnull=True
    ).count()
    if not plan or count >= plan.quantity:
        raise ValidationError("Zuerst eine ausreichende Menge dieser Materialart einplanen.")
    return UnitReservation.objects.create(
        organization=production.organization, production=production, unit=unit, created_by=user
    )


@transaction.atomic
def cancel(reservation):
    lock_production(reservation.production)
    lock_unit(reservation.unit)
    if UnitIssue.objects.filter(
        production=reservation.production, unit=reservation.unit, returned_at__isnull=True
    ).exists():
        raise ValidationError("Gerät vor dem Aufheben der Reservierung zurückgeben.")
    UnitReservation.objects.filter(pk=reservation.pk, released_at__isnull=True).update(
        released_at=timezone.now()
    )


@transaction.atomic
def scan_unit(production, raw, mode, user):
    production = lock_production(production)
    unit = (
        MaterialUnit.objects.for_org(production.organization)
        .filter(code__iexact=normalize_code(raw))
        .first()
    )
    if unit is None:
        raise ValidationError("Unbekannter Inventarcode.")
    unit = lock_unit(unit)
    current = unit.issues.filter(returned_at__isnull=True).first()
    if mode == "return":
        if not current or current.production_id != production.pk:
            raise ValidationError("Dieses Gerät ist hier nicht ausgegeben.")
        current.returned_at, current.returned_by = timezone.now(), user
        current.save(update_fields=["returned_at", "returned_by"])
        return "Rückgabe gespeichert."
    if mode != "issue":
        raise ValidationError("Ungültiger Scanmodus.")
    check_open(production)
    check_available(unit)
    today = timezone.localdate()
    own = reservations(unit).filter(production=production, production__end_date__gte=today).first()
    if not own:
        raise ValidationError("Keine aktive Reservierung für dieses Gerät.")
    # Early issue must not block another production before our reservation starts.
    if (
        reservations(unit)
        .exclude(production=production)
        .filter(
            production__start_date__lte=production.end_date,
            production__end_date__gte=min(today, production.start_date),
        )
        .exists()
    ):
        raise ValidationError(
            "Das Gerät wird vorher oder im selben Zeitraum für eine andere Produktion benötigt."
        )
    plan = PlannedMaterial.objects.filter(production=production, material=unit.material).first()
    issued = UnitIssue.objects.filter(
        production=production, unit__material=unit.material, returned_at__isnull=True
    ).count()
    if not plan or issued >= plan.quantity:
        raise ValidationError("Kein freier Platz in der Materialplanung.")
    UnitIssue.objects.create(
        organization=production.organization, unit=unit, production=production, issued_by=user
    )
    return "Ausgabe gespeichert."


@transaction.atomic
def report_defect(unit, description, user):
    unit = lock_unit(unit)
    description = description.strip()
    if not 5 <= len(description) <= 300:
        raise ValidationError("Beschreibung: 5–300 Zeichen erforderlich.")
    if unit.defects.filter(status__in=DefectReport.OPEN).exists():
        raise ValidationError("Für dieses Gerät ist bereits ein Defekt offen.")
    return DefectReport.objects.create(
        organization=unit.organization,
        material=unit.material,
        unit=unit,
        quantity=1,
        description=description,
        reported_by=user,
    )


@transaction.atomic
def resolve_defect(defect, status, resolution, user):
    lock_unit(defect.unit)
    if status not in DefectReport.Status.values:
        raise ValidationError("Ungültiger Defektstatus.")
    resolution = resolution.strip()
    if status == DefectReport.Status.REPAIRED and not 5 <= len(resolution) <= 2000:
        raise ValidationError("Reparaturvermerk: 5–2000 Zeichen erforderlich.")
    defect.status, defect.resolution = status, resolution
    defect.resolved_at = timezone.now() if status == DefectReport.Status.REPAIRED else None
    defect.resolved_by = user if defect.resolved_at else None
    defect.save(update_fields=["status", "resolution", "resolved_at", "resolved_by"])


@transaction.atomic
def archive_unit(unit, operation):
    unit = lock_unit(unit)
    if operation == "restore":
        unit.archived_at = None
        unit.save(update_fields=["archived_at"])
        return
    if (
        unit.issues.filter(returned_at__isnull=True).exists()
        or reservations(unit).filter(production__end_date__gte=timezone.localdate()).exists()
    ):
        raise ValidationError("Gerät ist noch ausgegeben oder reserviert.")
    if operation == "delete":
        if unit.issues.exists() or unit.reservations.exists() or unit.defects.exists():
            raise ValidationError("Geräte mit Historie können nur archiviert werden.")
        unit.delete()
    elif operation == "archive":
        unit.archived_at = timezone.now()
        unit.save(update_fields=["archived_at"])
    else:
        raise ValidationError("Ungültiger Vorgang.")


@transaction.atomic
def teardown(production, operation, user, *, issue_id=None, reason="", note=""):
    production = lock_production(production)
    state = ProductionTeardown.objects.filter(production=production).first()
    if operation == "start":
        if state is None:
            ProductionTeardown.objects.create(
                organization=production.organization, production=production, started_by=user
            )
        return
    if state is None or state.completed_at:
        raise ValidationError("Der Abbau ist nicht aktiv.")
    if operation == "exception":
        issue = UnitIssue.objects.filter(
            pk=issue_id, production=production, returned_at__isnull=True
        ).first()
        if (
            not issue
            or reason not in TeardownException.Reason.values
            or not 5 <= len(note.strip()) <= 2000
        ):
            raise ValidationError(
                "Offene Ausgabe, Grund und Bemerkung (5–2000 Zeichen) erforderlich."
            )
        if TeardownException.objects.filter(issue=issue).exists():
            raise ValidationError("Für diese Ausgabe ist bereits eine Ausnahme dokumentiert.")
        unit = lock_unit(issue.unit)
        if reason == "damaged" and not unit.defects.filter(status__in=DefectReport.OPEN).exists():
            report_defect(unit, ("Bei Abbau beschädigt: " + note.strip())[:300], user)
        TeardownException.objects.create(
            organization=production.organization,
            issue=issue,
            reason=reason,
            note=note.strip(),
            created_by=user,
        )
    elif operation == "complete":
        if UnitIssue.objects.filter(
            production=production, returned_at__isnull=True, exception__isnull=True
        ).exists():
            raise ValidationError("Es sind noch Rückgaben ungeklärt.")
        state.completed_at, state.completed_by = timezone.now(), user
        state.save(update_fields=["completed_at", "completed_by"])
        UnitReservation.objects.filter(production=production, released_at__isnull=True).update(
            released_at=state.completed_at
        )
    else:
        raise ValidationError("Ungültiger Abbauvorgang.")


@transaction.atomic
def checkout(material, quantity, user):
    from .models import MaterialCheckout
    from .services import available

    material = Material.objects.select_for_update().get(pk=material.pk)
    if material.is_archived or not 1 <= quantity <= 10000:
        raise ValidationError("Material archiviert oder ungültige Menge (1–10000).")
    if material.units.filter(archived_at__isnull=True).exists():
        raise ValidationError(
            "Material mit Einzelgeräten bitte über Produktionsreservierung und QR-Scan ausgeben."
        )
    stock = available(material)
    if material.defects.filter(status__in=DefectReport.OPEN).exists():
        raise ValidationError("Für dieses Material ist ein Defekt offen.")
    if stock is not None and quantity > stock:
        raise ValidationError("Nicht genügend Material für diese Ausleihe verfügbar.")
    return MaterialCheckout.objects.create(
        organization=material.organization, material=material, quantity=quantity, user=user
    )


@transaction.atomic
def checkin(loan, user, can_manage):
    from .models import MaterialCheckout

    Material.objects.select_for_update().get(pk=loan.material_id)
    if loan.user_id != user.pk and not can_manage:
        raise ValidationError("Nur eigene Ausleihen können zurückgegeben werden.")
    MaterialCheckout.objects.filter(pk=loan.pk, returned_at__isnull=True).update(
        returned_at=timezone.now()
    )
