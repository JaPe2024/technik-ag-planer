from datetime import date, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.organizations.permissions import Role
from apps.productions.models import CrewAssignment
from apps.scheduling.calendar import calendar_entries, month_grid, without_covered_productions
from apps.scheduling.models import Event, EventAttendee, Unavailability


def _unavailable(org, membership, day, start=None, end=None, end_day=None):
    return Unavailability.objects.create(
        organization=org,
        membership=membership,
        start_date=day,
        end_date=end_day or day,
        start_time=start,
        end_time=end,
    )


def test_month_grid_starts_monday():
    weeks = month_grid(2026, 10)
    assert weeks[0][0] == date(2026, 9, 28) and weeks[0][0].weekday() == 0
    assert weeks[-1][-1].weekday() == 6
    assert all(len(w) == 7 for w in weeks)


def test_entries_cover_productions_jobs_events_absences(org, student, make_production, make_job):
    production = make_production(org, "Abiball", days_ahead=2, length=2)
    make_job(production, "Aufbau")
    Event.objects.create(
        organization=org,
        title="AG-Treffen",
        date=production.start_date,
        start_time=time(14),
        end_time=time(15),
    )
    _unavailable(org, student, production.start_date)

    entries = calendar_entries(org, production.start_date, production.end_date)
    labels = [e.label for e in entries]

    assert "Abiball (In Planung)" in labels
    assert "14:00 Abiball – Aufbau (In Planung)" in labels
    assert "14:00 AG-Treffen" in labels
    assert "Nicht verfügbar: Emma" in labels
    abiball = next(e for e in entries if e.kind == "production")
    assert abiball.on(production.end_date)  # mehrtägig


def test_mine_filter(org, student, make_member, make_production, make_job, make_assignment):
    production = make_production(org)
    mine = make_job(production, "Aufbau")
    make_job(production, "Show", start=time(18), end=time(20))
    make_assignment(mine, student)
    other = make_member(org, Role.STUDENT, display_name="Ben")
    _unavailable(org, other, production.start_date)

    entries = calendar_entries(org, production.start_date, production.end_date, student)
    titles = {e.title for e in entries}
    assert titles == {"Schulkonzert", "Schulkonzert – Aufbau"}


def test_calendar_month_week_agenda(org, member_client, concert):
    day = concert.start_date
    for view in ["monat", "woche", "agenda"]:
        response = member_client.get(
            reverse("scheduling:calendar"), {"ansicht": view, "datum": day.isoformat()}
        )
        assert response.status_code == 200
        assert "Schulkonzert" in response.content.decode()

    detail = member_client.get(
        reverse("scheduling:calendar"), {"datum": day.isoformat(), "tag": day.isoformat()}
    )
    assert [e.kind for e in detail.context["selected_entries"]] == ["job", "job"]
    empty_day = day + timedelta(days=1)
    empty = member_client.get(
        reverse("scheduling:calendar"), {"tag": empty_day.isoformat(), "datum": day.isoformat()}
    )
    assert "Keine Termine an diesem Tag" in empty.content.decode()


def test_calendar_today_highlight_and_overflow(org, member_client):
    today = timezone.localdate()
    for i in range(5):
        Event.objects.create(organization=org, title=f"Termin {i}", date=today)
    content = member_client.get(reverse("scheduling:calendar")).content.decode()
    assert "cal__day--today" in content
    assert "+2" in content


def test_create_event_and_series_via_view(org, planner_client):
    day = timezone.localdate() + timedelta(days=1)
    planner_client.post(
        reverse("scheduling:event_create"),
        {
            "title": "AG-Treffen",
            "date": day.isoformat(),
            "start_time": "14:00",
            "end_time": "15:00",
            "location": "",
            "notes": "",
            "repeat": "weekly",
            "until": (day + timedelta(weeks=3)).isoformat(),
        },
    )
    assert Event.objects.for_org(org).count() == 4

    planner_client.post(
        reverse("scheduling:event_create"),
        {
            "title": "Probe",
            "date": day.isoformat(),
            "start_time": "",
            "end_time": "",
            "repeat": "",
        },
    )
    assert Event.objects.for_org(org).get(title="Probe").all_day


def test_series_requires_until(org, planner_client):
    response = planner_client.post(
        reverse("scheduling:event_create"),
        {
            "title": "AG-Treffen",
            "date": timezone.localdate().isoformat(),
            "repeat": "weekly",
        },
    )
    assert response.status_code == 200
    assert not Event.objects.exists()


def test_edit_following_via_view(org, planner_client):
    day = timezone.localdate() + timedelta(days=1)
    planner_client.post(
        reverse("scheduling:event_create"),
        {
            "title": "AG-Treffen",
            "date": day.isoformat(),
            "start_time": "14:00",
            "end_time": "15:00",
            "repeat": "weekly",
            "until": (day + timedelta(weeks=2)).isoformat(),
        },
    )
    second = Event.objects.order_by("date")[1]
    planner_client.post(
        reverse("scheduling:event_edit", args=[second.pk]),
        {
            "title": "AG-Treffen neu",
            "date": second.date.isoformat(),
            "start_time": "15:00",
            "end_time": "16:00",
            "scope": "following",
        },
    )
    assert [e.title for e in Event.objects.order_by("date")] == [
        "AG-Treffen",
        "AG-Treffen neu",
        "AG-Treffen neu",
    ]


def test_students_cannot_create_events(student_client):
    assert student_client.get(reverse("scheduling:event_create")).status_code == 403


def test_attendee_request_and_respond(org, planner_client, student, student_client):
    event = Event.objects.create(
        organization=org,
        title="AG-Treffen",
        date=timezone.localdate() + timedelta(days=2),
        start_time=time(14),
        end_time=time(15),
    )
    planner_client.post(
        reverse("scheduling:event_attendees", args=[event.pk]),
        {"membership": student.pk, "status": "requested"},
    )
    attendee = EventAttendee.objects.get()
    dashboard = student_client.get(reverse("productions:dashboard"))
    assert dashboard.context["open_request_count"] == 1

    student_client.post(
        reverse("scheduling:attendee_respond", args=[attendee.pk]), {"antwort": "ja"}
    )
    attendee.refresh_from_db()
    assert attendee.is_confirmed


def test_crew_warns_about_unavailability(org, planner_client, student, concert):
    job = concert.jobs.get(name="Aufbau")  # 14–16 Uhr
    _unavailable(org, student, job.date, time(13, 0), time(15, 0))

    response = planner_client.post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": student.pk, "status": "confirmed"},
    )
    content = response.content.decode()
    assert "Überschneidung" in content and "Nicht verfügbar" in content
    assert not CrewAssignment.objects.exists()


@pytest.mark.parametrize("kind", ["all_day", "multi_day"])
def test_crew_warns_about_all_day_and_multi_day_absence(
    org, planner_client, student, concert, kind
):
    job = concert.jobs.get(name="Show")
    if kind == "all_day":
        _unavailable(org, student, job.date)
    else:
        _unavailable(
            org,
            student,
            job.date - timedelta(days=1),
            time(8),
            time(10),
            end_day=job.date + timedelta(days=1),
        )
    response = planner_client.post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": student.pk, "status": "confirmed"},
    )
    assert "Nicht verfügbar" in response.content.decode()


def test_no_warning_outside_absence(org, planner_client, student, concert):
    job = concert.jobs.get(name="Aufbau")  # 14–16 Uhr
    _unavailable(org, student, job.date, time(8), time(13, 10))
    planner_client.post(
        reverse("productions:job_crew", args=[job.pk]),
        {"membership": student.pk, "status": "confirmed"},
    )
    assert CrewAssignment.objects.exists()


def test_event_assignment_warns_about_job(org, planner_client, student, concert, make_assignment):
    job = concert.jobs.get(name="Aufbau")
    make_assignment(job, student, status="confirmed")
    event = Event.objects.create(
        organization=org, title="Besprechung", date=job.date, start_time=time(15), end_time=time(17)
    )
    response = planner_client.post(
        reverse("scheduling:event_attendees", args=[event.pk]),
        {"membership": student.pk, "status": "confirmed"},
    )
    assert "Schulkonzert – Aufbau" in response.content.decode()
    assert not EventAttendee.objects.exists()


def test_unavailability_own_entries(org, student, student_client, make_member):
    day = timezone.localdate() + timedelta(days=3)
    student_client.post(
        reverse("scheduling:unavailability_create"),
        {
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "start_time": "08:00",
            "end_time": "13:00",
            "note": "Klausur",
        },
    )
    entry = Unavailability.objects.get()
    assert entry.membership == student

    other = make_member(org, Role.STUDENT)
    foreign = _unavailable(org, other, day)
    assert (
        student_client.get(reverse("scheduling:unavailability_edit", args=[foreign.pk])).status_code
        == 403
    )
    assert (
        student_client.post(
            reverse("scheduling:unavailability_delete", args=[foreign.pk])
        ).status_code
        == 403
    )
    assert (
        student_client.get(reverse("scheduling:ics_unavailability", args=[foreign.pk])).status_code
        == 403
    )
    list_content = student_client.get(reverse("scheduling:unavailability_list")).content.decode()
    assert "Klausur" in list_content


def test_unavailability_end_before_start(student_client):
    day = timezone.localdate()
    student_client.post(
        reverse("scheduling:unavailability_create"),
        {
            "start_date": day.isoformat(),
            "end_date": (day - timedelta(days=1)).isoformat(),
        },
    )
    assert not Unavailability.objects.exists()


def test_new_menu_links_event_and_unavailability(planner_client, student_client):
    planner = planner_client.get(reverse("productions:dashboard")).content.decode()
    assert reverse("scheduling:event_create") in planner
    student = student_client.get(reverse("productions:dashboard")).content.decode()
    assert reverse("scheduling:unavailability_create") in student
    assert reverse("scheduling:event_create") not in student.split('id="sheet-new"', 1)[1]


# ---------- Produktion nur einmal je Tag ----------


def _cell(response, day):
    cells = [d for week in response.context["grid"] for d in week]
    return next(d for d in cells if d["date"] == day)


@pytest.mark.parametrize("view", ["monat", "woche", "agenda"])
def test_views_list_jobs_without_production_entry(org, member_client, concert, view):
    day = concert.start_date
    response = member_client.get(
        reverse("scheduling:calendar"), {"ansicht": view, "datum": day.isoformat()}
    )

    if view != "agenda":
        items = _cell(response, day)["entries"]
    else:
        items = next(d for d in response.context["agenda"] if d["date"] == day)["all"]
    assert [e.title for e in items] == ["Schulkonzert – Aufbau", "Schulkonzert – Show"]


def test_multi_day_production_stays_on_days_without_job(org, make_production, make_job):
    production = make_production(org, length=2)
    start = production.start_date
    make_job(production, "Aufbau")
    entries = calendar_entries(org, start, start + timedelta(days=1))

    on_job_day = [e for e in entries if e.on(start)]
    next_day = [e for e in entries if e.on(start + timedelta(days=1))]

    assert [e.kind for e in without_covered_productions(on_job_day)] == ["job"]
    assert [e.kind for e in without_covered_productions(next_day)] == ["production"]
    assert without_covered_productions(next_day)[0].title == production.name


def test_mine_filter_keeps_only_own_jobs(org, student, make_production, make_job, make_assignment):
    production = make_production(org)
    make_job(production, "Aufbau")
    show = make_job(production, "Show", start=time(18), end=time(20))
    make_assignment(show, student)
    day = production.start_date

    items = without_covered_productions(calendar_entries(org, day, day, student))

    assert [e.title for e in items] == [f"{production.name} – Show"]


def test_overflow_counts_visible_entries(org, member_client, concert):
    day = concert.start_date
    for i in range(3):
        Event.objects.create(organization=org, title=f"Termin {i}", date=day)

    response = member_client.get(
        reverse("scheduling:calendar"), {"ansicht": "monat", "datum": day.isoformat()}
    )

    assert _cell(response, day)["overflow"] == 2  # 2 Jobs + 3 Termine, davon 3 sichtbar


def test_crew_switch_keeps_real_radio_fields(org, planner_client, concert):
    job = concert.jobs.get(name="Aufbau")

    content = planner_client.get(reverse("productions:job_crew", args=[job.pk])).content.decode()

    assert "segmented--choice" in content
    assert content.count('type="radio" name="status"') == 2
    requested = content.split('name="status" value="requested"', 1)[1].split(">", 1)[0]
    assert "checked" in requested
