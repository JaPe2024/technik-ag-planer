from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.google_sync import drive
from apps.google_sync.google_api import GoogleError
from apps.google_sync.services import connection_for
from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.permissions import Perm
from apps.productions import services as production_services
from apps.productions.models import Production

from . import services
from .forms import (
    DefectForm,
    KitForm,
    KitItemFormSet,
    MaterialCategoryForm,
    MaterialForm,
    MaterialLinkFormSet,
    PlanForm,
    PlanKitForm,
    PlannedQuantityForm,
)
from .models import DefectReport, Kit, Material, MaterialCategory, PlannedMaterial

INVENTORY = {"active_section": "inventory"}
PRODUCTIONS = {"active_section": "productions"}
SETTINGS = {"active_section": "settings"}


# ---------- Abfragen (immer nach AG gefiltert) ----------


def _material(request, pk):
    return get_object_or_404(
        Material.objects.for_org(request.organization).select_related("category"), pk=pk
    )


def _kit(request, pk):
    return get_object_or_404(Kit.objects.for_org(request.organization), pk=pk)


def _defect(request, pk):
    return get_object_or_404(
        DefectReport.objects.for_org(request.organization).select_related("material"), pk=pk
    )


def _production(request, pk):
    return get_object_or_404(Production.objects.for_org(request.organization), pk=pk)


def _planned(request, pk):
    return get_object_or_404(
        PlannedMaterial.objects.for_org(request.organization)
        .filter(production__deleted_at__isnull=True)
        .select_related("production", "material"),
        pk=pk,
    )


def _category(request, pk):
    return get_object_or_404(MaterialCategory.objects.for_org(request.organization), pk=pk)


# ---------- Materialliste und Detail ----------


FILTERS = {"defekt": "Defekt", "archiviert": "Archiviert"}


@org_required
def material_list(request):
    materials = Material.objects.for_org(request.organization).select_related("category")
    query = request.GET.get("q", "").strip()
    if query:
        materials = materials.filter(Q(name__icontains=query) | Q(notes__icontains=query))
    active_category = request.GET.get("kategorie", "")
    if active_category:
        materials = materials.filter(category_id=active_category)
    active_filter = request.GET.get("filter", "")
    if active_filter == "archiviert":
        materials = materials.archived()
    else:
        materials = materials.active()
        if active_filter == "defekt":
            materials = materials.filter(defects__status__in=DefectReport.OPEN).distinct()

    return render(
        request,
        "inventory/list.html",
        {
            **INVENTORY,
            "tab": "material",
            "materials": services.annotate_defects(materials),
            "categories": MaterialCategory.objects.for_org(request.organization),
            "active_category": active_category,
            "active_filter": active_filter,
            "filters": FILTERS,
            "query": query,
        },
    )


@org_required
def material_detail(request, pk):
    material = _material(request, pk)
    services.annotate_defects([material])
    return render(
        request,
        "inventory/detail.html",
        {
            **INVENTORY,
            "material": material,
            "units": material.units.prefetch_related("defects", "issues__production"),
            "links": material.links.all(),
            "attachments": material.attachments.select_related("uploaded_by"),
            "open_defects": material.defects.filter(status__in=DefectReport.OPEN)
            .select_related("reported_by")
            .prefetch_related("attachments"),
            "repaired": material.defects.filter(status=DefectReport.Status.REPAIRED)[:5],
            "plannings": services.material_plannings(material),
            "statuses": DefectReport.Status,
        },
    )


def _material_form(request, material=None):
    instance = material or Material(organization=request.organization)
    form = MaterialForm(request.POST or None, instance=instance, organization=request.organization)
    formset = MaterialLinkFormSet(request.POST or None, instance=instance, prefix="links")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.organization = request.organization
            if saved.created_by_id is None:
                saved.created_by = request.user
            saved.save()
            for link in formset.save(commit=False):
                link.material = saved
                link.organization = request.organization
                link.save()
            for link in formset.deleted_objects:
                link.delete()
        messages.success(request, f"„{saved.name}“ gespeichert.")
        return redirect("inventory:detail", pk=saved.pk)
    return render(
        request,
        "inventory/form.html",
        {**INVENTORY, "form": form, "formset": formset, "material": material},
    )


@permission_required_in_org(Perm.MANAGE_INVENTORY)
def material_create(request):
    return _material_form(request)


@permission_required_in_org(Perm.MANAGE_INVENTORY)
def material_edit(request, pk):
    return _material_form(request, _material(request, pk))


@require_POST
@permission_required_in_org(Perm.MANAGE_INVENTORY)
def material_archive(request, pk):
    material = _material(request, pk)
    if material.is_archived:
        services.unarchive(material)
        messages.success(request, f"„{material.name}“ ist wieder aktiv.")
    else:
        services.archive(material)
        messages.success(request, f"„{material.name}“ archiviert.")
    return redirect("inventory:detail", pk=pk)


# ---------- Defekte ----------


@permission_required_in_org(Perm.REPORT_DEFECT)
def defect_report(request, pk):
    material = _material(request, pk)
    form = DefectForm(
        request.POST or None,
        request.FILES or None,
        material=material,
        allow_photo=connection_for(request.organization) is not None,
    )
    if request.method == "POST" and form.is_valid():
        defect = services.report_defect(
            material,
            form.cleaned_data["quantity"],
            form.cleaned_data["description"],
            request.user,
        )
        messages.success(request, "Defekt gemeldet – danke!")
        photo = form.cleaned_data.get("photo")
        if photo:
            try:
                drive.upload(request.organization, photo, defect=defect, user=request.user)
            except GoogleError as error:
                messages.warning(request, f"Das Foto wurde nicht gespeichert: {error.message}")
        return redirect("inventory:detail", pk=pk)
    return render(
        request, "inventory/defect_form.html", {**INVENTORY, "form": form, "material": material}
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_INVENTORY)
def defect_status(request, pk):
    defect = _defect(request, pk)
    if defect.unit_id and request.organization.inventory_qr_enabled:
        return redirect("inventory:units", pk=defect.material_id)
    status = request.POST.get("status")
    if status in DefectReport.Status.values and status != defect.status:
        services.set_defect_status(defect, status)
        messages.success(request, f"{defect.material}: {DefectReport.Status(status).label}.")
    return redirect("inventory:detail", pk=defect.material_id)


# ---------- Materialsätze ----------


@org_required
def kit_list(request):
    kits = (
        Kit.objects.for_org(request.organization)
        .annotate(item_count=Count("items"))
        .prefetch_related("items__material")
    )
    return render(request, "inventory/kits.html", {**INVENTORY, "tab": "kits", "kits": kits})


def _kit_form(request, kit=None):
    instance = kit or Kit(organization=request.organization)
    form = KitForm(request.POST or None, instance=instance)
    formset = KitItemFormSet(
        request.POST or None,
        instance=instance,
        prefix="items",
        form_kwargs={"organization": request.organization},
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.organization = request.organization
            saved.save()
            for item in formset.save(commit=False):
                item.kit = saved
                item.organization = request.organization
                item.save()
            for item in formset.deleted_objects:
                item.delete()
        messages.success(request, f"Satz „{saved.name}“ gespeichert.")
        return redirect("inventory:kits")
    return render(
        request,
        "inventory/kit_form.html",
        {**INVENTORY, "form": form, "formset": formset, "kit": kit},
    )


@permission_required_in_org(Perm.MANAGE_KITS)
def kit_create(request):
    return _kit_form(request)


@permission_required_in_org(Perm.MANAGE_KITS)
def kit_edit(request, pk):
    return _kit_form(request, _kit(request, pk))


@require_POST
@permission_required_in_org(Perm.MANAGE_KITS)
def kit_copy(request, pk):
    copy = services.copy_kit(_kit(request, pk))
    messages.success(request, "Kopie angelegt – bitte Name anpassen.")
    return redirect("inventory:kit_edit", pk=copy.pk)


@require_POST
@permission_required_in_org(Perm.MANAGE_KITS)
def kit_delete(request, pk):
    kit = _kit(request, pk)
    kit.delete()
    messages.success(
        request, f"Satz „{kit.name}“ gelöscht. Geplante Produktionen bleiben unverändert."
    )
    return redirect("inventory:kits")


# ---------- Material einer Produktion ----------


def _back_to_production(production):
    return redirect(reverse("productions:detail", args=[production.pk]) + "#material")


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def plan_material(request, pk):
    production = _production(request, pk)
    form = PlanForm(request.POST or None, organization=request.organization)
    shortages = []
    if request.method == "POST" and form.is_valid():
        material, quantity = form.cleaned_data["material"], form.cleaned_data["quantity"]
        current = (
            production.planned_material.filter(material=material)
            .values_list("quantity", flat=True)
            .first()
            or 0
        )
        shortage = services.check(material, production, current + quantity)
        if shortage is None or form.cleaned_data["ignore_conflicts"]:
            services.plan(production, material, quantity)
            messages.success(request, f"{material} × {quantity} eingeplant.")
            return _back_to_production(production)
        shortages = [shortage]
        form = PlanForm(
            {**request.POST.dict(), "ignore_conflicts": "on"}, organization=request.organization
        )
        form.is_valid()
    return render(
        request,
        "inventory/plan_form.html",
        {**PRODUCTIONS, "form": form, "production": production, "shortages": shortages},
    )


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def plan_kit(request, pk):
    production = _production(request, pk)
    form = PlanKitForm(request.POST or None, organization=request.organization)
    shortages = []
    if request.method == "POST" and form.is_valid():
        kit = form.cleaned_data["kit"]
        shortages = services.kit_shortages(production, kit)
        if not shortages or form.cleaned_data["ignore_conflicts"]:
            skipped = services.apply_kit(production, kit)
            messages.success(request, f"Satz „{kit.name}“ eingeplant.")
            if skipped:
                names = ", ".join(str(m) for m in skipped)
                messages.warning(request, f"Archiviert und daher nicht eingeplant: {names}.")
            return _back_to_production(production)
        form = PlanKitForm(
            {**request.POST.dict(), "ignore_conflicts": "on"}, organization=request.organization
        )
        form.is_valid()
    return render(
        request,
        "inventory/plan_kit_form.html",
        {**PRODUCTIONS, "form": form, "production": production, "shortages": shortages},
    )


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def planned_edit(request, pk):
    planned = _planned(request, pk)
    form = PlannedQuantityForm(request.POST or None, initial={"quantity": planned.quantity})
    shortages = []
    if request.method == "POST" and form.is_valid():
        quantity = form.cleaned_data["quantity"]
        if quantity < planned.issued_quantity:
            form.add_error(
                "quantity", "Die Menge darf nicht unter der bereits ausgegebenen Menge liegen."
            )
            return render(
                request,
                "inventory/planned_form.html",
                {**PRODUCTIONS, "form": form, "planned": planned, "shortages": []},
            )
        shortage = services.check(planned.material, planned.production, quantity)
        if shortage is None or form.cleaned_data["ignore_conflicts"]:
            planned.quantity = quantity
            planned.save(update_fields=["quantity"])
            messages.success(request, f"{planned.material} × {quantity}.")
            return _back_to_production(planned.production)
        shortages = [shortage]
        form = PlannedQuantityForm({**request.POST.dict(), "ignore_conflicts": "on"})
        form.is_valid()
    return render(
        request,
        "inventory/planned_form.html",
        {**PRODUCTIONS, "form": form, "planned": planned, "shortages": shortages},
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def planned_remove(request, pk):
    planned = _planned(request, pk)
    if (
        planned.movements.exists()
        or planned.material.units.filter(issues__production=planned.production).exists()
    ):
        messages.error(request, "Material mit Ausgabehistorie kann nicht entfernt werden.")
        return _back_to_production(planned.production)
    planned.delete()
    messages.success(request, f"{planned.material} entfernt.")
    return _back_to_production(planned.production)


# ---------- Packliste (alle Mitglieder, freiwillig) ----------


@org_required
def packing_list(request, pk):
    production = _production(request, pk)
    if request.organization.inventory_qr_enabled and request.membership.has_perm(
        Perm.MANAGE_PRODUCTIONS
    ):
        return redirect("inventory:scan", pk=pk)
    planned = production.planned_material.select_related("material", "material__category")
    return render(
        request,
        "inventory/packing_list.html",
        {**PRODUCTIONS, "production": production, "planned": planned},
    )


PACK_FIELDS = {"ausgabe": "issued_at", "rueckgabe": "returned_at"}


@require_POST
@org_required
def packing_toggle(request, pk):
    planned = _planned(request, pk)
    if request.organization.inventory_qr_enabled:
        messages.info(request, "Im QR-Modus erfolgt die Ausgabe und Rückgabe über den Scanner.")
        return redirect("inventory:packing_list", pk=planned.production_id)
    field = PACK_FIELDS.get(request.POST.get("spalte", ""))
    if field:
        services.set_packed(planned, field, getattr(planned, field) is None)
    return redirect(
        reverse("inventory:packing_list", args=[planned.production_id]) + f"#zeile-{planned.pk}"
    )


# ---------- Material-Kategorien (Einstellungen) ----------


@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def categories(request):
    items = MaterialCategory.objects.for_org(request.organization)
    form = MaterialCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = request.organization
        item.position = items.count()
        item.save()
        messages.success(request, f"„{item.name}“ angelegt.")
        return redirect(request.path)
    return render(request, "inventory/categories.html", {**SETTINGS, "items": items, "form": form})


@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_edit(request, pk):
    item = _category(request, pk)
    form = MaterialCategoryForm(request.POST or None, instance=item)
    back = reverse("inventory:categories")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect(back)
    return render(
        request,
        "productions/settings_item_form.html",
        {**SETTINGS, "form": form, "item": item, "back": back},
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_delete(request, pk):
    category = _category(request, pk)
    category.delete()
    messages.success(request, f"Kategorie „{category.name}“ gelöscht.")
    return redirect("inventory:categories")


@require_POST
@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_move(request, pk):
    direction = -1 if request.POST.get("richtung") == "-1" else 1
    production_services.move(
        _category(request, pk), direction, MaterialCategory.objects.for_org(request.organization)
    )
    return redirect("inventory:categories")
