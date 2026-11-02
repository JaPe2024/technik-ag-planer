"""Mandantentrennung für Kalender, Termine, „Nicht verfügbar“, Stundenraster und ICS."""

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.organizations.permissions import Role
from apps.scheduling.models import Event, EventAttendee, EventSeries, SchoolPeriod, Unavailability


@pytest.fixture
def foreign(other_org, make_member, make_production, make_job):
    day = timezone.localdate() + timedelta(days=2)
    member = make_member(other_org, Role.STUDENT, display_name="Sam Süd")
    series = EventSeries.objects.create(organization=other_org, frequency="weekly", until=day)
    event = Event.objects.create(
        organization=other_org,
        title="Fremdes Treffen",
        date=day,
        series=series,
        start_time=time(14),
        end_time=time(15),
    )
    attendee = EventAttendee.objects.create(organization=other_org, event=event, membership=member)
    absence = Unavailability.objects.create(
        organization=other_org, membership=member, start_date=day, end_date=day
    )
    production = make_production(other_org, "Fremdes Konzert", days_ahead=2)
    job = make_job(production)
    SchoolPeriod.objects.create(
        organization=other_org, number=1, start_time=time(8), end_time=time(8, 45)
    )
    return {
        "event": event,
        "attendee": attendee,
        "absence": absence,
        "production": production,
        "job": job,
        "member": member,
        "day": day,
    }


URLS = [
    ("get", "scheduling:event_detail", "event"),
    ("get", "scheduling:event_edit", "event"),
    ("post", "scheduling:event_cancel", "event"),
    ("post", "scheduling:event_delete", "event"),
    ("get", "scheduling:event_attendees", "event"),
    ("post", "scheduling:attendee_remove", "attendee"),
    ("post", "scheduling:attendee_respond", "attendee"),
    ("get", "scheduling:unavailability_edit", "absence"),
    ("post", "scheduling:unavailability_delete", "absence"),
    ("get", "scheduling:ics_event", "event"),
    ("get", "scheduling:ics_unavailability", "absence"),
    ("get", "scheduling:ics_production", "production"),
    ("get", "scheduling:ics_job", "job"),
    ("get", "scheduling:private_calendar_event", "event"),
    ("get", "scheduling:private_calendar_unavailability", "absence"),
    ("get", "scheduling:private_calendar_production", "production"),
    ("get", "scheduling:private_calendar_job", "job"),
]


@pytest.mark.parametrize(("method", "url_name", "target"), URLS)
def test_foreign_objects_return_404(org, owner, login, foreign, method, url_name, target):
    client = login(owner.user, org)
    response = getattr(client, method)(reverse(url_name, args=[foreign[target].pk]))
    assert response.status_code == 404


def test_calendar_never_shows_other_org(org, owner, login, foreign):
    client = login(owner.user, org)
    for view in ["monat", "woche", "agenda"]:
        content = client.get(
            reverse("scheduling:calendar"), {"ansicht": view, "datum": foreign["day"].isoformat()}
        ).content.decode()
        assert "Fremdes Treffen" not in content
        assert "Sam Süd" not in content
        assert "Fremdes Konzert" not in content


def test_period_grid_and_choices_only_own_org(org, owner, login, foreign, make_production):
    client = login(owner.user, org)
    response = client.get(reverse("scheduling:periods"))
    assert response.context["is_suggestion"]  # fremdes Raster zählt nicht

    production = make_production(org)
    form = client.get(reverse("productions:job_create", args=[production.pk])).context["form"]
    assert "start_period" not in form.fields  # kein eigenes Raster → keine Stunden-Auswahl


def test_cannot_invite_member_of_other_org(org, owner, login, foreign):
    event = Event.objects.create(organization=org, title="Eigenes Treffen", date=foreign["day"])
    login(owner.user, org).post(
        reverse("scheduling:event_attendees", args=[event.pk]),
        {"membership": foreign["member"].pk, "status": "confirmed"},
    )
    assert not EventAttendee.objects.filter(event=event).exists()


def test_export_contains_scheduling_only_for_own_org(org, foreign, member_client):
    import io
    import json
    import zipfile

    from apps.organizations.export import export_organization

    Event.objects.create(organization=org, title="Eigenes Treffen", date=foreign["day"])
    archive = zipfile.ZipFile(io.BytesIO(export_organization(org)))
    events = json.loads(archive.read("scheduling_event.json"))
    assert [e["title"] for e in events] == ["Eigenes Treffen"]
