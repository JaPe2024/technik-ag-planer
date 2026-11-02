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


def test_custom_code_and_stock_limit(unit, planner_client):
    unit.material.quantity = 1
    unit.material.save()
    planner_client.post(
        reverse("inventory:unit_create", args=[unit.material_id]), {"code": "MIC-02"}
    )
    assert MaterialUnit.objects.count() == 1
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


def test_labels_and_bulk_loan_ui(mics, planner_client):
    assert planner_client.get(reverse("inventory:labels")).status_code == 200
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
