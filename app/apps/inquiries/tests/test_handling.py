"""Anfragen bearbeiten, Einstellungen, Rechte und Mandantentrennung."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inquiries import services
from apps.inquiries.models import Inquiry, InquiryLink
from apps.inquiries.tasks import purge_done_inquiries
from apps.organizations.permissions import Role
from apps.productions.models import Production, ProductionStatus


def _member(org, owner, make_member, role):
    """Pro AG gibt es genau einen Owner – der kommt aus der Fixture."""
    return owner if role == Role.OWNER else make_member(org, role)


# ---------- Produktionsliste ----------


@pytest.mark.parametrize(
    ("role", "visible"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_production_list_shows_open_inquiries(
    org, owner, make_member, login, evening, role, visible
):
    client = login(_member(org, owner, make_member, role).user, org)
    content = client.get(reverse("productions:list")).content.decode()

    assert ("Elternabend ·" in content) is visible
    if visible:
        assert "19:00–21:30 Uhr · Aula · von Frau Muster" in content


def test_done_inquiries_leave_the_list(org, planner_client, evening):
    services.mark_done(evening, None)
    assert "Elternabend ·" not in planner_client.get(reverse("productions:list")).content.decode()


# ---------- Geteilte Ansicht ----------


def test_split_view_prefills_date_and_suggests_jobs(planner_client, evening):
    response = planner_client.get(reverse("inquiries:detail", args=[evening.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert f'value="{evening.date.isoformat()}"' in content
    for name in ["Aufbau", "Veranstaltung", "Abbau"]:
        assert f'value="{name}"' in content
    assert 'value="17:00"' in content and 'value="22:00"' in content
    assert "mailto:muster@schule.example" in content
    assert "tel:0221 123456" in content
    assert 'data-copy="Aula"' in content
    assert "data-paste=" in content
    assert "Mikrofone, Beamer und Leinwand" in content


def test_suggested_jobs_need_both_times(org, make_inquiry):
    from datetime import time

    only_start = make_inquiry(org, start_time=time(19))
    assert services.suggested_jobs(only_start) == []

    with_end = make_inquiry(org, start_time=time(19), end_time=time(20))
    assert [j["name"] for j in services.suggested_jobs(with_end)] == ["Veranstaltung"]


def test_create_production_from_inquiry(org, planner_client, evening):
    day = evening.date.isoformat()
    data = {
        "name": "Elternabend 5b",
        "start_date": day,
        "end_date": day,
        "status": ProductionStatus.planning_for(org).pk,
        "location_name": "Aula",
        "address": "",
        "notes": "",
        "jobs-TOTAL_FORMS": "2",
        "jobs-INITIAL_FORMS": "0",
        "jobs-MIN_NUM_FORMS": "0",
        "jobs-MAX_NUM_FORMS": "1000",
        "jobs-0-name": "Aufbau",
        "jobs-0-date": day,
        "jobs-0-start_time": "17:00",
        "jobs-0-end_time": "19:00",
        "jobs-1-name": "Veranstaltung",
        "jobs-1-date": day,
        "jobs-1-start_time": "19:00",
        "jobs-1-end_time": "21:30",
    }
    response = planner_client.post(reverse("inquiries:detail", args=[evening.pk]), data)

    production = Production.objects.for_org(org).get()
    assert response.url == reverse("inquiries:followup", args=[evening.pk])
    assert [j.name for j in production.jobs.all()] == ["Aufbau", "Veranstaltung"]
    evening.refresh_from_db()
    assert evening.production == production and not evening.is_done
    assert "Produktion angelegt" in planner_client.get(reverse("productions:list")).content.decode()


def test_invalid_production_shows_production_pane(planner_client, evening):
    response = planner_client.post(
        reverse("inquiries:detail", args=[evening.pk]),
        {"name": "", "jobs-TOTAL_FORMS": "0", "jobs-INITIAL_FORMS": "0"},
    )
    assert response.status_code == 200
    assert 'data-split="produktion"' in response.content.decode()
    assert not Production.objects.exists()


def test_done_and_reopen(org, planner_client, planner, evening):
    url = reverse("inquiries:done", args=[evening.pk])
    planner_client.post(url)
    evening.refresh_from_db()
    assert evening.is_done and evening.done_by == planner.user

    done = planner_client.get(reverse("inquiries:done_list")).content.decode()
    assert "Elternabend" in done and "180 Tagen" in done

    planner_client.post(url)
    evening.refresh_from_db()
    assert not evening.is_done


def test_purge_after_keep_days(org, make_inquiry, settings):
    settings.INQUIRY_KEEP_DONE_DAYS = 180
    old = make_inquiry(org, "Alt", done_at=timezone.now() - timedelta(days=181))
    recent = make_inquiry(org, "Neu", done_at=timezone.now() - timedelta(days=10))
    open_one = make_inquiry(org, "Offen")

    assert purge_done_inquiries() == 1
    assert set(Inquiry.objects.values_list("pk", flat=True)) == {recent.pk, open_one.pk}
    assert not Inquiry.objects.filter(pk=old.pk).exists()


# ---------- Einstellungen ----------


def test_link_settings_activate_renew_deactivate(org, owner, login):
    client = login(owner.user, org)
    url = reverse("inquiries:settings")
    assert "Link ist nicht aktiv" in client.get(url).content.decode()

    client.post(url, {"action": "activate"})
    link = InquiryLink.objects.get(organization=org)
    content = client.get(url).content.decode()
    assert link.is_active and "Link ist aktiv" in content
    assert f"/anfrage/{link.token}/" in content

    old_token = link.token
    client.post(url, {"action": "renew"})
    link.refresh_from_db()
    assert link.token != old_token and link.is_active

    client.post(url, {"action": "deactivate"})
    link.refresh_from_db()
    assert not link.is_active


def test_settings_menu_links_inquiry_settings(org, owner, login):
    content = login(owner.user, org).get(reverse("organizations:settings")).content.decode()
    assert reverse("inquiries:settings") in content


# ---------- Rechte und Mandantentrennung ----------


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 403), (Role.STUDENT, 403)],
)
def test_link_settings_for_owner_and_admin(org, owner, make_member, login, role, expected):
    client = login(_member(org, owner, make_member, role).user, org)
    assert client.get(reverse("inquiries:settings")).status_code == expected
    client.post(reverse("inquiries:settings"), {"action": "activate"})
    is_active = InquiryLink.objects.filter(organization=org, is_active=True).exists()
    assert is_active is (expected == 200)


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 200), (Role.STUDENT, 403)],
)
def test_handling_rights(org, owner, make_member, login, evening, role, expected):
    client = login(_member(org, owner, make_member, role).user, org)
    assert client.get(reverse("inquiries:detail", args=[evening.pk])).status_code == expected
    assert client.get(reverse("inquiries:done_list")).status_code == expected
    client.post(reverse("inquiries:done", args=[evening.pk]))
    evening.refresh_from_db()
    assert evening.is_done is (expected == 200)


@pytest.mark.parametrize(
    ("method", "url_name"),
    [
        ("get", "inquiries:detail"),
        ("post", "inquiries:detail"),
        ("post", "inquiries:done"),
        ("get", "inquiries:followup"),
        ("post", "inquiries:followup"),
    ],
)
def test_foreign_inquiries_return_404(org, other_org, owner, login, make_inquiry, method, url_name):
    foreign = make_inquiry(other_org, "Fremde Anfrage")
    client = login(owner.user, org)
    assert getattr(client, method)(reverse(url_name, args=[foreign.pk])).status_code == 404


def test_lists_show_only_own_org(org, other_org, owner, login, make_inquiry):
    make_inquiry(other_org, "Fremde Anfrage")
    make_inquiry(other_org, "Fremd erledigt", done_at=timezone.now())
    client = login(owner.user, org)
    assert "Fremd" not in client.get(reverse("productions:list")).content.decode()
    assert "Fremd" not in client.get(reverse("inquiries:done_list")).content.decode()


def test_settings_show_only_own_link(org, other_org, owner, login):
    foreign = services.link_for(other_org)
    content = login(owner.user, org).get(reverse("inquiries:settings")).content.decode()
    assert foreign.token not in content


def test_export_and_audit_include_inquiries(org, other_org, evening, make_inquiry):
    import io
    import json
    import zipfile

    from apps.audit.models import AuditEntry
    from apps.organizations.export import export_organization

    make_inquiry(other_org, "Fremde Anfrage")
    archive = zipfile.ZipFile(io.BytesIO(export_organization(org)))
    rows = json.loads(archive.read("inquiries_inquiry.json"))
    assert [r["event_name"] for r in rows] == ["Elternabend"]
    assert AuditEntry.objects.filter(object_type="Technik-Anfrage", organization=org).exists()


# ---------- Dashboard-Kachel ----------


@pytest.mark.parametrize(
    ("role", "visible"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_dashboard_tile_per_role(org, owner, make_member, login, make_inquiry, role, visible):
    make_inquiry(org)
    client = login(_member(org, owner, make_member, role).user, org)

    response = client.get(reverse("productions:dashboard"))

    assert ("Technik-Anfragen offen" in response.content.decode()) is visible
    assert response.context["open_inquiry_count"] == (1 if visible else None)


def test_dashboard_tile_counts_only_open_inquiries_of_this_org(
    org, other_org, owner, login, make_inquiry
):
    make_inquiry(org)
    make_inquiry(org, done_at=timezone.now())
    make_inquiry(other_org)

    response = login(owner.user, org).get(reverse("productions:dashboard"))

    assert response.context["open_inquiry_count"] == 1


# ---------- Zähler in der Navigation ----------


@pytest.mark.parametrize(
    ("role", "visible"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_nav_badge_per_role(org, owner, make_member, login, make_inquiry, role, visible):
    make_inquiry(org)
    client = login(_member(org, owner, make_member, role).user, org)

    content = client.get(reverse("scheduling:calendar")).content.decode()

    assert ('aria-label="1 offene Technik-Anfragen"' in content) is visible
    # Seitenleiste und Handy-Leiste
    assert content.count("offene Technik-Anfragen") == (2 if visible else 0)


def test_nav_badge_counts_only_open_inquiries_of_this_org(
    org, other_org, owner, login, make_inquiry
):
    done = make_inquiry(org, done_at=timezone.now())
    make_inquiry(other_org)

    content = login(owner.user, org).get(reverse("scheduling:calendar")).content.decode()

    assert done.is_done
    assert "offene Technik-Anfragen" not in content


# ---------- Nachfrage nach dem Anlegen ----------


@pytest.fixture
def linked(org, evening, make_production):
    evening.production = make_production(org)
    evening.save()
    return evening


def test_followup_asks_and_yes_marks_done(linked, planner_client):
    url = reverse("inquiries:followup", args=[linked.pk])

    assert "Hat sich die Anfrage damit erledigt?" in planner_client.get(url).content.decode()
    response = planner_client.post(url)

    assert response.url == reverse("productions:detail", args=[linked.production_id])
    linked.refresh_from_db()
    assert linked.is_done


def test_followup_no_leaves_inquiry_open(linked, planner_client):
    url = reverse("inquiries:followup", args=[linked.pk])
    target = reverse("productions:detail", args=[linked.production_id])

    assert f'href="{target}"' in planner_client.get(url).content.decode()
    linked.refresh_from_db()
    assert not linked.is_done


def test_followup_without_production_goes_to_inquiry(evening, planner_client):
    response = planner_client.get(reverse("inquiries:followup", args=[evening.pk]))

    assert response.url == reverse("inquiries:detail", args=[evening.pk])


def test_followup_of_deleted_production_goes_to_inquiry(linked, planner_client):
    linked.production.deleted_at = timezone.now()
    linked.production.save()

    response = planner_client.post(reverse("inquiries:followup", args=[linked.pk]))

    assert response.url == reverse("inquiries:detail", args=[linked.pk])
    linked.refresh_from_db()
    assert not linked.is_done


def test_followup_when_already_done_goes_to_production(linked, planner_client, owner):
    services.mark_done(linked, owner.user)

    response = planner_client.get(reverse("inquiries:followup", args=[linked.pk]))

    assert response.url == reverse("productions:detail", args=[linked.production_id])


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, 200), (Role.ADMIN, 200), (Role.TEACHER, 200), (Role.STUDENT, 403)],
)
def test_followup_rights_per_role(org, owner, make_member, login, linked, role, expected):
    client = login(_member(org, owner, make_member, role).user, org)

    assert client.get(reverse("inquiries:followup", args=[linked.pk])).status_code == expected
