"""„In privaten Kalender“: Auswahl, Google-Link und Datei."""

from datetime import date, datetime, time
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from apps.organizations.permissions import Role
from apps.scheduling import ics
from apps.scheduling.models import Event, Unavailability

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1"
IPAD = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/18.0 Safari/605.1.15"
ANDROID = "Mozilla/5.0 (Linux; Android 15) Chrome/130.0 Mobile Safari/537.36"


def _query(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}", parse_qs(parts.query)


def _option(response, label):
    return next(o for o in response.context["options"] if o["label"] == label)


@pytest.fixture
def job(concert, make_assignment, student):
    job = concert.jobs.get(name="Aufbau")
    make_assignment(job, student)
    return job


# ---------- Google-Link ----------


def test_google_url_with_times_and_encoding():
    berlin = ZoneInfo("Europe/Berlin")
    event = ics.IcsEvent(
        uid="x",
        summary="Konzert & Probe",
        start=datetime(2027, 1, 2, 8, tzinfo=berlin),
        end=datetime(2027, 1, 2, 16, tzinfo=berlin),
        location="Aula, Haus A",
        description="Zeile 1\nZeile 2",
        url="https://planer.example/p/1/",
    )

    base, query = _query(ics.google_url(event))

    assert base == "https://calendar.google.com/calendar/render"
    assert query["action"] == ["TEMPLATE"]
    assert query["text"] == ["Konzert & Probe"]
    assert query["dates"] == ["20270102T070000Z/20270102T150000Z"]
    assert query["location"] == ["Aula, Haus A"]
    assert query["details"] == ["Zeile 1\nZeile 2\n\nhttps://planer.example/p/1/"]
    assert query["ctz"] == ["Europe/Berlin"]


def test_google_url_all_day_has_exclusive_end():
    start, end = ics.all_day(date(2027, 1, 2), date(2027, 1, 3))
    event = ics.IcsEvent(uid="x", summary="Fest", start=start, end=end)

    _base, query = _query(ics.google_url(event))

    assert query["dates"] == ["20270102/20270104"]
    assert "location" not in query and "details" not in query


def test_google_url_leaves_out_internal_and_shortens_long_text():
    event = ics.IcsEvent(
        uid="x",
        summary="Job",
        start=date(2027, 1, 2),
        end=date(2027, 1, 3),
        description="x" * 5000,
        internal="Crew: Emma Schulz",
    )

    url = ics.google_url(event)

    assert "Emma" not in url
    assert len(_query(url)[1]["details"][0]) == ics.GOOGLE_DETAILS_MAX + 1
    assert "Crew: Emma Schulz" in ics.build_calendar([event])


# ---------- Auswahl ----------


@pytest.mark.parametrize(
    ("agent", "first"),
    [
        (IPHONE, "Apple Kalender"),
        (IPAD, "Apple Kalender"),
        (ANDROID, "Google Kalender"),
        ("", "Google Kalender"),
    ],
)
def test_order_follows_device(member_client, concert, agent, first):
    response = member_client.get(
        reverse("scheduling:private_calendar_production", args=[concert.pk]),
        headers={"user-agent": agent},
    )

    assert response.context["options"][0]["label"] == first
    assert "User-Agent" in response["Vary"]


def test_sheet_offers_all_ways(member_client, concert):
    url = reverse("scheduling:private_calendar_production", args=[concert.pk])
    file_url = reverse("scheduling:ics_production", args=[concert.pk])

    response = member_client.get(url)
    content = response.content.decode()

    assert _option(response, "Apple Kalender")["href"] == f"{file_url}?oeffnen=1"
    assert f'href="{file_url}"' in content
    assert 'target="_blank" rel="noopener noreferrer"' in content
    assert "Datei herunterladen" in content


def test_sheet_request_returns_fragment(member_client, concert):
    response = member_client.get(
        reverse("scheduling:private_calendar_production", args=[concert.pk]),
        headers={"x-sheet": "1"},
    )

    content = response.content.decode()
    assert "Google Kalender" in content
    assert "<html" not in content


def test_production_is_one_entry_with_job_lines(member_client, concert):
    response = member_client.get(
        reverse("scheduling:private_calendar_production", args=[concert.pk])
    )

    _base, query = _query(_option(response, "Google Kalender")["href"])
    assert query["text"] == ["Schulkonzert"]
    assert "Aufbau" in query["details"][0] and "Show" in query["details"][0]
    day = concert.start_date
    assert query["dates"] == [f"{day:%Y%m%d}/{ics.all_day(day, day)[1]:%Y%m%d}"]


def test_job_google_link_has_no_member_names_but_file_has(member_client, job, student):
    response = member_client.get(reverse("scheduling:private_calendar_job", args=[job.pk]))

    href = _option(response, "Google Kalender")["href"]
    assert str(student.user) not in _query(href)[1].get("details", [""])[0]
    assert "Crew" not in href

    content = member_client.get(reverse("scheduling:ics_job", args=[job.pk])).content.decode()
    assert "Crew:" in content


def test_unavailability_link_has_no_name(org, student, student_client):
    entry = Unavailability.objects.create(
        organization=org, membership=student, start_date=date(2027, 1, 2), end_date=date(2027, 1, 2)
    )

    response = student_client.get(
        reverse("scheduling:private_calendar_unavailability", args=[entry.pk])
    )

    _base, query = _query(_option(response, "Google Kalender")["href"])
    assert query["text"] == ["Nicht verfügbar"]
    assert str(student.user) not in _option(response, "Google Kalender")["href"]


# ---------- Datei ----------


def test_file_is_attachment_by_default_and_inline_for_apple(member_client, concert):
    url = reverse("scheduling:ics_production", args=[concert.pk])

    assert member_client.get(url)["Content-Disposition"].startswith("attachment;")
    opened = member_client.get(url, {"oeffnen": "1"})
    assert opened["Content-Disposition"].startswith("inline;")
    assert opened["Content-Type"].startswith("text/calendar")


# ---------- Rechte und Knöpfe ----------


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_every_member_may_open_sheets(org, make_member, login, job, role):
    client = login(make_member(org, role).user, org)
    event = Event.objects.create(organization=org, title="Treffen", date=date(2027, 1, 2))

    for name, pk in [
        ("private_calendar_production", job.production_id),
        ("private_calendar_job", job.pk),
        ("private_calendar_event", event.pk),
    ]:
        assert client.get(reverse(f"scheduling:{name}", args=[pk])).status_code == 200


def test_owner_may_open_sheet(org, owner, login, concert):
    client = login(owner.user, org)

    url = reverse("scheduling:private_calendar_production", args=[concert.pk])
    assert client.get(url).status_code == 200


def test_buttons_open_sheet_everywhere(org, student, student_client, concert):
    job = concert.jobs.get(name="Aufbau")
    day = concert.start_date
    event = Event.objects.create(organization=org, title="Treffen", date=day, start_time=time(14))
    Unavailability.objects.create(
        organization=org, membership=student, start_date=day, end_date=day
    )
    pages = {
        reverse("productions:detail", args=[concert.pk]): [
            reverse("scheduling:private_calendar_production", args=[concert.pk]),
            reverse("scheduling:private_calendar_job", args=[job.pk]),
        ],
        reverse("scheduling:event_detail", args=[event.pk]): [
            reverse("scheduling:private_calendar_event", args=[event.pk]),
        ],
        reverse("scheduling:calendar") + f"?datum={day}&tag={day}": [
            reverse("scheduling:private_calendar_job", args=[job.pk]),
        ],
    }
    for page, targets in pages.items():
        content = student_client.get(page).content.decode()
        assert "In privaten Kalender" in content, page
        assert ".ics" not in content and "In Kalender übernehmen" not in content, page
        for target in targets:
            assert f'href="{target}" data-sheet-url' in content, target
