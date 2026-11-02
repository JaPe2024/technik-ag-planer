"""Datenexport einer AG für den Betreiber (Django-Admin): ZIP mit einer JSON-Datei je Datenart.

Spätere Meilensteine tragen ihre AG-Daten hier ein: export.register(Model).
"""

import io
import json
import zipfile

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

_registry = {}

USER_FIELDS = ["id", "email", "display_name", "grade", "date_joined", "is_active"]


def register(model, *, exclude=()):
    _registry[model] = set(exclude)
    return model


def _rows(queryset, exclude):
    meta = queryset.model._meta
    fields = [f for f in meta.concrete_fields if f.name not in exclude]
    # Mehrfach-Zuordnungen (z. B. Aufsicht, Fähigkeiten) als Liste von IDs
    many = [f for f in meta.many_to_many if f.name not in exclude]
    return [
        {f.name: f.value_from_object(obj) for f in fields}
        | {f.name: sorted(o.pk for o in f.value_from_object(obj)) for f in many}
        for obj in queryset.prefetch_related(*(f.name for f in many))
    ]


def export_organization(organization) -> bytes:
    from .models import Membership

    files = {
        "ag.json": {
            "id": organization.pk,
            "name": organization.name,
            "is_active": organization.is_active,
            "require_2fa": organization.require_2fa,
            "inventory_qr_enabled": organization.inventory_qr_enabled,
            "created_at": organization.created_at,
            "exportiert_am": timezone.now(),
        },
        "konten.json": [
            {field: getattr(m.user, field) for field in USER_FIELDS}
            for m in Membership.objects.for_org(organization).select_related("user")
        ],
    }
    for model, exclude in _registry.items():
        name = f"{model._meta.app_label}_{model._meta.model_name}.json"
        # _base_manager: auch weich gelöschte Einträge (z. B. „Kürzlich gelöscht“) exportieren
        queryset = model._base_manager.filter(organization=organization).order_by("pk")
        files[name] = _rows(queryset, exclude)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(
                name, json.dumps(content, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
            )
    return buffer.getvalue()
