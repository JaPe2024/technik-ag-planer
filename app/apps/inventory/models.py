from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.organizations.models import OrganizationQuerySet, OrganizationScopedModel
from apps.productions.palette import Color

DEFAULT_CATEGORIES = [
    ("Licht", Color.YELLOW),
    ("Audio", Color.BLUE),
    ("Video", Color.VIOLET),
    ("Bühne", Color.CORAL),
    ("Strom & Kabel", Color.TEAL),
    ("Sonstiges", Color.GREY),
]


class MaterialCategory(OrganizationScopedModel):
    """Kategorie für Material – getrennt von den Produktions-Kategorien."""

    name = models.CharField("Name", max_length=60)
    color = models.CharField("Farbe", max_length=10, choices=Color.choices, default=Color.BLUE)
    position = models.PositiveIntegerField("Reihenfolge", default=0)

    class Meta:
        verbose_name = "Material-Kategorie"
        verbose_name_plural = "Material-Kategorien"
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


def ensure_defaults(organization):
    """Legt Standard-Kategorien für Material an (idempotent)."""
    if not MaterialCategory.objects.for_org(organization).exists():
        MaterialCategory.objects.bulk_create(
            MaterialCategory(organization=organization, name=name, color=color, position=i)
            for i, (name, color) in enumerate(DEFAULT_CATEGORIES)
        )


class MaterialQuerySet(OrganizationQuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class Material(OrganizationScopedModel):
    class Tracking(models.TextChoices):
        BULK = "bulk", "Mengenmaterial (z. B. Kabel)"
        INDIVIDUAL = "individual", "Einzelgeräte mit QR-Code"
        CONSUMABLE = "consumable", "Verbrauchsmaterial (ohne Rückgabe)"

    tracking = models.CharField(
        "Verwaltung", max_length=12, choices=Tracking.choices, default=Tracking.BULK
    )
    name = models.CharField("Name", max_length=120, help_text="z. B. Lichtpult")
    category = models.ForeignKey(
        MaterialCategory,
        verbose_name="Kategorie",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="materials",
    )
    quantity = models.PositiveIntegerField(
        "Bestand",
        null=True,
        blank=True,
        help_text="Leer lassen für „beliebig“, z. B. bei Verbrauchsmaterial.",
    )
    notes = models.TextField(
        "Notizen", blank=True, help_text="z. B. Lagerort, Zubehör, Besonderheiten"
    )
    archived_at = models.DateTimeField("archiviert am", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="angelegt von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField("angelegt am", auto_now_add=True)
    updated_at = models.DateTimeField("geändert am", auto_now=True)

    objects = MaterialQuerySet.as_manager()

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Material"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_unlimited(self):
        return self.quantity is None

    @property
    def is_archived(self):
        return self.archived_at is not None


class MaterialLink(OrganizationScopedModel):
    material = models.ForeignKey(
        Material, verbose_name="Material", on_delete=models.CASCADE, related_name="links"
    )
    title = models.CharField("Titel", max_length=120, blank=True, help_text="z. B. Handbuch")
    url = models.URLField("Link", max_length=500)

    class Meta:
        verbose_name = "Link"
        verbose_name_plural = "Links"
        ordering = ["id"]

    def __str__(self):
        return self.title or self.url


class DefectReport(OrganizationScopedModel):
    """Defektmeldung. Solange nicht „repariert“, fehlt die Menge im verfügbaren Bestand."""

    class Status(models.TextChoices):
        DEFECT = "defect", "defekt"
        IN_REPAIR = "in_repair", "in Reparatur"
        REPAIRED = "repaired", "repariert"

    OPEN = (Status.DEFECT, Status.IN_REPAIR)
    unit = models.ForeignKey(
        "MaterialUnit", null=True, blank=True, on_delete=models.PROTECT, related_name="defects"
    )
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    material = models.ForeignKey(
        Material, verbose_name="Material", on_delete=models.CASCADE, related_name="defects"
    )
    quantity = models.PositiveIntegerField("Menge", default=1)
    description = models.CharField(
        "Beschreibung", max_length=300, help_text="Kurz: Was ist kaputt?"
    )
    status = models.CharField(
        "Status", max_length=10, choices=Status.choices, default=Status.DEFECT
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="gemeldet von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reported_at = models.DateTimeField("gemeldet am", auto_now_add=True)
    resolved_at = models.DateTimeField("repariert am", null=True, blank=True)

    class Meta:
        verbose_name = "Defektmeldung"
        verbose_name_plural = "Defektmeldungen"
        ordering = ["-reported_at"]

    def __str__(self):
        return f"{self.material} × {self.quantity}: {self.get_status_display()}"

    @property
    def is_open(self):
        return self.status in self.OPEN


class Kit(OrganizationScopedModel):
    """Materialsatz für wiederkehrende Aufbauten, z. B. „Große Audioanlage“."""

    name = models.CharField("Name", max_length=120, help_text="z. B. Große Audioanlage")
    description = models.TextField("Beschreibung", blank=True)
    created_at = models.DateTimeField("angelegt am", auto_now_add=True)

    class Meta:
        verbose_name = "Materialsatz"
        verbose_name_plural = "Materialsätze"
        ordering = ["name"]

    def __str__(self):
        return self.name


class KitItem(OrganizationScopedModel):
    kit = models.ForeignKey(
        Kit, verbose_name="Satz", on_delete=models.CASCADE, related_name="items"
    )
    material = models.ForeignKey(
        Material, verbose_name="Material", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveIntegerField("Menge", default=1)

    class Meta:
        verbose_name = "Position im Satz"
        verbose_name_plural = "Positionen im Satz"
        ordering = ["material__name"]
        constraints = [
            models.UniqueConstraint(fields=["kit", "material"], name="kititem_unique_material")
        ]

    def __str__(self):
        return f"{self.material} × {self.quantity}"


class PlannedMaterial(OrganizationScopedModel):
    """Für eine Produktion eingeplantes Material – zugleich eine Zeile der Packliste."""

    production = models.ForeignKey(
        "productions.Production",
        verbose_name="Produktion",
        on_delete=models.CASCADE,
        related_name="planned_material",
    )
    material = models.ForeignKey(
        Material, verbose_name="Material", on_delete=models.CASCADE, related_name="plannings"
    )
    quantity = models.PositiveIntegerField("Menge", default=1)
    issued_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)

    @property
    def outstanding_quantity(self):
        return self.issued_quantity - self.returned_quantity

    # Nur zur Anzeige („aus Satz …“); Änderungen am Satz wirken nicht zurück
    source_kit = models.ForeignKey(
        Kit,
        verbose_name="aus Satz",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    issued_at = models.DateTimeField("ausgegeben am", null=True, blank=True)
    returned_at = models.DateTimeField("zurück am", null=True, blank=True)

    class Meta:
        verbose_name = "Geplantes Material"
        verbose_name_plural = "Geplantes Material"
        ordering = ["material__category__position", "material__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["production", "material"], name="planned_unique_material"
            ),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="planned_quantity_min_1"),
        ]

    def __str__(self):
        return f"{self.production} – {self.material} × {self.quantity}"


class MaterialUnit(OrganizationScopedModel):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="units")
    code = models.CharField(max_length=100, unique=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class UnitIssue(OrganizationScopedModel):
    unit = models.ForeignKey(MaterialUnit, on_delete=models.PROTECT, related_name="issues")
    production = models.ForeignKey("productions.Production", on_delete=models.PROTECT)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["unit"], condition=Q(returned_at__isnull=True), name="unit_one_open_issue"
            )
        ]


class UnitReservation(OrganizationScopedModel):
    unit = models.ForeignKey(MaterialUnit, on_delete=models.PROTECT, related_name="reservations")
    production = models.ForeignKey(
        "productions.Production", on_delete=models.CASCADE, related_name="unit_reservations"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["unit", "production"],
                condition=Q(released_at__isnull=True),
                name="unit_unique_reservation",
            )
        ]


class ProductionTeardown(OrganizationScopedModel):
    production = models.OneToOneField(
        "productions.Production", on_delete=models.CASCADE, related_name="teardown"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )


class TeardownException(OrganizationScopedModel):
    class Reason(models.TextChoices):
        MISSING = "missing", "Vermisst"
        DAMAGED = "damaged", "Beschädigt"
        OTHER = "other", "Sonstiges"

    issue = models.OneToOneField(UnitIssue, on_delete=models.PROTECT, related_name="exception")
    reason = models.CharField(max_length=10, choices=Reason.choices)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )


class MaterialCheckout(OrganizationScopedModel):
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="checkouts")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    quantity = models.PositiveIntegerField(default=1)
    taken_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="checkout_quantity_min_1")
        ]


class QuantityMovement(OrganizationScopedModel):
    planned = models.ForeignKey(PlannedMaterial, on_delete=models.PROTECT, related_name="movements")
    operation = models.CharField(
        max_length=6, choices=[("issue", "Ausgabe"), ("return", "Rückgabe")]
    )
    quantity = models.PositiveIntegerField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="movement_quantity_min_1")
        ]
