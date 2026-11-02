from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.decorators import landing_for_anonymous
from apps.google_sync.services import connection_for
from apps.inquiries.models import Inquiry
from apps.inventory import services as inventory_services
from apps.organizations.decorators import org_required, permission_required_in_org
from apps.organizations.models import Membership
from apps.organizations.permissions import Perm
from apps.scheduling.models import EventAttendee
from apps.scheduling.services import find_conflicts

from . import hours, services
from .forms import (
    CategoryForm,
    CrewForm,
    HoursForm,
    JobForm,
    JobFormSet,
    MySkillsForm,
    ProductionForm,
    ProductionLinkForm,
    SkillForm,
    StatusChangeForm,
    StatusForm,
    TodoForm,
)
from .models import (
    Category,
    CrewAssignment,
    Job,
    Production,
    ProductionLink,
    ProductionStatus,
    Skill,
    Todo,
)

PRODUCTIONS = {"active_section": "productions"}
SETTINGS = {"active_section": "settings"}


# ---------- Abfragen (immer nach AG gefiltert) ----------


def _productions(request):
    return (
        Production.objects.for_org(request.organization)
        .select_related("category", "status")
        .annotate(job_count=Count("jobs", distinct=True))
    )


def _production(request, pk):
    return get_object_or_404(Production.objects.for_org(request.organization), pk=pk)


def _job(request, pk):
    return get_object_or_404(
        Job.objects.for_org(request.organization)
        .of_active_productions()
        .select_related("production"),
        pk=pk,
    )


def _assignment(request, pk):
    return get_object_or_404(
        CrewAssignment.objects.for_org(request.organization)
        .filter(job__production__deleted_at__isnull=True)
        .select_related("job", "job__production", "membership__user"),
        pk=pk,
    )


def _todo(request, pk):
    return get_object_or_404(
        Todo.objects.for_org(request.organization).filter(production__deleted_at__isnull=True),
        pk=pk,
    )


def _my_assignments(request, today):
    return (
        CrewAssignment.objects.for_org(request.organization)
        .filter(
            membership=request.membership,
            job__date__gte=today,
            job__production__deleted_at__isnull=True,
        )
        .select_related("job", "job__production", "job__production__category")
        .order_by("job__date", "job__start_time")
    )


# ---------- Dashboard ----------


@landing_for_anonymous
@org_required
def dashboard(request):
    today = timezone.localdate()
    upcoming = list(_productions(request).upcoming(today).prefetch_related("jobs"))
    my_assignments = list(_my_assignments(request, today))
    my_events = list(
        EventAttendee.objects.for_org(request.organization)
        .filter(membership=request.membership, event__date__gte=today)
        .select_related("event")
        .order_by("event__date", "event__start_time")
    )
    open_requests = [a for a in my_assignments if not a.is_confirmed] + [
        a for a in my_events if not a.is_confirmed and not a.event.cancelled
    ]

    next_production = upcoming[0] if upcoming else None
    next_job = next_production.next_job() if next_production else None
    view = "jobs" if request.GET.get("ansicht") == "jobs" else "productions"
    open_inquiry_count = None
    if request.membership.has_perm(Perm.HANDLE_INQUIRIES):
        open_inquiry_count = Inquiry.objects.for_org(request.organization).open().count()

    return render(
        request,
        "productions/dashboard.html",
        {
            "active_section": "dashboard",
            "today": today,
            "upcoming": upcoming,
            "next_production": next_production,
            "next_job": next_job,
            "my_assignments": my_assignments,
            "my_events": my_events,
            "open_request_count": len(open_requests),
            "open_inquiry_count": open_inquiry_count,
            "view": view,
        },
    )


# ---------- Produktionen ----------


@org_required
def production_list(request):
    today = timezone.localdate()
    productions = _productions(request)
    query = request.GET.get("q", "").strip()
    if query:
        productions = productions.filter(
            Q(name__icontains=query) | Q(location_name__icontains=query)
        )
    categories = Category.objects.for_org(request.organization)
    active_category = request.GET.get("kategorie", "")
    if active_category:
        productions = productions.filter(category_id=active_category)
    inquiries = None
    if request.membership.has_perm(Perm.HANDLE_INQUIRIES):
        inquiries = Inquiry.objects.for_org(request.organization).open()

    return render(
        request,
        "productions/list.html",
        {
            **PRODUCTIONS,
            "upcoming": productions.upcoming(today),
            "past": productions.past(today).order_by("-start_date"),
            "categories": categories,
            "active_category": active_category,
            "query": query,
            "inquiries": inquiries,
        },
    )


@org_required
def production_detail(request, pk):
    production = get_object_or_404(
        services.with_jobs_and_crew(Production.objects.for_org(request.organization)), pk=pk
    )
    supervisors = list(production.supervisors.all())
    return render(
        request,
        "productions/detail.html",
        {
            **PRODUCTIONS,
            "production": production,
            "status_form": StatusChangeForm(
                organization=request.organization, initial={"status": production.status_id}
            ),
            "todo_form": TodoForm(),
            "planned_material": inventory_services.production_material(production),
            "supervisors": supervisors,
            "is_supervisor": request.membership in supervisors,
            "links": production.links.all(),
            "attachments": production.attachments.select_related("uploaded_by"),
            "google_connected": connection_for(request.organization) is not None,
        },
    )


def _production_form(request, production=None):
    instance = production or Production(organization=request.organization)
    form = ProductionForm(
        request.POST or None, instance=instance, organization=request.organization
    )
    formset = JobFormSet(
        request.POST or None,
        instance=instance,
        prefix="jobs",
        form_kwargs={"organization": request.organization},
    )
    if request.method == "POST" and form.is_valid():
        # Jobs gegen die (neuen) Daten der Produktion prüfen
        formset.instance = form.instance
        if formset.is_valid():
            saved = services.save_production(request.organization, request.user, form, formset)
            messages.success(request, f"„{saved.name}“ gespeichert.")
            return redirect("productions:detail", pk=saved.pk)
    elif request.method == "POST":
        formset.is_valid()
    return render(
        request,
        "productions/form.html",
        {**PRODUCTIONS, "form": form, "formset": formset, "production": production},
    )


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_create(request):
    return _production_form(request)


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_edit(request, pk):
    return _production_form(request, _production(request, pk))


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_status(request, pk):
    production = _production(request, pk)
    form = StatusChangeForm(request.POST, organization=request.organization)
    if form.is_valid():
        production.status = form.cleaned_data["status"]
        production.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Status: {production.status}.")
    return redirect("productions:detail", pk=pk)


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_copy(request, pk):
    copy = services.copy_production(_production(request, pk), request.user)
    messages.success(request, "Kopie angelegt – bitte Name und Daten anpassen.")
    return redirect("productions:edit", pk=copy.pk)


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_delete(request, pk):
    production = _production(request, pk)
    if request.method == "POST":
        production.soft_delete()
        messages.success(
            request,
            f"„{production.name}“ gelöscht. Unter „Kürzlich gelöscht“ 7 Tage wiederherstellbar.",
        )
        return redirect("productions:list")
    return render(
        request, "productions/confirm_delete.html", {**PRODUCTIONS, "production": production}
    )


@require_POST
@permission_required_in_org(Perm.BE_SUPERVISOR)
def production_supervise(request, pk):
    production = _production(request, pk)
    if production.supervisors.filter(pk=request.membership.pk).exists():
        production.supervisors.remove(request.membership)
        messages.success(request, "Du bist nicht mehr als Aufsicht eingetragen.")
    else:
        production.supervisors.add(request.membership)
        messages.success(request, "Du bist als Aufsicht eingetragen.")
    return redirect("productions:detail", pk=pk)


# ---------- Kürzlich gelöscht ----------


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def trash(request):
    deleted = Production.all_objects.for_org(request.organization).deleted().order_by("-deleted_at")
    return render(request, "productions/trash.html", {**SETTINGS, "deleted": deleted})


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def production_restore(request, pk):
    production = get_object_or_404(
        Production.all_objects.for_org(request.organization).deleted(), pk=pk
    )
    production.restore()
    messages.success(request, f"„{production.name}“ wiederhergestellt.")
    return redirect("productions:detail", pk=pk)


# ---------- Jobs ----------


def _job_form(request, production, job=None):
    instance = job or Job(production=production, organization=request.organization)
    if job is None and request.method == "GET":
        instance.date = production.start_date
    form = JobForm(request.POST or None, instance=instance, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.production = production
        saved.organization = request.organization
        saved.save()
        messages.success(request, f"Job „{saved.name}“ gespeichert.")
        return redirect("productions:detail", pk=production.pk)
    return render(
        request,
        "productions/job_form.html",
        {**PRODUCTIONS, "form": form, "production": production, "job": job},
    )


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def job_create(request, pk):
    return _job_form(request, _production(request, pk))


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def job_edit(request, pk):
    job = _job(request, pk)
    return _job_form(request, job.production, job)


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def job_delete(request, pk):
    job = _job(request, pk)
    production_pk = job.production_id
    job.delete()
    messages.success(request, f"Job „{job.name}“ gelöscht.")
    return redirect("productions:detail", pk=production_pk)


# ---------- Crew ----------


@permission_required_in_org(Perm.MANAGE_CREW)
def job_crew(request, pk):
    job = _job(request, pk)
    skills = list(Skill.objects.for_org(request.organization))
    skill = next((s for s in skills if str(s.pk) == request.GET.get("faehigkeit")), None)
    initial = {"membership": request.GET.get("mitglied")} if request.GET.get("mitglied") else {}
    form = CrewForm(request.POST or None, job=job, skill=skill, initial=initial)
    conflicts = []
    if request.method == "POST" and form.is_valid():
        membership = form.cleaned_data["membership"]
        conflicts = find_conflicts(
            membership, job.start_datetime, job.end_datetime, exclude_job=job
        )
        if not conflicts or form.cleaned_data["ignore_conflicts"]:
            assignment = services.assign(
                job,
                membership,
                status=form.cleaned_data["status"],
                role_label=form.cleaned_data["role_label"],
                requested_by=request.user,
            )
            verb = "eingeteilt" if assignment.is_confirmed else "angefragt"
            messages.success(request, f"{membership.user} {verb}.")
            return redirect("productions:detail", pk=job.production_id)
        form = CrewForm({**request.POST.dict(), "ignore_conflicts": "on"}, job=job, skill=skill)
        form.is_valid()
    return render(
        request,
        "productions/crew_form.html",
        {
            **PRODUCTIONS,
            "form": form,
            "job": job,
            "conflicts": conflicts,
            "skills": skills,
            "skill": skill,
            "suggestions": services.suggest_crew(job, skill) if skill else [],
        },
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_CREW)
def crew_remove(request, pk):
    assignment = _assignment(request, pk)
    assignment.delete()
    messages.success(request, f"{assignment.person} entfernt.")
    return redirect("productions:detail", pk=assignment.job.production_id)


@require_POST
@permission_required_in_org(Perm.RESPOND_TO_REQUESTS)
def crew_respond(request, pk):
    assignment = _assignment(request, pk)
    if assignment.membership_id != request.membership.pk:
        raise PermissionDenied  # nur eigene Anfragen beantworten
    accept = request.POST.get("antwort") == "ja"
    services.respond(assignment, accept)
    job = assignment.job
    if accept:
        messages.success(request, f"Zugesagt: {job.production} – {job.name}.")
    else:
        messages.info(request, f"Abgelehnt: {job.production} – {job.name}.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("productions:dashboard") + "?ansicht=jobs"
    return redirect(next_url)


# ---------- To-dos (alle Mitglieder dürfen anlegen, abhaken und löschen) ----------


@require_POST
@org_required
def todo_create(request, pk):
    production = _production(request, pk)
    form = TodoForm(request.POST)
    if form.is_valid():
        todo = form.save(commit=False)
        todo.production = production
        todo.organization = request.organization
        todo.position = production.todos.count()
        todo.save()
    return redirect(reverse("productions:detail", args=[pk]) + "#todos")


@require_POST
@org_required
def todo_toggle(request, pk):
    todo = _todo(request, pk)
    services.set_todo_done(todo, not todo.done, request.user)
    return redirect(reverse("productions:detail", args=[todo.production_id]) + "#todos")


@require_POST
@org_required
def todo_delete(request, pk):
    todo = _todo(request, pk)
    todo.delete()
    return redirect(reverse("productions:detail", args=[todo.production_id]) + "#todos")


# ---------- Kategorien und Status-Werte (Einstellungen) ----------


def _direction(request):
    return -1 if request.POST.get("richtung") == "-1" else 1


def _ordered_settings(request, model, form_class, template, title, perm_label):
    items = model.objects.for_org(request.organization)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = request.organization
        item.position = items.count()
        item.save()
        messages.success(request, f"„{item.name}“ angelegt.")
        return redirect(request.path)
    return render(
        request,
        template,
        {**SETTINGS, "items": items, "form": form, "title": title, "kind": perm_label},
    )


def _edit_item(request, item, form_class, back):
    form = form_class(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect(back)
    return render(
        request,
        "productions/settings_item_form.html",
        {**SETTINGS, "form": form, "item": item, "back": back},
    )


@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def categories(request):
    return _ordered_settings(
        request,
        Category,
        CategoryForm,
        "productions/settings_list.html",
        "Kategorien",
        "categories",
    )


def _category(request, pk):
    return get_object_or_404(Category.objects.for_org(request.organization), pk=pk)


@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_edit(request, pk):
    return _edit_item(
        request, _category(request, pk), CategoryForm, reverse("productions:categories")
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_delete(request, pk):
    category = _category(request, pk)
    category.delete()
    messages.success(request, f"Kategorie „{category.name}“ gelöscht.")
    return redirect("productions:categories")


@require_POST
@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def category_move(request, pk):
    services.move(
        _category(request, pk), _direction(request), Category.objects.for_org(request.organization)
    )
    return redirect("productions:categories")


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def statuses(request):
    return _ordered_settings(
        request,
        ProductionStatus,
        StatusForm,
        "productions/settings_list.html",
        "Status-Werte",
        "statuses",
    )


def _status(request, pk):
    return get_object_or_404(ProductionStatus.objects.for_org(request.organization), pk=pk)


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def status_edit(request, pk):
    return _edit_item(request, _status(request, pk), StatusForm, reverse("productions:statuses"))


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def status_delete(request, pk):
    status = _status(request, pk)
    if status.is_system:
        messages.error(request, "„In Planung“ und „Bestätigt“ können nicht gelöscht werden.")
    else:
        services.delete_status(status)
        messages.success(request, f"Status „{status.name}“ gelöscht.")
    return redirect("productions:statuses")


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def status_move(request, pk):
    services.move(
        _status(request, pk),
        _direction(request),
        ProductionStatus.objects.for_org(request.organization),
    )
    return redirect("productions:statuses")


# ---------- Links im Abschnitt „Dateien“ (Dateien selbst: apps/google_sync) ----------


@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def link_create(request, pk):
    production = _production(request, pk)
    form = ProductionLinkForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        link = form.save(commit=False)
        link.organization = request.organization
        link.production = production
        link.save()
        messages.success(request, "Link hinzugefügt.")
        return redirect(reverse("productions:detail", args=[pk]) + "#dateien")
    return render(
        request,
        "productions/link_form.html",
        {**PRODUCTIONS, "form": form, "production": production},
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_PRODUCTIONS)
def link_delete(request, pk):
    link = get_object_or_404(
        ProductionLink.objects.for_org(request.organization).filter(
            production__deleted_at__isnull=True
        ),
        pk=pk,
    )
    link.delete()
    messages.success(request, "Link entfernt.")
    return redirect(reverse("productions:detail", args=[link.production_id]) + "#dateien")


# ---------- Fähigkeiten ----------


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def skills(request):
    return _ordered_settings(
        request, Skill, SkillForm, "productions/skills.html", "Fähigkeiten", "skills"
    )


def _skill(request, pk):
    return get_object_or_404(Skill.objects.for_org(request.organization), pk=pk)


@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def skill_edit(request, pk):
    return _edit_item(request, _skill(request, pk), SkillForm, reverse("productions:skills"))


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def skill_delete(request, pk):
    skill = _skill(request, pk)
    skill.delete()
    messages.success(request, f"Fähigkeit „{skill.name}“ gelöscht.")
    return redirect("productions:skills")


@require_POST
@permission_required_in_org(Perm.MANAGE_ORG_CONFIG)
def skill_move(request, pk):
    services.move(
        _skill(request, pk), _direction(request), Skill.objects.for_org(request.organization)
    )
    return redirect("productions:skills")


@org_required
def my_skills(request):
    form = MySkillsForm(
        request.POST or None,
        organization=request.organization,
        initial={"skills": request.membership.skills.all()},
    )
    if request.method == "POST" and form.is_valid():
        request.membership.skills.set(form.cleaned_data["skills"])
        messages.success(request, "Gespeichert.")
        return redirect("productions:my_skills")
    return render(request, "productions/my_skills.html", {**SETTINGS, "form": form})


# ---------- Einsatzübersicht ----------


def hours_membership(request, pk):
    """Mitglied für die Einsatzübersicht: eigene immer, andere nur mit Recht (sonst 403)."""
    membership = get_object_or_404(
        Membership.objects.for_org(request.organization).select_related("user"), pk=pk
    )
    if membership != request.membership and not request.membership.has_perm(
        Perm.VIEW_ALL_ASSIGNMENTS
    ):
        raise PermissionDenied
    return membership


def hours_context(request, membership):
    """Gemeinsam für Seite und PDF (apps/documents)."""
    period = hours.period_from_request(request.GET)
    items = hours.entries(membership, period.start, period.end)
    return {
        "member": membership,
        "period": period,
        "periods": hours.periods(),
        "entries": items,
        "total": hours.total(items),
        "any_corrected": any(e.is_corrected for e in items),
    }


@org_required
def hours_overview(request):
    if not request.membership.has_perm(Perm.VIEW_ALL_ASSIGNMENTS):
        return redirect("productions:hours_member", pk=request.membership.pk)
    period = hours.period_from_request(request.GET)
    memberships = Membership.objects.for_org(request.organization).select_related("user")
    return render(
        request,
        "productions/hours_overview.html",
        {
            **SETTINGS,
            "period": period,
            "periods": hours.periods(),
            "rows": hours.summary(request.organization, memberships, period.start, period.end),
        },
    )


@org_required
def hours_member(request, pk):
    membership = hours_membership(request, pk)
    return render(
        request,
        "productions/hours_member.html",
        {**SETTINGS, **hours_context(request, membership)},
    )


def _correct_hours(request, obj, title, back):
    form = HoursForm(request.POST or None, initial={"corrected_hours": obj.corrected_hours})
    if request.method == "POST" and form.is_valid():
        obj.corrected_hours = form.cleaned_data["corrected_hours"]
        obj.save(update_fields=["corrected_hours"])
        messages.success(request, "Stunden gespeichert.")
        return redirect(back)
    return render(
        request,
        "productions/hours_form.html",
        {**SETTINGS, "form": form, "title": title, "person": obj.person, "back": back},
    )


def _back_to_member(request, obj):
    url = reverse("productions:hours_member", args=[obj.membership_id])
    next_url = request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return url


@permission_required_in_org(Perm.CORRECT_HOURS)
def hours_correct_job(request, pk):
    assignment = get_object_or_404(
        CrewAssignment.objects.for_org(request.organization)
        .filter(membership__isnull=False, job__production__deleted_at__isnull=True)
        .select_related("job", "job__production", "membership__user"),
        pk=pk,
    )
    title = f"{assignment.job.production} – {assignment.job.name}"
    return _correct_hours(request, assignment, title, _back_to_member(request, assignment))


@permission_required_in_org(Perm.CORRECT_HOURS)
def hours_correct_event(request, pk):
    attendee = get_object_or_404(
        EventAttendee.objects.for_org(request.organization)
        .filter(membership__isnull=False)
        .select_related("event", "membership__user"),
        pk=pk,
    )
    return _correct_hours(
        request, attendee, attendee.event.title, _back_to_member(request, attendee)
    )
