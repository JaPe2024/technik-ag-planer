from django.apps import AppConfig
from django.db.models.signals import post_save


def _create_defaults(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from .models import ensure_defaults

        ensure_defaults(instance)


class InquiriesConfig(AppConfig):
    name = "apps.inquiries"
    verbose_name = "Technik-Anfragen"

    def ready(self):
        from apps.audit.registry import register as audit
        from apps.organizations import export
        from apps.organizations.models import Organization

        post_save.connect(_create_defaults, sender=Organization, dispatch_uid="inquiry-defaults")

        for name in ["InquiryLink", "Inquiry", "TechOption"]:
            model = self.get_model(name)
            audit(model)
            export.register(model)
