from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.inventory import services, unit_services
from apps.inventory.models import (
    DefectReport,
    MaterialUnit,
    PlannedMaterial,
    ProductionTeardown,
    TeardownException,
    UnitIssue,
    UnitReservation,
)


@pytest.fixture
def unit(org, mics):
    mics.tracking = "individual"
    mics.save(update_fields=["tracking"])
    org.inventory_qr_enabled = True
    org.save(update_fields=["inventory_qr_enabled"])
    return MaterialUnit.objects.create(organization=org, material=mics, code="MIC-01")


@pytest.fixture
def planned(org, concert, mics):
    return PlannedMaterial.objects.create(
        organization=org, production=concert, material=mics, quantity=2
    )


def test_reservation_scan_return(org, concert, unit, planned, planner):
    unit_services.reserve(concert, unit, planner.user)
    unit_services.scan_unit(concert, "https://example.org/geraet/mic-01/", "issue", planner.user)
    with pytest.raises(ValidationError):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    issue = UnitIssue.objects.get()
    assert issue.organization == org and issue.returned_at is None
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    issue.refresh_from_db()
    assert issue.returned_by == planner.user and issue.returned_at


def test_overlap_and_adjacent_days(org, concert, unit, planned, planner, make_production):
    unit_services.reserve(concert, unit, planner.user)
    other = make_production(org)
    PlannedMaterial.objects.create(organization=org, production=other, material=unit.material)
    with pytest.raises(ValidationError, match="bereits reserviert"):
        unit_services.reserve(other, unit, planner.user)
    other.start_date = concert.end_date + timedelta(days=1)
    other.end_date = other.start_date
    other.save()
    unit_services.reserve(other, unit, planner.user)
    with pytest.raises(ValidationError, match="vorher"):
        unit_services.scan_unit(other, unit.code, "issue", planner.user)


def test_no_reservation_and_expired(concert, unit, planned, planner):
    with pytest.raises(ValidationError, match="Reservierung"):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.reserve(concert, unit, planner.user)
    concert.start_date = concert.end_date = timezone.localdate() - timedelta(days=1)
    concert.save()
    with pytest.raises(ValidationError, match="Reservierung"):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)


def test_unit_defect_counts_once_and_only_blocks_affected_device(
    org, concert, unit, planned, planner
):
    second = MaterialUnit.objects.create(organization=org, material=unit.material, code="MIC-02")
    defect = unit_services.report_defect(unit, "Kapsel ist beschädigt", planner.user)
    assert services.defective_count(unit.material) == 1
    with pytest.raises(ValidationError, match="defekt"):
        unit_services.reserve(concert, unit, planner.user)
    unit_services.reserve(concert, second, planner.user)
    with pytest.raises(ValidationError):
        unit_services.resolve_defect(defect, "repaired", "", planner.user)
    unit_services.resolve_defect(defect, "repaired", "Kapsel ausgetauscht", planner.user)
    assert services.defective_count(unit.material) == 0
    unit_services.reserve(concert, unit, planner.user)


def test_teardown_missing_device_stays_blocked(concert, unit, planned, planner):
    unit_services.reserve(concert, unit, planner.user)
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.teardown(concert, "start", planner.user)
    with pytest.raises(ValidationError, match="ungeklärt"):
        unit_services.teardown(concert, "complete", planner.user)
    unit_services.teardown(
        concert,
        "exception",
        planner.user,
        issue_id=UnitIssue.objects.get().pk,
        reason="missing",
        note="Beim Abbau nicht gefunden",
    )
    unit_services.teardown(concert, "complete", planner.user)
    assert ProductionTeardown.objects.get().completed_at
    assert not UnitReservation.objects.filter(released_at__isnull=True).exists()
    assert UnitIssue.objects.get().returned_at is None
    with pytest.raises(ValidationError):
        unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    assert UnitIssue.objects.get().returned_at
    assert TeardownException.objects.count() == 1


def test_damaged_exception_creates_real_defect(concert, unit, planned, planner):
    unit_services.reserve(concert, unit, planner.user)
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    unit_services.teardown(concert, "start", planner.user)
    unit_services.teardown(
        concert,
        "exception",
        planner.user,
        issue_id=UnitIssue.objects.get().pk,
        reason="damaged",
        note="Gehäuse beim Abbau gebrochen",
    )
    assert DefectReport.objects.get().unit == unit
    with pytest.raises(ValidationError):
        unit_services.teardown(
            concert,
            "exception",
            planner.user,
            issue_id=UnitIssue.objects.get().pk,
            reason="other",
            note="Noch eine Ausnahme",
        )


def test_archive_and_delete_history(concert, unit, planned, planner):
    reservation = unit_services.reserve(concert, unit, planner.user)
    with pytest.raises(ValidationError):
        unit_services.archive_unit(unit, "archive")
    unit_services.cancel(reservation)
    with pytest.raises(ValidationError):
        unit_services.archive_unit(unit, "delete")
    unit_services.archive_unit(unit, "archive")
    unit.refresh_from_db()
    assert unit.archived_at
    unit_services.archive_unit(unit, "restore")
    unit.refresh_from_db()
    assert unit.archived_at is None


def test_pages_and_permissions(concert, unit, planned, planner_client, member_client):
    for name, pk in [
        ("units", unit.material_id),
        ("scan", concert.pk),
        ("teardown_protocol", concert.pk),
    ]:
        assert planner_client.get(reverse(f"inventory:{name}", args=[pk])).status_code == 200
    assert (
        planner_client.get(reverse("inventory:unit_qr", args=[unit.pk]))["Content-Type"]
        == "image/png"
    )
    assert (
        member_client.post(
            reverse("inventory:reserve_unit", args=[concert.pk]), {"unit_id": unit.pk}
        ).status_code
        == 403
    )
    assert (
        member_client.post(
            reverse("inventory:unit_action", args=[unit.pk]), {"operation": "archive"}
        ).status_code
        == 403
    )
    response = planner_client.post(
        reverse("inventory:scan", args=[concert.pk]),
        {"code": unit.code, "mode": "issue"},
        HTTP_ACCEPT="application/json",
    )
    assert response.json()["ok"] is False


def test_foreign_ag_rejected(other_org, unit, concert, planned, planner_client, make_material):
    foreign = MaterialUnit.objects.create(
        organization=other_org, material=make_material(other_org), code="FOREIGN-01"
    )
    assert planner_client.get(reverse("inventory:unit_qr", args=[foreign.pk])).status_code == 404
    assert (
        planner_client.post(
            reverse("inventory:reserve_unit", args=[concert.pk]), {"unit_id": foreign.pk}
        ).status_code
        == 404
    )
    assert (
        planner_client.post(
            reverse("inventory:scan", args=[concert.pk]),
            {"code": foreign.code, "mode": "issue"},
            HTTP_ACCEPT="application/json",
        ).json()["ok"]
        is False
    )


def test_custom_code_grows_stock(unit, planner_client):
    unit.material.quantity = 1
    unit.material.save()
    planner_client.post(
        reverse("inventory:unit_create", args=[unit.material_id]), {"code": "MIC-02"}
    )
    assert MaterialUnit.objects.count() == 2
    unit.material.refresh_from_db()
    assert unit.material.quantity == 2
    assert (
        planner_client.post(
            reverse("inventory:unit_create", args=[unit.material_id]), {"code": "bad/code"}
        ).status_code
        == 302
    )


def test_checkout_capacity_return_and_ownership(unit, planner_client, member_client, planner, mics):
    from apps.inventory.models import MaterialCheckout

    # Bulk loans are kept separate from scanned single-device issues.
    unit.delete()
    mics.organization.inventory_qr_enabled = False
    mics.organization.save(update_fields=["inventory_qr_enabled"])
    mics.quantity = 2
    mics.save()
    url = reverse("inventory:checkout", args=[mics.pk])
    assert member_client.post(url, {"quantity": "2"}).status_code == 302
    loan = MaterialCheckout.objects.get()
    planner_client.post(url, {"quantity": "1"})
    assert MaterialCheckout.objects.count() == 1
    member_client.post(reverse("inventory:checkin", args=[loan.pk]))
    loan.refresh_from_db()
    assert loan.returned_at
    planner_client.post(url, {"quantity": "1"})
    other_loan = MaterialCheckout.objects.get(returned_at__isnull=True)
    member_client.post(reverse("inventory:checkin", args=[other_loan.pk]))
    other_loan.refresh_from_db()
    assert other_loan.returned_at is None
    planner_client.post(reverse("inventory:checkin", args=[other_loan.pk]))
    other_loan.refresh_from_db()
    assert other_loan.returned_at


def test_legacy_generated_lowercase_code(concert, unit, planned, planner):
    unit.code = "TAG-abcdef01234"
    unit.save()
    unit_services.reserve(concert, unit, planner.user)
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    assert UnitIssue.objects.get().unit == unit


def test_cancel_issued_and_return_wrong_production(
    org, concert, unit, planned, planner, make_production
):
    reservation = unit_services.reserve(concert, unit, planner.user)
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    with pytest.raises(ValidationError):
        unit_services.cancel(reservation)
    other = make_production(org)
    with pytest.raises(ValidationError):
        unit_services.scan_unit(other, unit.code, "return", planner.user)
    assert UnitIssue.objects.get().returned_at is None


def test_labels_and_bulk_loan_ui(mics, planner_client, unit, org):
    assert planner_client.get(reverse("inventory:labels")).status_code == 200
    org.inventory_qr_enabled = False
    org.save(update_fields=["inventory_qr_enabled"])
    assert (
        "Persönliche Ausleihe"
        in planner_client.get(reverse("inventory:detail", args=[mics.pk])).content.decode()
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("operation", ["reserve", "issue"])
def test_parallel_device_operations_are_serialized(
    operation, org, concert, unit, planned, planner, make_production
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    if connection.vendor != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    other = make_production(org)
    PlannedMaterial.objects.create(
        organization=org, production=other, material=unit.material, quantity=1
    )
    if operation == "issue":
        unit_services.reserve(concert, unit, planner.user)
    barrier = Barrier(2)

    def act(production):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                if operation == "reserve":
                    unit_services.reserve(production, unit, planner.user)
                else:
                    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
            except ValidationError:
                return False
            return True
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(act, [concert, other]))
    assert sorted(results) == [False, True]
    if operation == "reserve":
        assert UnitReservation.objects.filter(released_at__isnull=True).count() == 1
    else:
        assert UnitIssue.objects.filter(returned_at__isnull=True).count() == 1


def test_bulk_loans_reduce_planning_availability(mics, planner):
    original = services.available(mics)
    loan = unit_services.checkout(mics, 2, planner.user)
    assert services.available(mics) == original - 2
    annotated = services.annotate_defects([mics])[0]
    assert annotated.available == original - 2 and annotated.checked_out == 2
    unit_services.checkin(loan, planner.user, False)
    assert services.available(mics) == original


def test_modes_are_exclusive(org, concert, planned, planner_client):
    planned.material.tracking = "individual"
    planned.material.save(update_fields=["tracking"])
    settings_url = reverse("inventory:settings")
    detail_url = reverse("inventory:detail", args=[planned.material_id])
    pack_url = reverse("inventory:packing_list", args=[concert.pk])
    units_url = reverse("inventory:units", args=[planned.material_id])
    classic = planner_client.get(detail_url).content.decode()
    assert "Einzelgeräte &amp; QR-Etiketten" not in classic
    assert planner_client.get(units_url).status_code == 302
    assert "pack__check" in planner_client.get(pack_url).content.decode()
    planner_client.post(settings_url, {"mode": "qr"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    assert "Einzelgeräte &amp; QR-Etiketten" in planner_client.get(detail_url).content.decode()
    assert planner_client.get(units_url).status_code == 200
    assert planner_client.get(pack_url).url == reverse("inventory:scan", args=[concert.pk])
    planner_client.post(
        reverse("inventory:packing_toggle", args=[planned.pk]), {"spalte": "ausgabe"}
    )
    planned.refresh_from_db()
    assert planned.issued_at is None
    planner_client.post(settings_url, {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    assert "pack__check" in planner_client.get(pack_url).content.decode()


def test_switch_preserves_devices_and_blocks_outstanding_issues(
    org, unit, planned, concert, planner, planner_client
):
    url = reverse("inventory:settings")
    unit_services.reserve(concert, unit, planner.user)
    planner_client.post(url, {"mode": "classic"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    unit_services.scan_unit(concert, unit.code, "issue", planner.user)
    planner_client.post(url, {"mode": "classic"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    unit_services.scan_unit(concert, unit.code, "return", planner.user)
    unit_services.cancel(UnitReservation.objects.get())
    planner_client.post(url, {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    assert MaterialUnit.objects.get().code == unit.code
    planner_client.post(url, {"mode": "qr"})
    assert (
        planner_client.get(reverse("inventory:units", args=[unit.material_id])).status_code == 200
    )


def test_settings_rights_and_ag_scope(org, other_org, planner_client, member_client):
    url = reverse("inventory:settings")
    assert member_client.post(url, {"mode": "qr"}).status_code == 403
    planner_client.post(url, {"mode": "qr"})
    other_org.refresh_from_db()
    assert not other_org.inventory_qr_enabled
    planner_client.post(url, {"mode": "invalid"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled


def test_add_first_device_from_qr_interface(org, mics, planner_client):
    mics.tracking = "individual"
    mics.save(update_fields=["tracking"])
    planner_client.post(reverse("inventory:settings"), {"mode": "qr"})
    response = planner_client.post(reverse("inventory:unit_create", args=[mics.pk]), {"code": ""})
    unit = MaterialUnit.objects.get()
    assert response.url == reverse("inventory:units", args=[mics.pk])
    page = planner_client.get(response.url).content.decode()
    assert unit.code in page and "Einzelgerät hinzufügen" in page
    assert "QR-Etikett anzeigen" in page


def test_classic_mode_reuses_material_with_existing_devices(org, unit, planned, planner_client):
    planner_client.post(reverse("inventory:settings"), {"mode": "classic"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled
    response = planner_client.post(
        reverse("inventory:checkout", args=[unit.material_id]), {"quantity": 1}
    )
    assert response.status_code == 302
    assert unit.material.checkouts.filter(returned_at__isnull=True).count() == 1
    planner_client.post(reverse("inventory:settings"), {"mode": "qr"})
    org.refresh_from_db()
    assert not org.inventory_qr_enabled


def test_reservations_only_on_production_page(unit, planned, concert, planner_client):
    production_url = reverse("productions:detail", args=[concert.pk])
    scan_url = reverse("inventory:scan", args=[concert.pk])
    reserve_url = reverse("inventory:reserve_unit", args=[concert.pk])
    page = planner_client.get(production_url).content.decode()
    assert reserve_url in page and "Gerät reservieren" in page
    scan_page = planner_client.get(scan_url).content.decode()
    assert reserve_url not in scan_page
    assert "Reservierungen in der Produktion verwalten" in scan_page
    response = planner_client.post(reserve_url, {"unit_id": unit.pk})
    assert response.url == production_url + "#material"
    reservation = UnitReservation.objects.get()
    assert unit.code in planner_client.get(production_url).content.decode()
    assert unit.code in planner_client.get(scan_url).content.decode()
    response = planner_client.post(reverse("inventory:cancel_reservation", args=[reservation.pk]))
    assert response.url == production_url + "#material"


def test_bulk_partial_return_and_teardown(org, concert, planned, planner, planner_client):
    org.inventory_qr_enabled = True
    org.save()
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    planned.refresh_from_db()
    assert planned.outstanding_quantity == 2
    with pytest.raises(ValidationError):
        unit_services.move_quantity(planned, "return", 3, planner.user)
    unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "start", planner.user)
    with pytest.raises(ValidationError, match="Mengenmaterial"):
        unit_services.teardown(concert, "complete", planner.user)
    planner_client.post(reverse("inventory:settings"), {"mode": "classic"})
    org.refresh_from_db()
    assert org.inventory_qr_enabled
    unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "complete", planner.user)
    planned.refresh_from_db()
    assert planned.outstanding_quantity == 0 and planned.movements.count() == 3


def test_consumable_reduces_stock_without_return(org, concert, planned, planner):
    org.inventory_qr_enabled = True
    org.save()
    material = planned.material
    material.tracking = "consumable"
    material.save()
    before = material.quantity
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    material.refresh_from_db()
    assert material.quantity == before - 2
    with pytest.raises(ValidationError):
        unit_services.move_quantity(planned, "return", 1, planner.user)
    unit_services.teardown(concert, "start", planner.user)
    unit_services.teardown(concert, "complete", planner.user)


def test_bulk_output_has_no_device_scanner(org, concert, planned, planner_client):
    org.inventory_qr_enabled = True
    org.save()
    content = planner_client.get(reverse("inventory:scan", args=[concert.pk])).content.decode()
    assert "Menge ausgeben" in content and 'id="scan-form"' not in content
    response = planner_client.post(
        reverse("inventory:quantity_move", args=[planned.pk]), {"quantity": 1, "operation": "issue"}
    )
    assert response.status_code == 302
    planned.refresh_from_db()
    assert planned.issued_quantity == 1
    content = planner_client.get(
        reverse("inventory:teardown_protocol", args=[concert.pk])
    ).content.decode()
    assert planned.material.name in content


def test_bulk_stock_cannot_be_double_issued(org, concert, planned, planner, make_production):
    org.inventory_qr_enabled = True
    org.save()
    material = planned.material
    material.quantity = 2
    material.save()
    other = make_production(org)
    second = PlannedMaterial.objects.create(
        organization=org, production=other, material=material, quantity=2
    )
    unit_services.move_quantity(planned, "issue", 2, planner.user)
    with pytest.raises(ValidationError, match="verfügbar"):
        unit_services.move_quantity(second, "issue", 1, planner.user)


def test_new_inventory_data_is_exported_and_audited(
    org, other_org, unit, concert, planned, planner, make_material
):
    import io
    import json
    import zipfile

    from django.apps import apps

    from apps.audit.context import acting_as
    from apps.audit.models import AuditEntry
    from apps.organizations.export import export_organization

    foreign = MaterialUnit.objects.create(
        organization=other_org, material=make_material(other_org), code="FOREIGN-EXPORT"
    )
    with acting_as(planner.user):
        reservation = unit_services.reserve(concert, unit, planner.user)
        unit_services.cancel(reservation)
    changes = AuditEntry.objects.filter(organization=org, actor=planner.user, action="update")
    assert any("released_at" in entry.changes for entry in changes)
    with zipfile.ZipFile(io.BytesIO(export_organization(org))) as archive:
        data = {name: json.loads(archive.read(name)) for name in archive.namelist()}
    names = [
        "MaterialUnit",
        "UnitIssue",
        "UnitReservation",
        "ProductionTeardown",
        "TeardownException",
        "MaterialCheckout",
        "QuantityMovement",
    ]
    from apps.audit.registry import _registry

    for name in names:
        model = apps.get_model("inventory", name)
        assert model in _registry
        assert f"inventory_{model._meta.model_name}.json" in data
    assert data["ag.json"]["inventory_qr_enabled"] is True
    assert [row["code"] for row in data["inventory_materialunit.json"]] == [unit.code]
    assert foreign.code not in json.dumps(data)
