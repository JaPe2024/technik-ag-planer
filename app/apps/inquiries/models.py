import secrets

from django.conf import settings
from django.db import models

from apps.organizations.models import OrganizationQuerySet, OrganizationScopedModel

# Startwerte der Ankreuzliste im Anfrage-Formular – in Alltagssprache (Abschnitt 6)
DEFAULT_TECH_OPTIONS = [
    "Mikrofone",
    "Musik abspielen",
    "Licht",
    "Beamer und Leinwand",
    "Laptop anschließen",
]


def new_token():
    return secrets.token_urlsafe(16)


class TechOption(OrganizationScopedModel):
    """Eintrag der Ankreuzliste „Welche Technik brauchen Sie?“ einer AG."""

    name = models.CharField("Bezeichnung", max_length=60)
    position = models.PositiveIntegerField("Reihenfolge", default=0)

    class Meta:
        verbose_name = "Technik-Auswahl"
        verbose_name_plural = "Technik-Auswahl"
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


def ensure_defaults(organization):
    """Legt die Startwerte der Technik-Auswahl für eine AG an (idempotent)."""
    if not TechOption.objects.for_org(organization).exists():
        TechOption.objects.bulk_create(
            TechOption(organization=organization, name=name, position=i)
            for i, name in enumerate(DEFAULT_TECH_OPTIONS)
        )


class InquiryLink(OrganizationScopedModel):
    """Öffentlicher Link „Technik anfragen“ – einer je AG.

    Der Token steht im Klartext: Owner und Admins müssen den Link immer wieder sehen und
    weitergeben können. Ein neuer Token macht den alten Link ungültig.
    """

    organization = models.OneToOneField(
        "organizations.Organization",
        verbose_name="AG",
        on_delete=models.CASCADE,
        related_name="inquiry_link",
    )
    token = models.CharField(max_length=40, unique=True, default=new_token, editable=False)
    is_active = models.BooleanField("aktiv", default=False)
    created_at = models.DateTimeField("angelegt am", auto_now_add=True)

    class Meta:
        verbose_name = "Anfrage-Link"
        verbose_name_plural = "Anfrage-Links"

    def __str__(self):
        return f"{self.organization} ({'aktiv' if self.is_active else 'nicht aktiv'})"

    def renew(self):
        self.token = new_token()
        self.save(update_fields=["token"])


class InquiryQuerySet(OrganizationQuerySet):
    def open(self):
        return self.filter(done_at__isnull=True)

    def done(self):
        return self.filter(done_at__isnull=False)


class Inquiry(OrganizationScopedModel):
    """Technik-Anfrage einer Person ohne Konto (Lehrkraft, Schulleitung, SV …)."""

    # Wer fragt an
    requester_name = models.CharField("Ihr Name", max_length=120)
    requester_email = models.EmailField("Ihre E-Mail-Adresse")
    requester_role = models.CharField(
        "Funktion", max_length=80, blank=True, help_text="z. B. Lehrkraft, Schulleitung, SV"
    )
    # Was
    event_name = models.CharField(
        "Name der Veranstaltung", max_length=120, blank=True, help_text="z. B. Elternabend"
    )
    category = models.ForeignKey(
        "productions.Category",
        verbose_name="Art der Veranstaltung",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Wann
    date = models.DateField("Datum")
    start_time = models.TimeField("Beginn", null=True, blank=True)
    end_time = models.TimeField("Ende", null=True, blank=True)
    setup_from = models.TimeField(
        "Aufbau ab", null=True, blank=True, help_text="Ab wann darf aufgebaut werden?"
    )
    teardown_until = models.TimeField(
        "Abbau bis", null=True, blank=True, help_text="Bis wann muss abgebaut sein?"
    )
    # Wo
    location = models.CharField("Ort bzw. Raum", max_length=120, blank=True)
    # Welche Technik
    tech_needs = models.JSONField("Welche Technik", default=list, blank=True)
    tech_notes = models.TextField(
        "Sonstiges zur Technik",
        blank=True,
        help_text="Was brauchen Sie noch? Gern in eigenen Worten.",
    )
    # Ablauf
    schedule = models.TextField("Programm bzw. Ablauf", blank=True)
    schedule_link = models.URLField("Link zum Ablauf", max_length=500, blank=True)
    # Ansprechperson am Tag
    contact_name = models.CharField("Ansprechperson am Tag", max_length=120, blank=True)
    contact_phone = models.CharField("Telefonnummer", max_length=40, blank=True)
    # Bearbeitung in der AG
    created_at = models.DateTimeField("eingegangen am", auto_now_add=True)
    done_at = models.DateTimeField("erledigt am", null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="erledigt von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    production = models.ForeignKey(
        "productions.Production",
        verbose_name="daraus angelegte Produktion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = InquiryQuerySet.as_manager()

    class Meta:
        verbose_name = "Technik-Anfrage"
        verbose_name_plural = "Technik-Anfragen"
        ordering = ["date", "start_time", "created_at"]

    def __str__(self):
        return f"{self.title} ({self.date:%d.%m.%Y})"

    @property
    def title(self):
        return self.event_name or "Veranstaltung ohne Namen"

    @property
    def is_done(self):
        return self.done_at is not None
