"""Einladungen, Beitritt und Owner-Regeln (Abschnitt 2)."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import Invitation, Membership, Organization, hash_token
from .permissions import Role

OPERATOR_NOT_ALLOWED = (
    "Betreiber-Konten können keiner AG beitreten. Bitte eine andere E-Mail-Adresse verwenden."
)


def is_operator_email(email):
    """Gehört die Adresse zu einem Betreiber-Konto (ADR 0017)?"""
    return (
        get_user_model()
        .objects.filter(email__iexact=email)
        .filter(Q(is_staff=True) | Q(is_superuser=True))
        .exists()
    )


def invitation_url(token):
    return settings.SITE_URL.rstrip("/") + reverse("organizations:accept_invitation", args=[token])


def send_invitation_email(invitation, token):
    context = {
        "invitation": invitation,
        "organization": invitation.organization,
        "url": invitation_url(token),
        "valid_days": settings.INVITATION_VALID_DAYS,
        "invited_by": invitation.invited_by,
    }
    message = EmailMultiAlternatives(
        subject=f"Einladung in die {invitation.organization.name}",
        body=render_to_string("emails/invitation.txt", context),
        to=[invitation.email],
    )
    message.attach_alternative(render_to_string("emails/invitation.html", context), "text/html")
    message.send()


@transaction.atomic
def invite(organization, email, role, invited_by=None, send=True):
    """Lädt eine E-Mail-Adresse ein. Eine ältere offene Einladung derselben Adresse
    wird dabei zurückgezogen, damit immer nur ein gültiger Link existiert."""
    email = email.strip().lower()
    if is_operator_email(email):
        raise ValidationError(OPERATOR_NOT_ALLOWED)
    if Membership.objects.for_org(organization).filter(user__email__iexact=email).exists():
        raise ValidationError("Diese Person ist bereits Mitglied der AG.")

    Invitation.objects.for_org(organization).open().filter(email__iexact=email).update(
        revoked_at=timezone.now()
    )
    invitation = Invitation(
        organization=organization, email=email, role=role, invited_by=invited_by
    )
    token = invitation.renew_token()
    invitation.save()
    if send:
        transaction.on_commit(lambda: send_invitation_email(invitation, token))
    return invitation, token


@transaction.atomic
def resend(invitation):
    if invitation.accepted_at is not None:
        raise ValidationError("Die Einladung wurde bereits angenommen.")
    if is_operator_email(invitation.email):
        raise ValidationError(OPERATOR_NOT_ALLOWED)
    token = invitation.renew_token()
    invitation.revoked_at = None
    invitation.save()
    transaction.on_commit(lambda: send_invitation_email(invitation, token))
    return token


def revoke(invitation):
    if invitation.is_open:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at"])


def find_open_invitation(token):
    """Gibt (Einladung, Fehlertext) zurück. Abgelaufene, benutzte oder zurückgezogene
    Einladungen liefern einen verständlichen Grund."""
    invitation = (
        Invitation.objects.select_related("organization")
        .filter(token_hash=hash_token(token))
        .first()
    )
    if invitation is None:
        return None, "Dieser Einladungslink ist ungültig."
    if invitation.accepted_at is not None:
        return None, "Diese Einladung wurde bereits angenommen. Du kannst dich direkt anmelden."
    if invitation.revoked_at is not None:
        return None, "Diese Einladung wurde zurückgezogen."
    if invitation.expires_at <= timezone.now():
        return None, "Diese Einladung ist abgelaufen. Bitte frage nach einer neuen."
    if not invitation.organization.is_active:
        return None, "Diese AG ist derzeit deaktiviert."
    if is_operator_email(invitation.email):
        return None, OPERATOR_NOT_ALLOWED
    return invitation, None


@transaction.atomic
def accept(invitation, user):
    """Fügt das Konto der AG hinzu. Eine Owner-Einladung überträgt die Ownership."""
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    if not invitation.is_open:
        raise ValidationError("Diese Einladung ist nicht mehr gültig.")
    if user.email.lower() != invitation.email.lower():
        raise ValidationError("Diese Einladung gilt für eine andere E-Mail-Adresse.")
    if is_operator_email(user.email):
        raise ValidationError(OPERATOR_NOT_ALLOWED)

    organization = invitation.organization
    membership = Membership.objects.for_org(organization).filter(user=user).first()
    if membership is None:
        role = Role.ADMIN if invitation.role == Role.OWNER else invitation.role
        membership = Membership.objects.create(organization=organization, user=user, role=role)
    if invitation.role == Role.OWNER:
        make_owner(membership)

    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    return membership


@transaction.atomic
def create_account_and_accept(invitation, *, display_name, password, grade=""):
    User = get_user_model()
    if User.objects.filter(email__iexact=invitation.email).exists():
        raise ValidationError("Für diese E-Mail-Adresse gibt es schon ein Konto. Bitte anmelden.")
    user = User.objects.create_user(
        email=invitation.email, password=password, display_name=display_name, grade=grade
    )
    accept(invitation, user)
    return user


@transaction.atomic
def make_owner(membership):
    """Überträgt die Ownership. Der bisherige Owner wird Admin."""
    if is_operator_email(membership.user.email):
        raise ValidationError(OPERATOR_NOT_ALLOWED)
    organization = membership.organization
    previous = Membership.objects.for_org(organization).filter(role=Role.OWNER)
    for old_owner in previous.exclude(pk=membership.pk):
        old_owner.role = Role.ADMIN
        old_owner.save(update_fields=["role"])  # einzeln, damit das Protokoll es erfasst
    if membership.role != Role.OWNER:
        membership.role = Role.OWNER
        membership.save(update_fields=["role"])
    return membership


def change_role(membership, role):
    if role == Role.OWNER:
        raise ValidationError("Die Ownership wird über „Ownership übertragen“ geändert.")
    if membership.is_owner:
        raise ValidationError("Die Rolle des Owners kann nicht geändert werden.")
    membership.role = role
    membership.save(update_fields=["role"])


def remove_member(membership):
    if membership.is_owner:
        raise ValidationError("Der Owner kann nicht entfernt werden.")
    membership.delete()


def leave(membership):
    if membership.is_owner:
        raise ValidationError(
            "Als Owner kannst du die AG erst verlassen, wenn du die Ownership übertragen hast."
        )
    membership.delete()


def dissolve(organization: Organization, confirm_name: str):
    if confirm_name.strip() != organization.name:
        raise ValidationError("Der eingegebene Name stimmt nicht mit dem Namen der AG überein.")
    organization.delete()


# ---------- Schuljahreswechsel ----------

SCHOOL_YEAR_LOCK = timedelta(days=180)


def _next_grade(grade):
    from apps.accounts.models import Grade

    order = [value for value, _label in Grade.choices]  # 5 … Q2, Extern
    if grade not in order or grade == Grade.EXTERN:
        return None
    return order[order.index(grade) + 1]


def school_year_preview(organization, now=None):
    """Wer wird wie hochgestuft? (Wechsel, übersprungene Konten, Sperre bis)."""
    now = now or timezone.now()
    changes, skipped = {}, []
    memberships = (
        Membership.objects.for_org(organization)
        .exclude(role=Role.TEACHER)
        .select_related("user")
        .order_by("user__display_name")
    )
    for m in memberships:
        user = m.user
        target = _next_grade(user.grade)
        if target is None:
            continue
        if user.grade_promoted_at and now - user.grade_promoted_at < SCHOOL_YEAR_LOCK:
            skipped.append(user)
            continue
        changes.setdefault((user.grade, target), []).append(user)
    locked_until = None
    if organization.school_year_changed_at:
        locked_until = organization.school_year_changed_at + SCHOOL_YEAR_LOCK
        if locked_until <= now:
            locked_until = None
    return changes, skipped, locked_until


@transaction.atomic
def change_school_year(organization, now=None):
    """Alle Jahrgangsstufen eins hoch, aus Q2 wird „Extern“ (Abschnitt 2).

    Konten in mehreren AGs werden nur einmal je Schuljahr hochgestuft; eine AG kann den
    Wechsel nur einmal in 180 Tagen auslösen. Gibt die Anzahl hochgestufter Konten zurück.
    """
    from apps.board.services import post_system

    now = now or timezone.now()
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    changes, _skipped, locked_until = school_year_preview(organization, now)
    if locked_until:
        raise ValidationError(
            f"Der Schuljahreswechsel wurde schon ausgelöst; erneut möglich ab "
            f"{timezone.localtime(locked_until):%d.%m.%Y}."
        )
    count = 0
    for (_old, new), users in changes.items():
        for user in users:
            user.grade = new
            user.grade_promoted_at = now
            user.save(update_fields=["grade", "grade_promoted_at"])  # einzeln fürs Protokoll
            count += 1
    organization.school_year_changed_at = now
    organization.save(update_fields=["school_year_changed_at"])
    post_system(
        organization,
        f"Schuljahreswechsel: Die Jahrgangsstufen von {count} Mitglied"
        f"{'ern' if count != 1 else ''} wurden um eins erhöht.",
    )
    return count
