from datetime import date, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.permissions import Perm

from . import ics, services
from .calendar import calendar_entries, month_grid, without_covered_productions
from .forms import AttendeeForm, EventEditScopeForm, EventForm, PeriodFormSet, UnavailabilityForm
from .models import Event, EventAttendee, SchoolPeriod, Unavailability
from .periods import DEFAULT_PERIODS

CALENDAR = {"active_section": "calendar"}
SETTINGS = {"active_section": "settings"}
MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
MAX_PER_CELL = 3
AGENDA_DAYS = 60


def _parse_date(value, default):
    try:
        return date.fromisoformat(value) if value else default
    except ValueError:
        return default


def _add_months(day, months):
    month = day.month - 1 + months
    return date(day.year + month // 12, month % 12 + 1, 1)


# ---------- Kalender ----------


def _google_subscribe_url(organization):
    from apps.google_sync.services import connection_for, subscribe_url

    return subscribe_url(connection_for(organization))


@org_required
def calendar_view(request):
    today = timezone.localdate()
    view = request.GET.get("ansicht", "monat")
    if view not in ("monat", "woche", "agenda"):
        view = "monat"
    anchor = _parse_date(request.GET.get("datum"), today)
    mine = request.GET.get("filter") == "meine"
    membership = request.membership if mine else None

    if view == "monat":
        weeks = month_grid(anchor.year, anchor.month)
        start, end = weeks[0][0], weeks[-1][-1]
        prev_anchor, next_anchor = _add_months(anchor, -1), _add_months(anchor, 1)
        title = f"{MONTHS[anchor.month - 1]} {anchor.year}"
    elif view == "woche":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        weeks = [[start + timedelta(days=i) for i in range(7)]]
        prev_anchor, next_anchor = start - timedelta(days=7), start + timedelta(days=7)
        title = f"{start:%d.%m.} – {end:%d.%m.%Y}"
    else:
        start, end = anchor, anchor + timedelta(days=AGENDA_DAYS - 1)
        weeks = []
        prev_anchor = anchor - timedelta(days=AGENDA_DAYS)
        next_anchor = anchor + timedelta(days=AGENDA_DAYS)
        title = f"ab {anchor:%d.%m.%Y}"

    entries = calendar_entries(request.organization, start, end, membership)
    selected = _parse_date(request.GET.get("tag"), today if start <= today <= end else start)

    def link(**changes):
        params = {"ansicht": view, "datum": anchor.isoformat()}
        if mine:
            params["filter"] = "meine"
        params.update(changes)
        return "?" + urlencode({k: v for k, v in params.items() if v})

    limit = MAX_PER_CELL if view == "monat" else None

    def entries_on(day):
        return without_covered_productions([e for e in entries if e.on(day)])

    def day_info(day):
        items = entries_on(day)
        return {
            "date": day,
            "url": link(datum=anchor.isoformat(), tag=day.isoformat()),
            "entries": items[:limit],
            "overflow": max(0, len(items) - limit) if limit else 0,
            "all": items,
            "in_month": view != "monat" or day.month == anchor.month,
            "is_today": day == today,
            "is_selected": day == selected,
        }

    grid = [[day_info(d) for d in week] for week in weeks]
    agenda = []
    if view == "agenda":
        day = start
        while day <= end:
            items = entries_on(day)
            if items:
                agenda.append({"date": day, "all": items, "is_today": day == today})
            day += timedelta(days=1)

    return render(
        request,
        "scheduling/calendar.html",
        {
            **CALENDAR,
            "view": view,
            "mine": mine,
            "title": title,
            "anchor": anchor,
            "today": today,
            "prev_anchor": prev_anchor,
            "next_anchor": next_anchor,
            "grid": grid,
            "agenda": agenda,
            "selected": selected,
            "selected_entries": entries_on(selected),
            "weekdays": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
            "google_subscribe_url": _google_subscribe_url(request.organization),
            "links": {
                "prev": link(datum=prev_anchor.isoformat()),
                "next": link(datum=next_anchor.isoformat()),
                "today": link(datum=today.isoformat(), tag=today.isoformat()),
                "month": link(ansicht="monat"),
                "week": link(ansicht="woche"),
                "agenda": link(ansicht="agenda"),
                "all": link(filter=""),
                "mine": link(filter="meine"),
            },
            "new_event_url": f"{reverse('scheduling:event_create')}?datum={selected.isoformat()}",
        },
    )


# ---------- Termine ----------


def _event(request, pk):
    return get_object_or_404(
        Event.objects.for_org(request.organization).select_related("series"), pk=pk
    )


@permission_required_in_org(Perm.CREATE_EVENTS)
def event_create(request):
    initial = {"date": _parse_date(request.GET.get("datum"), timezone.localdate())}
    form = EventForm(request.POST or None, initial=initial, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        event = services.create_event(
            request.organization,
            form.cleaned_data,
            frequency=form.cleaned_data.get("repeat", ""),
            until=form.cleaned_data.get("until"),
            user=request.user,
        )
        if event.series_id:
            count = event.series.events.count()
            messages.success(request, f"Serie „{event.title}“ mit {count} Terminen angelegt.")
        else:
            messages.success(request, f"Termin „{event.title}“ angelegt.")
        return redirect("scheduling:event_detail", pk=event.pk)
    return render(request, "scheduling/event_form.html", {**CALENDAR, "form": form})


@org_required
def event_detail(request, pk):
    event = _event(request, pk)
    attendees = list(event.attendees.select_related("membership__user"))
    return render(
        request,
        "scheduling/event_detail.html",
        {
            **CALENDAR,
            "event": event,
            "attendees": attendees,
            "my_attendance": next(
                (a for a in attendees if a.membership_id == request.membership.pk), None
            ),
            "series_count": event.series.events.count() if event.series_id else 0,
        },
    )


@permission_required_in_org(Perm.CREATE_EVENTS)
def event_edit(request, pk):
    event = _event(request, pk)
    form = EventForm(
        request.POST or None,
        instance=event,
        organization=request.organization,
        allow_repeat=False,
    )
    scope_form = EventEditScopeForm(request.POST or None) if event.series_id else None
    if (
        request.method == "POST"
        and form.is_valid()
        and (scope_form is None or scope_form.is_valid())
    ):
        scope = scope_form.cleaned_data["scope"] if scope_form else "single"
        # form.is_valid() hat die Instanz schon geändert – Originaldatum für die Serie zurückholen
        original = Event.objects.get(pk=event.pk)
        services.update_event(original, form.cleaned_data, scope=scope)
        messages.success(
            request,
            "Termin gespeichert."
            if scope == "single"
            else "Dieser und alle folgenden Termine gespeichert.",
        )
        return redirect("scheduling:event_detail", pk=event.pk)
    return render(
        request,
        "scheduling/event_form.html",
        {**CALENDAR, "form": form, "scope_form": scope_form, "event": event},
    )


@require_POST
@permission_required_in_org(Perm.CREATE_EVENTS)
def event_cancel(request, pk):
    event = _event(request, pk)
    services.set_cancelled(event, not event.cancelled)
    messages.success(request, "Termin abgesagt." if event.cancelled else "Absage zurückgenommen.")
    return redirect("scheduling:event_detail", pk=pk)


@permission_required_in_org(Perm.CREATE_EVENTS)
def event_delete(request, pk):
    event = _event(request, pk)
    if request.method == "POST":
        scope = "following" if request.POST.get("scope") == "following" else "single"
        day = event.date
        services.delete_event(event, scope=scope)
        messages.success(
            request,
            "Termin gelöscht."
            if scope == "single"
            else "Dieser und alle folgenden Termine gelöscht.",
        )
        return redirect(f"{reverse('scheduling:calendar')}?datum={day:%Y-%m-%d}&tag={day:%Y-%m-%d}")
    return render(request, "scheduling/event_delete.html", {**CALENDAR, "event": event})


@permission_required_in_org(Perm.CREATE_EVENTS)
def event_attendees(request, pk):
    from .services import find_conflicts

    event = _event(request, pk)
    form = AttendeeForm(request.POST or None, event=event)
    conflicts = []
    if request.method == "POST" and form.is_valid():
        membership = form.cleaned_data["membership"]
        conflicts = find_conflicts(
            membership, event.start_datetime, event.end_datetime, exclude_event=event
        )
        if not conflicts or form.cleaned_data["ignore_conflicts"]:
            attendee = services.assign_attendee(event, membership, form.cleaned_data["status"])
            verb = "eingeteilt" if attendee.is_confirmed else "angefragt"
            messages.success(request, f"{membership.user} {verb}.")
            return redirect("scheduling:event_detail", pk=pk)
        form = AttendeeForm({**request.POST.dict(), "ignore_conflicts": "on"}, event=event)
        form.is_valid()
    return render(
        request,
        "scheduling/attendee_form.html",
        {**CALENDAR, "form": form, "event": event, "conflicts": conflicts},
    )


def _attendee(request, pk):
    return get_object_or_404(
        EventAttendee.objects.for_org(request.organization).select_related(
            "event", "membership__user"
        ),
        pk=pk,
    )


@require_POST
@permission_required_in_org(Perm.CREATE_EVENTS)
def attendee_remove(request, pk):
    attendee = _attendee(request, pk)
    attendee.delete()
    messages.success(request, f"{attendee.person} entfernt.")
    return redirect("scheduling:event_detail", pk=attendee.event_id)


@require_POST
@permission_required_in_org(Perm.RESPOND_TO_REQUESTS)
def attendee_respond(request, pk):
    attendee = _attendee(request, pk)
    if attendee.membership_id != request.membership.pk:
        raise PermissionDenied
    if request.POST.get("antwort") == "ja":
        attendee.status = EventAttendee.Status.CONFIRMED
        attendee.save(update_fields=["status"])
        messages.success(request, f"Zugesagt: {attendee.event.title}.")
    else:
        attendee.delete()
        messages.info(request, f"Abgelehnt: {attendee.event.title}.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("scheduling:event_detail", args=[attendee.event_id])
    return redirect(next_url)


# ---------- Nicht verfügbar ----------


def _own_unavailability(request, pk):
    entry = get_object_or_404(Unavailability.objects.for_org(request.organization), pk=pk)
    if entry.membership_id != request.membership.pk:
        raise PermissionDenied  # nur eigene Einträge bearbeiten
    return entry


@permission_required_in_org(Perm.OWN_UNAVAILABILITY)
def unavailability_list(request):
    entries = Unavailability.objects.for_org(request.organization).filter(
        membership=request.membership, end_date__gte=timezone.localdate() - timedelta(days=30)
    )
    return render(request, "scheduling/unavailability_list.html", {**SETTINGS, "entries": entries})


def _unavailability_form(request, entry=None):
    today = timezone.localdate()
    instance = entry or Unavailability(
        organization=request.organization, membership=request.membership
    )
    initial = {} if entry else {"start_date": today, "end_date": today}
    form = UnavailabilityForm(
        request.POST or None,
        instance=instance,
        initial=initial,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.organization = request.organization
        saved.membership = request.membership
        saved.save()
        messages.success(request, "„Nicht verfügbar“ gespeichert.")
        return redirect("scheduling:unavailability_list")
    return render(
        request, "scheduling/unavailability_form.html", {**SETTINGS, "form": form, "entry": entry}
    )


@permission_required_in_org(Perm.OWN_UNAVAILABILITY)
def unavailability_create(request):
    return _unavailability_form(request)


@permission_required_in_org(Perm.OWN_UNAVAILABILITY)
def unavailability_edit(request, pk):
    return _unavailability_form(request, _own_unavailability(request, pk))


@require_POST
@permission_required_in_org(Perm.OWN_UNAVAILABILITY)
def unavailability_delete(request, pk):
    _own_unavailability(request, pk).delete()
    messages.success(request, "Eintrag gelöscht.")
    return redirect("scheduling:unavailability_list")


# ---------- Stundenraster ----------


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def periods(request):
    queryset = SchoolPeriod.objects.for_org(request.organization)
    initial = []
    if not queryset.exists() and request.method != "POST":
        # Vorschlag nur beim Anzeigen – beim Speichern zählen alle ausgefüllten Zeilen als neu
        initial = [{"number": n, "start_time": s, "end_time": e} for n, s, e in DEFAULT_PERIODS]
    formset = PeriodFormSet(request.POST or None, queryset=queryset, initial=initial)
    if initial:
        formset.extra = len(initial)  # Vorschlag als vorausgefüllte Zeilen
    if request.method == "POST" and formset.is_valid():
        with transaction.atomic():
            for item in formset.save(commit=False):
                item.organization = request.organization
                item.save()
            for obj in formset.deleted_objects:
                if obj.pk:
                    obj.delete()
        messages.success(request, "Stundenraster gespeichert.")
        return redirect("scheduling:periods")
    return render(
        request,
        "scheduling/periods.html",
        {**SETTINGS, "formset": formset, "is_suggestion": not queryset.exists()},
    )


# ---------- ICS-Export ----------


def _ics_response(request, name, events):
    response = HttpResponse(ics.build_calendar(events), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{slugify(name) or "termin"}.ics"'
    return response


def _uid(request, kind, pk):
    return f"{kind}-{pk}@{request.get_host().split(':')[0]}"


@org_required
def ics_production(request, pk):
    from apps.productions.models import Production

    p = get_object_or_404(Production.objects.for_org(request.organization), pk=pk)
    start, end = ics.all_day(p.start_date, p.end_date)
    lines = [
        f"{j.date:%d.%m.} {j.start_time:%H:%M}–{j.end_time:%H:%M} {j.name}" for j in p.jobs.all()
    ]
    event = ics.IcsEvent(
        uid=_uid(request, "production", p.pk),
        summary=p.name,
        start=start,
        end=end,
        location=", ".join(x for x in [p.location_name, p.address] if x),
        description="\n".join([f"Status: {p.status}", *lines, p.notes]).strip(),
        url=request.build_absolute_uri(reverse("productions:detail", args=[p.pk])),
    )
    return _ics_response(request, p.name, [event])


@org_required
def ics_job(request, pk):
    from apps.productions.models import Job

    j = get_object_or_404(
        Job.objects.for_org(request.organization)
        .of_active_productions()
        .select_related("production"),
        pk=pk,
    )
    crew = ", ".join(a.person for a in j.crew.select_related("membership__user"))
    event = ics.IcsEvent(
        uid=_uid(request, "job", j.pk),
        summary=f"{j.production} – {j.name}",
        start=j.start_datetime,
        end=j.end_datetime,
        location=j.production.location_name or j.production.address,
        description="\n".join(
            x
            for x in [
                f"Treffpunkt: {j.meeting_point}" if j.meeting_point else "",
                f"Crew: {crew}" if crew else "",
            ]
            if x
        ),
        url=request.build_absolute_uri(reverse("productions:detail", args=[j.production_id])),
    )
    return _ics_response(request, f"{j.production}-{j.name}", [event])


@org_required
def ics_event(request, pk):
    e = _event(request, pk)
    if e.all_day:
        start, end = ics.all_day(e.date, e.date)
    else:
        start, end = e.start_datetime, e.end_datetime
    event = ics.IcsEvent(
        uid=_uid(request, "event", e.pk),
        summary=e.title + (" (abgesagt)" if e.cancelled else ""),
        start=start,
        end=end,
        location=e.location,
        description=e.notes,
        url=request.build_absolute_uri(reverse("scheduling:event_detail", args=[e.pk])),
    )
    return _ics_response(request, e.title, [event])


@org_required
def ics_unavailability(request, pk):
    u = _own_unavailability(request, pk)
    if u.all_day:
        start, end = ics.all_day(u.start_date, u.end_date)
    else:
        start, end = u.start_datetime, u.end_datetime
    event = ics.IcsEvent(
        uid=_uid(request, "unavailable", u.pk),
        summary="Nicht verfügbar",
        start=start,
        end=end,
        description=u.note,
    )
    return _ics_response(request, "nicht-verfuegbar", [event])
