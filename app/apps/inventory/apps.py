from django.apps import AppConfig
from django.db.models.signals import post_save


def _create_defaults(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from .models import ensure_defaults

        ensure_defaults(instance)


class InventoryConfig(AppConfig):
    name = "apps.inventory"
    verbose_name = "Material"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export
        from apps.organizations.models import Organization

        post_save.connect(_create_defaults, sender=Organization, dispatch_uid="inventory-defaults")

        for name in [
            "MaterialCategory",
            "Material",
            "MaterialLink",
            "DefectReport",
            "Kit",
            "KitItem",
            "PlannedMaterial",
            "MaterialUnit",
            "UnitIssue",
            "UnitReservation",
            "ProductionTeardown",
            "TeardownException",
            "MaterialCheckout",
            "QuantityMovement",
        ]:
            model = self.get_model(name)
            audit(model)
            export.register(model)
