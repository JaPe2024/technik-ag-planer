from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.forms import AcceptInvitationForm, LoginForm
from apps.accounts.models import Grade
from apps.google_sync.services import connection_for
from apps.inquiries.models import InquiryLink

from . import services
from .decorators import org_required, owner_required, permission_required_in_org
from .forms import (
    DissolveForm,
    InviteForm,
    Require2FAForm,
    RoleForm,
    SchoolYearForm,
    TransferOwnershipForm,
)
from .middleware import set_active_organization
from .models import Invitation, Membership
from .permissions import Perm, Role
from .settings_menu import visible_groups

SETTINGS = {"active_section": "settings"}


def _error(request, error: ValidationError):
    for message in error.messages:
        messages.error(request, message)


def no_organization(request):
    if request.organization is not None:
        return redirect("productions:dashboard")
    return render(request, "organizations/no_organization.html", {"admin_url": settings.ADMIN_URL})


@require_POST
def switch_organization(request):
    membership = next(
        (m for m in request.memberships if str(m.organization_id) == request.POST.get("org")),
        None,
    )
    if membership is None:
        messages.error(request, "Du bist kein Mitglied dieser AG.")
    else:
        set_active_organization(request, membership.organization)
        messages.success(request, f"Gewechselt zu {membership.organization.name}.")
    return redirect("productions:dashboard")


@org_required
def settings_index(request):
    google_connected = connection_for(request.organization) is not None
    return render(
        request,
        "organizations/settings.html",
        {
            **SETTINGS,
            "groups": visible_groups(request.membership),
            "inquiry_link_active": InquiryLink.objects.filter(
                organization=request.organization, is_active=True
            ).exists(),
            "google_connected": google_connected,
            # Ohne Google-Projekt der Installation könnte der Owner nichts verbinden
            "show_google_hint": request.membership.is_owner
            and not google_connected
            and bool(settings.GOOGLE_OAUTH_CLIENT_ID),
        },
    )


@org_required
def members(request):
    org = request.organization
    memberships = (
        Membership.objects.for_org(org)
        .select_related("user")
        .prefetch_related("skills")
        .order_by("user__display_name")
    )
    context = {**SETTINGS, "memberships": memberships, "role_form": RoleForm()}
    if request.membership.has_perm(Perm.INVITE_MEMBERS):
        context["invite_form"] = InviteForm()
        context["invitations"] = Invitation.objects.for_org(org).open().select_related("invited_by")
    return render(request, "organizations/members.html", context)


@require_POST
@permission_required_in_org(Perm.INVITE_MEMBERS)
def invite(request):
    form = InviteForm(request.POST)
    if form.is_valid():
        try:
            services.invite(
                request.organization,
                form.cleaned_data["email"],
                form.cleaned_data["role"],
                invited_by=request.user,
            )
        except ValidationError as error:
            _error(request, error)
        else:
            messages.success(request, f"Einladung an {form.cleaned_data['email']} verschickt.")
    else:
        messages.error(request, "Bitte eine gültige E-Mail-Adresse und Rolle angeben.")
    return redirect("organizations:members")


def _invitation(request, pk):
    return get_object_or_404(Invitation.objects.for_org(request.organization), pk=pk)


def _membership(request, pk):
    return get_object_or_404(
        Membership.objects.for_org(request.organization).select_related("user"), pk=pk
    )


@require_POST
@permission_required_in_org(Perm.INVITE_MEMBERS)
def invitation_resend(request, pk):
    invitation = _invitation(request, pk)
    try:
        services.resend(invitation)
    except ValidationError as error:
        _error(request, error)
    else:
        messages.success(request, f"Einladung an {invitation.email} erneut verschickt.")
    return redirect("organizations:members")


@require_POST
@permission_required_in_org(Perm.INVITE_MEMBERS)
def invitation_revoke(request, pk):
    invitation = _invitation(request, pk)
    services.revoke(invitation)
    messages.success(request, f"Einladung an {invitation.email} zurückgezogen.")
    return redirect("organizations:members")


@require_POST
@permission_required_in_org(Perm.INVITE_MEMBERS)
def member_role(request, pk):
    membership = _membership(request, pk)
    form = RoleForm(request.POST)
    if form.is_valid():
        try:
            services.change_role(membership, form.cleaned_data["role"])
        except ValidationError as error:
            _error(request, error)
        else:
            messages.success(
                request, f"{membership.user} ist jetzt {membership.get_role_display()}."
            )
    return redirect("organizations:members")


@require_POST
@permission_required_in_org(Perm.INVITE_MEMBERS)
def member_remove(request, pk):
    membership = _membership(request, pk)
    try:
        services.remove_member(membership)
    except ValidationError as error:
        _error(request, error)
    else:
        messages.success(request, f"{membership.user} wurde aus der AG entfernt.")
    return redirect("organizations:members")


@org_required
def manage(request):
    context = {**SETTINGS}
    if request.membership.is_owner:
        context["transfer_form"] = TransferOwnershipForm(
            organization=request.organization, current=request.membership
        )
        context["dissolve_form"] = DissolveForm()
    context["member_count"] = Membership.objects.for_org(request.organization).count()
    return render(request, "organizations/manage.html", context)


@require_POST
@owner_required
def transfer_ownership(request):
    form = TransferOwnershipForm(
        request.POST, organization=request.organization, current=request.membership
    )
    if form.is_valid():
        new_owner = form.cleaned_data["membership"]
        services.make_owner(new_owner)
        messages.success(request, f"{new_owner.user} ist jetzt Owner. Du bist jetzt Admin.")
    else:
        messages.error(request, "Bitte ein Mitglied auswählen.")
    return redirect("organizations:manage")


@require_POST
@org_required
def leave(request):
    name = request.organization.name
    try:
        services.leave(request.membership)
    except ValidationError as error:
        _error(request, error)
        return redirect("organizations:manage")
    messages.success(request, f"Du hast die {name} verlassen.")
    return redirect("productions:dashboard")


@require_POST
@permission_required_in_org(Perm.MANAGE_2FA_AND_DISSOLVE)
def dissolve(request):
    form = DissolveForm(request.POST)
    if form.is_valid():
        name = request.organization.name
        try:
            services.dissolve(request.organization, form.cleaned_data["confirm_name"])
        except ValidationError as error:
            _error(request, error)
        else:
            messages.success(request, f"Die {name} wurde aufgelöst.")
            return redirect("productions:dashboard")
    return redirect("organizations:manage")


@permission_required_in_org(Perm.MANAGE_2FA_AND_DISSOLVE)
def require_2fa(request):
    org = request.organization
    form = Require2FAForm(request.POST or None, initial={"require_2fa": org.require_2fa})
    if request.method == "POST" and form.is_valid():
        org.require_2fa = form.cleaned_data["require_2fa"]
        org.save(update_fields=["require_2fa"])
        if org.require_2fa:
            messages.success(
                request,
                "Zwei-Faktor ist jetzt Pflicht. Mitglieder ohne Authenticator-App werden "
                "beim nächsten Aufruf zur Einrichtung geleitet.",
            )
        else:
            messages.success(request, "Zwei-Faktor ist jetzt freiwillig je Person.")
        return redirect("organizations:require_2fa")
    without_2fa = (
        Membership.objects.for_org(org)
        .annotate(devices=Count("user__totpdevice"))
        .filter(devices=0)
        .count()
    )
    return render(
        request,
        "organizations/require_2fa.html",
        {**SETTINGS, "form": form, "without_2fa": without_2fa},
    )


@login_not_required
def accept_invitation(request, token):
    invitation, error = services.find_open_invitation(token)
    if invitation is None:
        return render(
            request, "organizations/invitation_invalid.html", {"error": error}, status=410
        )

    from django.contrib.auth import get_user_model

    User = get_user_model()
    existing = User.objects.filter(email__iexact=invitation.email).first()
    context = {"invitation": invitation, "organization": invitation.organization}

    # Bestehendes Konto (z. B. Mitglied einer anderen AG): anmelden und beitreten
    if existing is not None:
        if request.user.is_authenticated and request.user != existing:
            context["wrong_account"] = True
            return render(request, "organizations/invitation_existing.html", context)
        if request.user.is_authenticated:
            if request.method == "POST":
                try:
                    services.accept(invitation, request.user)
                except ValidationError as err:
                    _error(request, err)
                    return redirect("productions:dashboard")
                set_active_organization(request, invitation.organization)
                messages.success(request, f"Willkommen in der {invitation.organization.name}!")
                return redirect("productions:dashboard")
            return render(request, "organizations/invitation_existing.html", context)
        context["login_form"] = LoginForm(initial={"email": existing.email})
        return render(request, "organizations/invitation_existing.html", context)

    if request.user.is_authenticated:
        logout(request)

    needs_grade = invitation.role != Role.TEACHER
    form = AcceptInvitationForm(
        request.POST or None, email=invitation.email, needs_grade=needs_grade
    )
    if request.method == "POST" and form.is_valid():
        try:
            user = services.create_account_and_accept(
                invitation,
                display_name=form.cleaned_data["display_name"],
                password=form.cleaned_data["password1"],
                grade=form.cleaned_data.get("grade", ""),
            )
        except ValidationError as err:
            form.add_error(None, err)
        else:
            from django.contrib.auth import login

            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            set_active_organization(request, invitation.organization)
            messages.success(request, f"Willkommen in der {invitation.organization.name}!")
            return redirect("productions:dashboard")
    context["form"] = form
    return render(request, "organizations/invitation_accept.html", context)


@permission_required_in_org(Perm.TRIGGER_SCHOOL_YEAR_CHANGE)
def school_year(request):
    form = SchoolYearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            count = services.change_school_year(request.organization)
        except ValidationError as error:
            _error(request, error)
        else:
            messages.success(
                request, f"Schuljahreswechsel erledigt: {count} Jahrgangsstufen erhöht."
            )
        return redirect("organizations:school_year")
    changes, skipped, locked_until = services.school_year_preview(request.organization)
    return render(
        request,
        "organizations/school_year.html",
        {
            **SETTINGS,
            "form": form,
            "changes": sorted(changes.items(), key=lambda item: _grade_index(item[0][0])),
            "skipped": skipped,
            "locked_until": locked_until,
        },
    )


def _grade_index(grade):
    values = [value for value, _label in Grade.choices]
    return values.index(grade) if grade in values else len(values)
