"""Einzelne Einträge für den privaten Kalender: iCalendar-Datei (RFC 5545) und Google-Link."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

GOOGLE_URL = "https://calendar.google.com/calendar/render"
GOOGLE_DETAILS_MAX = 1000  # lange Texte würden den Link sprengen


@dataclass
class IcsEvent:
    uid: str
    summary: str
    start: datetime | date
    end: datetime | date  # bei ganztägig: Tag NACH dem letzten Tag (exklusiv)
    location: str = ""
    description: str = ""
    url: str = ""
    internal: str = ""  # nur für die Datei, nie im Google-Link (z. B. Namen der Crew)

    @property
    def file_description(self):
        return "\n".join(x for x in [self.description, self.internal] if x)


def _escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    """Zeilen auf 75 Bytes umbrechen (Folgezeilen beginnen mit einem Leerzeichen)."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode()
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode())
            current = b""
        current += encoded
    parts.append(current.decode())
    return "\r\n ".join(parts)


def _stamp(value):
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return value.strftime("%Y%m%d")


def _dt(value):
    return (":" if isinstance(value, datetime) else ";VALUE=DATE:") + _stamp(value)


def build_calendar(events):
    stamp = timezone.now().astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Technik-AG Planer//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for ev in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev.uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART{_dt(ev.start)}",
            f"DTEND{_dt(ev.end)}",
            f"SUMMARY:{_escape(ev.summary)}",
        ]
        if ev.location:
            lines.append(f"LOCATION:{_escape(ev.location)}")
        if ev.file_description:
            lines.append(f"DESCRIPTION:{_escape(ev.file_description)}")
        if ev.url:
            lines.append(f"URL:{ev.url}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def google_url(event):
    """Link, der den Eintrag bei Google zum Speichern vorausfüllt – ohne `internal`."""
    text = event.description
    if len(text) > GOOGLE_DETAILS_MAX:
        text = text[:GOOGLE_DETAILS_MAX].rstrip() + "…"
    details = "\n\n".join(x for x in [text, event.url] if x)
    params = {
        "action": "TEMPLATE",
        "text": event.summary,
        "dates": f"{_stamp(event.start)}/{_stamp(event.end)}",
        "ctz": settings.TIME_ZONE,
    }
    if event.location:
        params["location"] = event.location
    if details:
        params["details"] = details
    return f"{GOOGLE_URL}?{urlencode(params)}"


def all_day(start_date, end_date):
    """Ganztägig von start_date bis einschließlich end_date."""
    return start_date, end_date + timedelta(days=1)
