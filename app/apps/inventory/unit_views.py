import uuid
from io import BytesIO

import qrcode
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.permissions import Perm

from . import unit_services as services
from .models import (
    DefectReport,
    Material,
    MaterialUnit,
    ProductionTeardown,
    UnitIssue,
    UnitReservation,
)
from .views import _production


def _unit(request, pk):
    if not str(pk).isdigit():
        raise Http404
    return get_object_or_404(
        MaterialUnit.objects.for_org(request.organization).select_related("material"), pk=pk
    )


def _run(request, action):
    try:
        action()
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Gespeichert.")


@org_required
def units(request, pk):
    material = get_object_or_404(Material.objects.for_org(request.organization), pk=pk)
    return render(
        request,
        "inventory/units.html",
        {
            "material": material,
            "units": material.units.prefetch_related("defects", "issues__production"),
            "active_section": "inventory",
            "statuses": DefectReport.Status,
        },
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_INVENTORY)
def create_unit(request, pk):
    material = get_object_or_404(Material.objects.for_org(request.organization).active(), pk=pk)
    try:
        code = services.normalize_code(request.POST.get("code", "") or f"TAG-{uuid.uuid4().hex}")
        with transaction.atomic():
            Material.objects.select_for_update().get(pk=material.pk)
            if (
                material.quantity is not None
                and material.units.filter(archived_at__isnull=True).count() >= material.quantity
            ):
                raise ValidationError(
                    "Der Bestand ist bereits vollständig als Einzelgeräte erfasst."
                )
            if material.checkouts.filter(returned_at__isnull=True).exists():
                raise ValidationError("Zuerst die offenen persönlichen Ausleihen zurückgeben.")
            MaterialUnit.objects.create(
                organization=request.organization, material=material, code=code
            )
    except (ValidationError, IntegrityError) as error:
        messages.error(
            request,
            " ".join(error.messages)
            if isinstance(error, ValidationError)
            else "Dieser Inventarcode ist bereits vergeben.",
        )
    return redirect("inventory:units", pk=pk)


@org_required
def qr(request, pk):
    unit = _unit(request, pk)
    stream = BytesIO()
    qrcode.make(request.build_absolute_uri(f"/geraet/{unit.code}/")).save(stream, format="PNG")
    return HttpResponse(stream.getvalue(), content_type="image/png")


@org_required
def device(request, code):
    unit = get_object_or_404(MaterialUnit.objects.for_org(request.organization), code=code)
    return redirect("inventory:units", pk=unit.material_id)


@require_POST
@permission_required_in_org(Perm.MANAGE_INVENTORY)
def unit_action(request, pk):
    unit = _unit(request, pk)
    material_id = unit.material_id
    _run(request, lambda: services.archive_unit(unit, request.POST.get("operation")))
    return redirect("inventory:units", pk=material_id)


@require_POST
@permission_required_in_org(Perm.REPORT_DEFECT)
def unit_defect(request, pk):
    unit = _unit(request, pk)
    _run(
        request,
        lambda: services.report_defect(unit, request.POST.get("description", ""), request.user),
    )
    return redirect("inventory:units", pk=unit.material_id)


@require_POST
@permission_required_in_org(Perm.MANAGE_INVENTORY)
def resolve_defect(request, pk):
    defect = get_object_or_404(
        DefectReport.objects.for_org(request.organization), pk=pk, unit__isnull=False
    )
    _run(
        request,
        lambda: services.resolve_defect(
            defect, request.POST.get("status"), request.POST.get("resolution", ""), request.user
        ),
    )
    return redirect("inventory:units", pk=defect.material_id)


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def reserve(request, pk):
    production = _production(request, pk)
    unit = _unit(request, request.POST.get("unit_id", "0"))
    _run(request, lambda: services.reserve(production, unit, request.user))
    return redirect("inventory:scan", pk=pk)


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def cancel(request, pk):
    reservation = get_object_or_404(
        UnitReservation.objects.for_org(request.organization),
        pk=pk,
        production__deleted_at__isnull=True,
    )
    _run(request, lambda: services.cancel(reservation))
    return redirect("inventory:scan", pk=reservation.production_id)


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def scan(request, pk):
    production = _production(request, pk)
    if request.method == "POST":
        try:
            message = services.scan_unit(
                production, request.POST.get("code", ""), request.POST.get("mode"), request.user
            )
        except ValidationError as error:
            message, ok = " ".join(error.messages), False
        else:
            ok = True
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"ok": ok, "message": message})
        (messages.success if ok else messages.error)(request, message)
        return redirect("inventory:scan", pk=pk)
    return render(
        request,
        "inventory/scan.html",
        {
            "production": production,
            "issues": UnitIssue.objects.for_org(request.organization)
            .filter(production=production)
            .select_related("unit", "issued_by", "returned_by", "exception"),
            "reservations": UnitReservation.objects.for_org(request.organization)
            .filter(production=production, released_at__isnull=True)
            .select_related("unit__material"),
            "available_units": MaterialUnit.objects.for_org(request.organization)
            .filter(
                archived_at__isnull=True,
                material__archived_at__isnull=True,
                material__plannings__production=production,
            )
            .select_related("material"),
            "teardown": ProductionTeardown.objects.filter(production=production).first(),
            "active_section": "inventory",
        },
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def teardown(request, pk):
    production = _production(request, pk)
    issue_id = request.POST.get("issue_id", "")
    _run(
        request,
        lambda: services.teardown(
            production,
            request.POST.get("operation"),
            request.user,
            issue_id=issue_id if issue_id.isdigit() else None,
            reason=request.POST.get("reason", ""),
            note=request.POST.get("note", ""),
        ),
    )
    return redirect("inventory:scan", pk=pk)


@org_required
def protocol(request, pk):
    production = _production(request, pk)
    return render(
        request,
        "inventory/protocol.html",
        {
            "production": production,
            "teardown": ProductionTeardown.objects.filter(production=production)
            .select_related("started_by", "completed_by")
            .first(),
            "issues": UnitIssue.objects.for_org(request.organization)
            .filter(production=production)
            .select_related("unit__material", "issued_by", "returned_by", "exception__created_by"),
            "active_section": "inventory",
        },
    )


@require_POST
@org_required
def checkout(request, pk):
    material = get_object_or_404(Material.objects.for_org(request.organization), pk=pk)
    raw = request.POST.get("quantity", "1")
    if not raw.isdigit() or len(raw) > 5:
        messages.error(request, "Bitte eine gültige Menge angeben.")
    else:
        _run(request, lambda: services.checkout(material, int(raw), request.user))
    return redirect("inventory:detail", pk=pk)


@require_POST
@org_required
def checkin(request, pk):
    from apps.organizations.permissions import role_has_perm

    from .models import MaterialCheckout

    loan = get_object_or_404(MaterialCheckout.objects.for_org(request.organization), pk=pk)
    _run(
        request,
        lambda: services.checkin(
            loan, request.user, role_has_perm(request.membership.role, Perm.MANAGE_INVENTORY)
        ),
    )
    return redirect("inventory:detail", pk=loan.material_id)


@org_required
def labels(request):
    return render(
        request,
        "inventory/labels.html",
        {
            "units": MaterialUnit.objects.for_org(request.organization)
            .filter(archived_at__isnull=True, material__archived_at__isnull=True)
            .select_related("material"),
            "active_section": "inventory",
        },
    )
