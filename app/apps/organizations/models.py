import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .permissions import Perm, Role, role_has_perm


class Organization(models.Model):
    """Eine Technik-AG. Wird nur vom Betreiber im Django-Admin angelegt."""

    name = models.CharField("Name", max_length=120)
    inventory_qr_enabled = models.BooleanField("Einzelgeräte und QR-Scans", default=False)
    is_active = models.BooleanField(
        "aktiv", default=True, help_text="Deaktivierte AGs sind für Mitglieder nicht erreichbar."
    )
    require_2fa = models.BooleanField(
        "Zwei-Faktor für alle Mitglieder",
        default=False,
        help_text="Wenn aktiv, müssen alle Mitglieder eine Authenticator-App einrichten.",
    )
    created_at = models.DateTimeField("angelegt am", auto_now_add=True)
    school_year_changed_at = models.DateTimeField(
        "Schuljahreswechsel zuletzt am", null=True, blank=True
    )

    class Meta:
        verbose_name = "AG"
        verbose_name_plural = "AGs"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def owner_membership(self):
        return self.memberships.filter(role=Role.OWNER).select_related("user").first()


class OrganizationQuerySet(models.QuerySet):
    def for_org(self, organization):
        """Nur Daten dieser AG – Pflicht für jede Abfrage auf AG-Daten (Mandantentrennung)."""
        if organization is None:
            return self.none()
        return self.filter(organization=organization)


class OrganizationScopedModel(models.Model):
    """Basis für alle Daten, die zu genau einer AG gehören."""

    organization = models.ForeignKey(
        Organization, verbose_name="AG", on_delete=models.CASCADE, related_name="+"
    )

    objects = OrganizationQuerySet.as_manager()

    class Meta:
        abstract = True


class Membership(OrganizationScopedModel):
    organization = models.ForeignKey(
        Organization, verbose_name="AG", on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Konto",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField("Rolle", max_length=10, choices=Role.choices, default=Role.STUDENT)
    joined_at = models.DateTimeField("beigetreten am", auto_now_add=True)

    class Meta:
        verbose_name = "Mitgliedschaft"
        verbose_name_plural = "Mitgliedschaften"
        ordering = ["user__display_name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="membership_unique"),
            models.UniqueConstraint(
                fields=["organization"],
                condition=Q(role="owner"),
                name="membership_one_owner_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.user} – {self.get_role_display()} ({self.organization})"

    def has_perm(self, perm: Perm) -> bool:
        return role_has_perm(self.role, perm)

    @property
    def is_owner(self):
        return self.role == Role.OWNER


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class InvitationQuerySet(OrganizationQuerySet):
    def open(self):
        return self.filter(
            accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()
        )


class Invitation(OrganizationScopedModel):
    organization = models.ForeignKey(
        Organization, verbose_name="AG", on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField("E-Mail-Adresse")
    role = models.CharField("Rolle", max_length=10, choices=Role.choices)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="eingeladen von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("erstellt am", auto_now_add=True)
    expires_at = models.DateTimeField("gültig bis")
    accepted_at = models.DateTimeField("angenommen am", null=True, blank=True)
    revoked_at = models.DateTimeField("zurückgezogen am", null=True, blank=True)

    objects = InvitationQuerySet.as_manager()

    class Meta:
        verbose_name = "Einladung"
        verbose_name_plural = "Einladungen"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.get_role_display()}, {self.organization})"

    def renew_token(self) -> str:
        """Erzeugt ein neues Token und eine neue Frist. Gibt das Klartext-Token zurück."""
        token = secrets.token_urlsafe(32)
        self.token_hash = hash_token(token)
        self.expires_at = timezone.now() + timedelta(days=settings.INVITATION_VALID_DAYS)
        return token

    @property
    def is_open(self):
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    @property
    def status_label(self):
        if self.accepted_at:
            return "angenommen"
        if self.revoked_at:
            return "zurückgezogen"
        if self.expires_at <= timezone.now():
            return "abgelaufen"
        return "offen"
