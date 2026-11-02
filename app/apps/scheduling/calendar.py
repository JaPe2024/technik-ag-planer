"""Einheitliche Kalendereinträge aus Produktionen, Jobs, Terminen und „Nicht verfügbar“.

Gemeinsame Quelle für die Kalenderansichten und später die Google-Kalender-Übertragung (M10).
"""

from dataclasses import dataclass
from datetime import date, time, timedelta

from django.urls import reverse

from .models import Event, Unavailability


@dataclass
class Entry:
    kind: str  # "production", "job", "event", "unavailable"
    pk: int
    title: str
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    color: str = ""  # Palette-Schlüssel; leer = Akzent
    url: str = ""
    ics_url: str = ""
    suffix: str = ""  # z. B. „(In Planung)“, „(abgesagt)“
    cancelled: bool = False
    location: str = ""
    detail: str = ""  # Zusatz für die Tagesliste, z. B. Zeitraum über mehrere Tage
    production_id: int | None = None  # nur bei Jobs

    @property
    def all_day(self):
        return self.start_time is None

    @property
    def is_multi_day(self):
        return self.start_date != self.end_date

    def on(self, day):
        return self.start_date <= day <= self.end_date

    @property
    def label(self):
        prefix = f"{self.start_time:%H:%M} " if self.start_time else ""
        return f"{prefix}{self.title}{' ' + self.suffix if self.suffix else ''}"

    @property
    def sort_key(self):
        order = {"production": 0, "unavailable": 1, "event": 2, "job": 2}
        return (
            self.start_date,
            self.start_time is not None,
            self.start_time or time.min,
            order[self.kind],
            self.title,
        )


def calendar_entries(organization, start: date, end: date, membership=None):
    """Alle Einträge, die den Zeitraum [start, end] berühren.
    Mit `membership` nur die eigenen („Meine“)."""
    from apps.productions.models import Job, Production

    entries = []

    productions = (
        Production.objects.for_org(organization)
        .filter(start_date__lte=end, end_date__gte=start)
        .select_related("category", "status")
    )
    jobs = (
        Job.objects.for_org(organization)
        .of_active_productions()
        .filter(date__range=(start, end))
        .select_related("production", "production__category", "production__status")
    )
    if membership is not None:
        productions = productions.filter(jobs__crew__membership=membership).distinct()
        jobs = jobs.filter(crew__membership=membership)

    for p in productions:
        entries.append(
            Entry(
                kind="production",
                pk=p.pk,
                title=p.name,
                start_date=p.start_date,
                end_date=p.end_date,
                color=p.category.color if p.category else "grey",
                url=reverse("productions:detail", args=[p.pk]),
                ics_url=reverse("scheduling:ics_production", args=[p.pk]),
                suffix="(In Planung)" if p.status.is_planning else "",
                location=p.location_name,
            )
        )
    for j in jobs:
        p = j.production
        entries.append(
            Entry(
                kind="job",
                pk=j.pk,
                title=f"{p.name} – {j.name}",
                start_date=j.date,
                end_date=j.date,
                start_time=j.start_time,
                end_time=j.end_time,
                color=p.category.color if p.category else "grey",
                url=reverse("productions:detail", args=[p.pk]),
                ics_url=reverse("scheduling:ics_job", args=[j.pk]),
                suffix="(In Planung)" if p.status.is_planning else "",
                location=j.meeting_point or p.location_name,
                production_id=p.pk,
            )
        )

    events = Event.objects.for_org(organization).filter(date__range=(start, end))
    if membership is not None:
        events = events.filter(attendees__membership=membership)
    for e in events:
        entries.append(
            Entry(
                kind="event",
                pk=e.pk,
                title=e.title,
                start_date=e.date,
                end_date=e.date,
                start_time=e.start_time,
                end_time=e.end_time,
                url=reverse("scheduling:event_detail", args=[e.pk]),
                ics_url=reverse("scheduling:ics_event", args=[e.pk]),
                suffix="(abgesagt)" if e.cancelled else "",
                cancelled=e.cancelled,
                location=e.location,
            )
        )

    absences = (
        Unavailability.objects.for_org(organization)
        .filter(start_date__lte=end, end_date__gte=start)
        .select_related("membership__user")
    )
    if membership is not None:
        absences = absences.filter(membership=membership)
    for u in absences:
        multi = u.start_date != u.end_date
        entries.append(
            Entry(
                kind="unavailable",
                pk=u.pk,
                title=f"Nicht verfügbar: {u.membership.user}",
                start_date=u.start_date,
                end_date=u.end_date,
                # mehrtägig: Balken über die Tage, der genaue Zeitraum steht im Zusatz
                start_time=u.start_time if not multi else None,
                end_time=u.end_time if not multi else None,
                color="grey",
                detail=_absence_detail(u) if multi else "",
            )
        )

    entries.sort(key=lambda e: e.sort_key)
    return entries


def without_covered_productions(items):
    """Einträge eines Tages ohne den Produktions-Eintrag, wenn ihre Jobs schon dastehen."""
    with_jobs = {e.production_id for e in items if e.kind == "job"}
    return [e for e in items if not (e.kind == "production" and e.pk in with_jobs)]


def _absence_detail(u):
    start = f"{u.start_date:%d.%m.}" + (f" {u.start_time:%H:%M}" if u.start_time else "")
    end = f"{u.end_date:%d.%m.}" + (f" {u.end_time:%H:%M}" if u.end_time else "")
    return f"{start} – {end}"


def month_grid(year, month):
    """Wochen (Mo–So) eines Monats als Liste von Listen mit Datumswerten."""
    first = date(year, month, 1)
    start = first - timedelta(days=first.weekday())
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    end = next_month - timedelta(days=1)
    end = end + timedelta(days=6 - end.weekday())
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return [days[i : i + 7] for i in range(0, len(days), 7)]
