import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.google_sync import drive
from apps.google_sync.google_api import GoogleError
from apps.google_sync.services import connection_for
from apps.organizations.decorators import permission_required_in_org
from apps.organizations.permissions import Perm
from apps.productions import services as production_services
from apps.productions.forms import JobForm, JobFormSet, ProductionForm
from apps.productions.models import Job, Production

from . import services
from .forms import InquiryForm, InquiryLinkForm, TechOptionForm
from .models import Inquiry, TechOption

logger = logging.getLogger(__name__)

PRODUCTIONS = {"active_section": "productions"}
SETTINGS = {"active_section": "settings"}


# ---------- Öffentliches Formular (ohne Anmeldung) ----------


def _inactive(request):
    return render(request, "inquiries/public_inactive.html", status=404)


@login_not_required
def public_form(request, token):
    link = services.active_link(token)
    if link is None:
        return _inactive(request)
    organization = link.organization
    allow_pdf = connection_for(organization) is not None
    form = InquiryForm(
        request.POST or None, request.FILES or None, organization=organization, allow_pdf=allow_pdf
    )
    limited = request.method == "POST" and services.is_limited(link, request)
    if limited:
        form.is_valid()
        form.add_error(
            None,
            "Von hier kamen gerade sehr viele Anfragen. Bitte versuchen Sie es später noch einmal.",
        )
    elif request.method == "POST" and form.is_valid():
        if not form.is_spam:
            inquiry = form.save(commit=False)
            inquiry.organization = organization
            inquiry.save()
            pdf = form.cleaned_data.get("schedule_pdf")
            if pdf:
                try:
                    drive.upload(
                        organization,
                        pdf,
                        inquiry=inquiry,
                        max_mb=settings.GOOGLE_INQUIRY_PDF_MAX_MB,
                    )
                except GoogleError:
                    logger.warning("PDF zur Anfrage %s nicht hochgeladen", inquiry.pk)
        services.count_submission(link, request)
        return redirect("inquiries:public_thanks", token=token)
    return render(
        request, "inquiries/public_form.html", {"form": form, "organization": organization}
    )


@login_not_required
def public_thanks(request, token):
    link = services.active_link(token)
    if link is None:
        return _inactive(request)
    return render(
        request,
        "inquiries/public_thanks.html",
        {"organization": link.organization, "token": token},
    )


# ---------- Einstellungen: Link verwalten ----------


@permission_required_in_org(Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK)
def link_settings(request):
    link = services.link_for(request.organization)
    if request.method == "POST":
        form = InquiryLinkForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            if action == "renew":
                link.renew()
                messages.success(request, "Neuer Link erzeugt – der alte funktioniert nicht mehr.")
            else:
                link.is_active = action == "activate"
                link.save(update_fields=["is_active"])
                messages.success(
                    request, "Link ist aktiv." if link.is_active else "Link ist deaktiviert."
                )
        return redirect("inquiries:settings")
    url = request.build_absolute_uri(reverse("inquiries:public", args=[link.token]))
    return render(request, "inquiries/settings.html", {**SETTINGS, "link": link, "url": url})


# ---------- Einstellungen: Technik-Auswahl ----------


def _tech_option(request, pk):
    return get_object_or_404(TechOption.objects.for_org(request.organization), pk=pk)


@permission_required_in_org(Perm.MANAGE_TECH_OPTIONS)
def tech_options(request):
    items = TechOption.objects.for_org(request.organization)
    form = TechOptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.organization = request.organization
        item.position = items.count()
        item.save()
        messages.success(request, f"„{item.name}“ angelegt.")
        return redirect("inquiries:tech_options")
    return render(
        request, "inquiries/tech_options.html", {**SETTINGS, "items": items, "form": form}
    )


@permission_required_in_org(Perm.MANAGE_TECH_OPTIONS)
def tech_option_edit(request, pk):
    item = _tech_option(request, pk)
    form = TechOptionForm(request.POST or None, instance=item)
    back = reverse("inquiries:tech_options")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Gespeichert.")
        return redirect(back)
    return render(
        request,
        "productions/settings_item_form.html",
        {**SETTINGS, "form": form, "item": item, "back": back},
    )


@require_POST
@permission_required_in_org(Perm.MANAGE_TECH_OPTIONS)
def tech_option_delete(request, pk):
    item = _tech_option(request, pk)
    item.delete()
    messages.success(request, f"„{item.name}“ gelöscht.")
    return redirect("inquiries:tech_options")


@require_POST
@permission_required_in_org(Perm.MANAGE_TECH_OPTIONS)
def tech_option_move(request, pk):
    direction = -1 if request.POST.get("richtung") == "-1" else 1
    production_services.move(
        _tech_option(request, pk), direction, TechOption.objects.for_org(request.organization)
    )
    return redirect("inquiries:tech_options")


# ---------- Anfragen bearbeiten ----------


def _inquiry(request, pk):
    return get_object_or_404(
        Inquiry.objects.for_org(request.organization).select_related("category", "production"),
        pk=pk,
    )


@permission_required_in_org(Perm.HANDLE_INQUIRIES)
def inquiry_detail(request, pk):
    """Geteilte Ansicht: links die Anfrage, rechts „Neue Produktion“."""
    inquiry = _inquiry(request, pk)
    instance = Production(organization=request.organization)
    if request.method == "POST":
        form = ProductionForm(request.POST, instance=instance, organization=request.organization)
        formset = JobFormSet(
            request.POST,
            instance=instance,
            prefix="jobs",
            form_kwargs={"organization": request.organization},
        )
        if form.is_valid():
            formset.instance = form.instance
            if formset.is_valid():
                production = production_services.save_production(
                    request.organization, request.user, form, formset
                )
                inquiry.production = production
                inquiry.save(update_fields=["production"])
                messages.success(
                    request,
                    f"Produktion „{production.name}“ angelegt. "
                    "Die Anfrage bleibt in der Liste, bis du sie als erledigt markierst.",
                )
                return redirect("productions:detail", pk=production.pk)
        else:
            formset.is_valid()
    else:
        form = ProductionForm(
            instance=instance,
            organization=request.organization,
            initial=services.production_initial(inquiry),
        )
        jobs = services.suggested_jobs(inquiry)
        # Vorschläge als Startwerte; beim Absenden zählen sie wie selbst eingegebene Jobs
        formset_class = inlineformset_factory(
            Production, Job, form=JobForm, extra=max(len(jobs), 1), can_delete=True
        )
        formset = formset_class(
            instance=instance,
            prefix="jobs",
            initial=jobs,
            form_kwargs={"organization": request.organization},
        )
    return render(
        request,
        "inquiries/detail.html",
        {**PRODUCTIONS, "inquiry": inquiry, "form": form, "formset": formset},
    )


@require_POST
@permission_required_in_org(Perm.HANDLE_INQUIRIES)
def inquiry_done(request, pk):
    inquiry = _inquiry(request, pk)
    if inquiry.is_done:
        services.reopen(inquiry)
        messages.success(request, f"Anfrage „{inquiry.title}“ ist wieder offen.")
        return redirect("inquiries:detail", pk=pk)
    services.mark_done(inquiry, request.user)
    messages.success(request, f"Anfrage „{inquiry.title}“ erledigt.")
    return redirect("productions:list")


@permission_required_in_org(Perm.HANDLE_INQUIRIES)
def done_list(request):
    inquiries = (
        Inquiry.objects.for_org(request.organization)
        .done()
        .select_related("production", "done_by")
        .order_by("-done_at")
    )
    return render(
        request,
        "inquiries/done_list.html",
        {**PRODUCTIONS, "inquiries": inquiries, "keep_days": settings.INQUIRY_KEEP_DONE_DAYS},
    )
