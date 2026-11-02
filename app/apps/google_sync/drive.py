"""Dateien im Google Drive der AG: Ordner, Hochladen, Öffnen, Löschen (Abschnitt 2)."""

import logging

from django.conf import settings

from .google_api import GoogleError
from .models import Attachment
from .services import api_for, connection_for

logger = logging.getLogger(__name__)

TOO_LARGE = "Die Datei ist zu groß (höchstens {mb} MB)."


def _folder(connection, api, key, name, parent):
    folder_id = connection.folder_ids.get(key)
    if not folder_id:
        folder_id = api.create_folder(name, parent)
        connection.folder_ids = {**connection.folder_ids, key: folder_id}
        connection.save(update_fields=["folder_ids"])
    return folder_id


def _root(connection, api):
    if not connection.root_folder_id:
        name = f"Technik-AG Planer – {connection.organization.name}"
        connection.root_folder_id = api.create_folder(name)
        connection.save(update_fields=["root_folder_id"])
    return connection.root_folder_id


def folder_for(connection, api, *, production=None, material=None, defect=None, inquiry=None):
    """Unterordner: Produktionen/<Name (Datum)>, Material (auch Defektfotos) oder Anfragen."""
    root = _root(connection, api)
    if production is not None:
        parent = _folder(connection, api, "productions", "Produktionen", root)
        name = f"{production.name} ({production.start_date:%d.%m.%Y})"
        return _folder(connection, api, f"production:{production.pk}", name, parent)
    if material is not None or defect is not None:
        return _folder(connection, api, "material", "Material", root)
    if inquiry is not None:
        return _folder(connection, api, "inquiries", "Anfragen", root)
    raise ValueError("Ziel fehlt")


def _reset_folders(connection):
    connection.root_folder_id = ""
    connection.folder_ids = {}
    connection.save(update_fields=["root_folder_id", "folder_ids"])


def upload(organization, uploaded_file, *, user=None, max_mb=None, **target):
    """Lädt eine Datei hoch und legt das Attachment an. Wirft GoogleError mit Text."""
    max_mb = max_mb or settings.GOOGLE_UPLOAD_MAX_MB
    if uploaded_file.size > max_mb * 1024 * 1024:
        raise GoogleError(TOO_LARGE.format(mb=max_mb), "too_large")
    api = api_for(organization)
    connection = connection_for(organization)
    mime_type = uploaded_file.content_type or "application/octet-stream"
    try:
        parent = folder_for(connection, api, **target)
        file_id = api.upload(uploaded_file.name, mime_type, uploaded_file, parent)
    except GoogleError as error:
        if error.kind != "not_found":
            raise
        # Ordner wurde im Drive gelöscht – einmal neu anlegen
        _reset_folders(connection)
        uploaded_file.seek(0)
        parent = folder_for(connection, api, **target)
        file_id = api.upload(uploaded_file.name, mime_type, uploaded_file, parent)
    return Attachment.objects.create(
        organization=organization,
        name=uploaded_file.name[:200],
        mime_type=mime_type[:120],
        size=uploaded_file.size,
        drive_file_id=file_id,
        uploaded_by=user,
        **target,
    )


def download(attachment):
    return api_for(attachment.organization).download(attachment.drive_file_id)


def delete(attachment):
    """Löscht die Datei im Drive und in der App. Ohne Verbindung bleibt sie im Drive liegen;
    gibt dann False zurück."""
    removed = True
    try:
        api_for(attachment.organization).delete_file(attachment.drive_file_id)
    except GoogleError as error:
        logger.warning("Drive-Datei %s nicht gelöscht: %s", attachment.drive_file_id, error)
        removed = False
    attachment.delete()
    return removed


def trash_production_folder(production):
    """Legt den Ordner einer endgültig gelöschten Produktion in den Papierkorb des Drive."""
    connection = connection_for(production.organization)
    key = f"production:{production.pk}"
    if connection is None or key not in connection.folder_ids:
        return
    try:
        api_for(production.organization).trash_file(connection.folder_ids[key])
    except GoogleError as error:
        logger.warning("Drive-Ordner %s nicht entfernt: %s", key, error)
        return
    connection.folder_ids = {k: v for k, v in connection.folder_ids.items() if k != key}
    connection.save(update_fields=["folder_ids"])


def delete_all(attachments):
    """Für Aufräum-Tasks: Drive-Dateien entfernen, bevor die Einträge endgültig verschwinden."""
    for attachment in list(attachments):
        delete(attachment)
