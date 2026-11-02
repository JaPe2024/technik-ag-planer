"""Material: verfügbarer Bestand, Planung je Produktion, Konfliktwarnung, Sätze und Defekte."""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import DefectReport, Kit, KitItem, Material, MaterialCheckout, PlannedMaterial

# ---------- Bestand ----------


def defective_count(material):
    return (
        material.defects.filter(status__in=DefectReport.OPEN).aggregate(n=Sum("quantity"))["n"] or 0
    )


def available(material):
    """Verfügbarer Bestand ohne offene Defekte; None = beliebig."""
    if material.quantity is None:
        return None
    taken = (
        material.checkouts.filter(returned_at__isnull=True).aggregate(n=Sum("quantity"))["n"] or 0
    )
    return max(material.quantity - defective_count(material) - taken, 0)


def annotate_defects(materials):
    """Setzt `defective` und `available` an jedem Material einer Liste."""
    materials = list(materials)
    counts = dict(
        DefectReport.objects.filter(material__in=materials, status__in=DefectReport.OPEN)
        .values("material_id")
        .annotate(n=Sum("quantity"))
        .values_list("material_id", "n")
    )
    loans = dict(
        MaterialCheckout.objects.filter(material__in=materials, returned_at__isnull=True)
        .values("material_id")
        .annotate(n=Sum("quantity"))
        .values_list("material_id", "n")
    )
    for m in materials:
        m.defective = counts.get(m.pk, 0)
        m.checked_out = loans.get(m.pk, 0)
        m.available = (
            None if m.quantity is None else max(m.quantity - m.defective - m.checked_out, 0)
        )
    return materials


# ---------- Bedarf und Konflikte ----------


def _plannings(material, start, end, exclude_production=None):
    qs = PlannedMaterial.objects.filter(
        material=material,
        production__deleted_at__isnull=True,
        production__start_date__lte=end,
        production__end_date__gte=start,
    ).select_related("production")
    if exclude_production is not None:
        qs = qs.exclude(production=exclude_production)
    return list(qs)


def peak_demand(material, start, end, *, extra=0, exclude_production=None):
    """Höchster Tagesbedarf im Zeitraum über alle nicht gelöschten Produktionen.

    Gezählt wird je Tag, damit zwei nacheinander liegende Produktionen sich nicht addieren.
    `extra` ist eine zusätzlich geplante Menge über den ganzen Zeitraum (z. B. beim Hinzufügen).
    """
    plannings = _plannings(material, start, end, exclude_production)
    peak = 0
    day = start
    while day <= end:
        total = extra + sum(
            p.quantity for p in plannings if p.production.start_date <= day <= p.production.end_date
        )
        peak = max(peak, total)
        day += timedelta(days=1)
    return peak


@dataclass
class Shortage:
    material: Material
    needed: int
    available: int

    @property
    def missing(self):
        return self.needed - self.available


def check(material, production, quantity):
    """Konflikt, wenn `quantity` für die Produktion (statt der bisherigen Menge) zu viel wäre."""
    stock = available(material)
    if stock is None:
        return None
    needed = peak_demand(
        material,
        production.start_date,
        production.end_date,
        extra=quantity,
        exclude_production=production,
    )
    return Shortage(material, needed, stock) if needed > stock else None


def production_shortages(production):
    """Überbuchtes Material der Produktion: {material_id: Shortage}."""
    result = {}
    for planned in production.planned_material.select_related("material"):
        stock = available(planned.material)
        if stock is None:
            continue
        needed = peak_demand(planned.material, production.start_date, production.end_date)
        if needed > stock:
            result[planned.material_id] = Shortage(planned.material, needed, stock)
    return result


def production_material(production):
    """Material der Produktion für die Detailansicht, mit `shortage` je Zeile."""
    shortages = production_shortages(production)
    planned = list(
        production.planned_material.select_related("material", "material__category", "source_kit")
    )
    for p in planned:
        p.shortage = shortages.get(p.material_id)
    return planned


def material_plannings(material, today=None):
    """Abschnitt „Geplant“: kommende Produktionen mit Menge, Überbuchung markiert."""
    today = today or timezone.localdate()
    plannings = list(
        material.plannings.filter(
            production__deleted_at__isnull=True, production__end_date__gte=today
        )
        .select_related("production", "production__category")
        .order_by("production__start_date", "production__name")
    )
    stock = available(material)
    for p in plannings:
        p.overbooked = stock is not None and (
            peak_demand(material, p.production.start_date, p.production.end_date) > stock
        )
    return plannings


# ---------- Planen ----------


def plan(production, material, quantity, source_kit=None):
    """Plant Material ein; ist es schon geplant, wird die Menge addiert."""
    planned, created = PlannedMaterial.objects.get_or_create(
        organization=production.organization,
        production=production,
        material=material,
        defaults={"quantity": quantity, "source_kit": source_kit},
    )
    if not created:
        PlannedMaterial.objects.filter(pk=planned.pk).update(quantity=F("quantity") + quantity)
        planned.refresh_from_db()
    return planned


def kit_shortages(production, kit):
    """Konflikte, die das Einplanen des ganzen Satzes auslösen würde."""
    result = []
    for item in kit.items.select_related("material").filter(material__archived_at__isnull=True):
        current = (
            production.planned_material.filter(material=item.material)
            .values_list("quantity", flat=True)
            .first()
            or 0
        )
        shortage = check(item.material, production, current + item.quantity)
        if shortage:
            result.append(shortage)
    return result


@transaction.atomic
def apply_kit(production, kit):
    """Plant alle Positionen des Satzes ein. Gibt übersprungenes (archiviertes) Material zurück."""
    skipped = []
    for item in kit.items.select_related("material"):
        if item.material.is_archived:
            skipped.append(item.material)
            continue
        plan(production, item.material, item.quantity, source_kit=kit)
    return skipped


def copy_plannings(source, target):
    """Für „Produktion kopieren“: Material mit Mengen, ohne Packlisten-Haken."""
    PlannedMaterial.objects.bulk_create(
        PlannedMaterial(
            organization=target.organization,
            production=target,
            material_id=p.material_id,
            quantity=p.quantity,
            source_kit_id=p.source_kit_id,
        )
        for p in source.planned_material.all()
    )


def set_packed(planned, field, done):
    """Packliste: `issued_at` oder `returned_at` setzen bzw. zurücknehmen."""
    if field not in ("issued_at", "returned_at"):
        raise ValueError(field)
    setattr(planned, field, timezone.now() if done else None)
    planned.save(update_fields=[field])


# ---------- Sätze ----------


@transaction.atomic
def copy_kit(kit):
    copy = Kit.objects.create(
        organization=kit.organization,
        name=f"{kit.name} (Kopie)"[:120],
        description=kit.description,
    )
    KitItem.objects.bulk_create(
        KitItem(
            organization=kit.organization,
            kit=copy,
            material_id=item.material_id,
            quantity=item.quantity,
        )
        for item in kit.items.all()
    )
    return copy


# ---------- Defekte ----------


def report_defect(material, quantity, description, user):
    return DefectReport.objects.create(
        organization=material.organization,
        material=material,
        quantity=quantity,
        description=description.strip(),
        reported_by=user,
    )


def set_defect_status(defect, status):
    defect.status = status
    defect.resolved_at = timezone.now() if status == DefectReport.Status.REPAIRED else None
    defect.save(update_fields=["status", "resolved_at"])


# ---------- Archiv ----------


def archive(material):
    material.archived_at = timezone.now()
    material.save(update_fields=["archived_at", "updated_at"])


def unarchive(material):
    material.archived_at = None
    material.save(update_fields=["archived_at", "updated_at"])
