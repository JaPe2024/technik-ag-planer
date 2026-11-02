"""Schmale Hülle um die Google-APIs (Drive v3, Calendar v3).

Alle Google-Aufrufe der App laufen hierüber; Tests ersetzen `for_connection` durch eine
Attrappe (apps/google_sync/tests/fake_google.py).
"""

import contextlib
import io

import requests
from django.conf import settings

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.app.created",
]
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 – Adresse, kein Geheimnis
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
FOLDER_MIME = "application/vnd.google-apps.folder"

NOT_CONNECTED = "Kein Google-Konto verbunden – bitte den Owner fragen."
EXPIRED = "Verbindung zu Google abgelaufen – bitte den Owner fragen."
QUOTA = "Google-Drive-Speicher ist voll."
UNAVAILABLE = "Google ist gerade nicht erreichbar. Bitte später erneut versuchen."
NOT_FOUND = "Die Datei gibt es im Google Drive nicht mehr."


class GoogleError(Exception):
    """Fehler bei Google mit verständlichem deutschem Text. `kind`: not_connected, expired,
    quota, not_found, other."""

    def __init__(self, message, kind="other"):
        super().__init__(message)
        self.message = message
        self.kind = kind


def is_configured():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _translate(error):
    from google.auth.exceptions import RefreshError, TransportError
    from googleapiclient.errors import HttpError

    if isinstance(error, GoogleError):
        return error
    if isinstance(error, RefreshError):
        return GoogleError(EXPIRED, "expired")
    if isinstance(error, TransportError):
        return GoogleError(UNAVAILABLE)
    if isinstance(error, HttpError):
        status = error.resp.status
        # Der Grund (z. B. „storageQuotaExceeded“) steht im Inhalt der Antwort
        text = (error.content or b"").decode(errors="ignore") + str(error.error_details or "")
        if status == 403 and "storageQuotaExceeded" in text:
            return GoogleError(QUOTA, "quota")
        if status in (404, 410):
            return GoogleError(NOT_FOUND, "not_found")
        if status == 401:
            return GoogleError(EXPIRED, "expired")
        return GoogleError(UNAVAILABLE)
    return GoogleError(UNAVAILABLE)


class GoogleApi:
    def __init__(self, connection):
        from google.oauth2.credentials import Credentials

        token = connection.refresh_token if connection else ""
        if not token:
            raise GoogleError(NOT_CONNECTED, "not_connected")
        self.credentials = Credentials(
            token=None,
            refresh_token=token,
            token_uri=TOKEN_URI,
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=connection.scopes or SCOPES,
        )
        self._services = {}

    def _service(self, name, version):
        from googleapiclient.discovery import build

        if name not in self._services:
            self._services[name] = build(
                name, version, credentials=self.credentials, cache_discovery=False
            )
        return self._services[name]

    def _call(self, request):
        try:
            return request.execute(num_retries=2)
        except Exception as error:  # noqa: BLE001 – alle Google-Fehler übersetzen
            raise _translate(error) from error

    # ---------- Drive ----------

    def create_folder(self, name, parent=None):
        body = {"name": name, "mimeType": FOLDER_MIME, **({"parents": [parent]} if parent else {})}
        drive = self._service("drive", "v3")
        return self._call(drive.files().create(body=body, fields="id"))["id"]

    def file_exists(self, file_id):
        drive = self._service("drive", "v3")
        try:
            result = self._call(drive.files().get(fileId=file_id, fields="id,trashed"))
        except GoogleError as error:
            if error.kind == "not_found":
                return False
            raise
        return not result.get("trashed", False)

    def upload(self, name, mime_type, fileobj, parent):
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(fileobj, mimetype=mime_type, resumable=True)
        drive = self._service("drive", "v3")
        request = drive.files().create(
            body={"name": name, "parents": [parent]}, media_body=media, fields="id"
        )
        return self._call(request)["id"]

    def download(self, file_id):
        from googleapiclient.http import MediaIoBaseDownload

        drive = self._service("drive", "v3")
        buffer = io.BytesIO()
        try:
            downloader = MediaIoBaseDownload(buffer, drive.files().get_media(fileId=file_id))
            done = False
            while not done:
                _status, done = downloader.next_chunk(num_retries=2)
        except Exception as error:  # noqa: BLE001
            raise _translate(error) from error
        return buffer.getvalue()

    def delete_file(self, file_id):
        drive = self._service("drive", "v3")
        try:
            self._call(drive.files().delete(fileId=file_id))
        except GoogleError as error:
            if error.kind != "not_found":
                raise

    def trash_file(self, file_id):
        """In den Papierkorb statt endgültig: Ein Ordner kann selbst abgelegte Dateien enthalten."""
        drive = self._service("drive", "v3")
        try:
            self._call(drive.files().update(fileId=file_id, body={"trashed": True}))
        except GoogleError as error:
            if error.kind != "not_found":
                raise

    # ---------- Kalender ----------

    def create_calendar(self, summary):
        calendar = self._service("calendar", "v3")
        body = {"summary": summary, "timeZone": settings.TIME_ZONE}
        return self._call(calendar.calendars().insert(body=body))["id"]

    def calendar_exists(self, calendar_id):
        calendar = self._service("calendar", "v3")
        try:
            self._call(calendar.calendars().get(calendarId=calendar_id))
        except GoogleError as error:
            if error.kind == "not_found":
                return False
            raise
        return True

    def insert_event(self, calendar_id, body):
        events = self._service("calendar", "v3").events()
        return self._call(events.insert(calendarId=calendar_id, body=body))["id"]

    def update_event(self, calendar_id, event_id, body):
        events = self._service("calendar", "v3").events()
        self._call(events.update(calendarId=calendar_id, eventId=event_id, body=body))

    def delete_event(self, calendar_id, event_id):
        events = self._service("calendar", "v3").events()
        try:
            self._call(events.delete(calendarId=calendar_id, eventId=event_id))
        except GoogleError as error:
            if error.kind != "not_found":
                raise

    # ---------- Verbindung ----------

    def revoke(self):
        """Widerruft den Zugriff bei Google. Fehler sind egal – getrennt wird trotzdem."""
        with contextlib.suppress(requests.RequestException):
            requests.post(REVOKE_URI, data={"token": self.credentials.refresh_token}, timeout=10)


def for_connection(connection):
    return GoogleApi(connection)
