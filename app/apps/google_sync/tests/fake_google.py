"""Attrappe der Google-APIs für Tests (ersetzt google_api.for_connection)."""

import itertools

from apps.google_sync.google_api import NOT_CONNECTED, GoogleError

_ids = itertools.count(1)


class FakeGoogle:
    def __init__(self):
        self.folders = {}  # id → (Name, Eltern-ID)
        self.files = {}  # id → {name, mime, content, parent}
        self.calendars = {}  # id → Name
        self.events = {}  # (Kalender, Termin-ID) → body
        self.revoked = False
        self.fail_with = None  # GoogleError, die der nächste Aufruf wirft
        self.calls = []

    def _maybe_fail(self, name):
        self.calls.append(name)
        if self.fail_with:
            error, self.fail_with = self.fail_with, None
            raise error

    # Drive
    def create_folder(self, name, parent=None):
        self._maybe_fail("create_folder")
        folder_id = f"folder-{next(_ids)}"
        self.folders[folder_id] = (name, parent)
        return folder_id

    def upload(self, name, mime_type, fileobj, parent):
        self._maybe_fail("upload")
        if parent not in self.folders:
            raise GoogleError("Ordner fehlt", "not_found")
        file_id = f"file-{next(_ids)}"
        self.files[file_id] = {
            "name": name,
            "mime": mime_type,
            "content": fileobj.read(),
            "parent": parent,
        }
        return file_id

    def download(self, file_id):
        self._maybe_fail("download")
        if file_id not in self.files:
            raise GoogleError("Die Datei gibt es im Google Drive nicht mehr.", "not_found")
        return self.files[file_id]["content"]

    def delete_file(self, file_id):
        self._maybe_fail("delete_file")
        self.files.pop(file_id, None)

    def trash_file(self, file_id):
        self._maybe_fail("trash_file")
        self.folders.pop(file_id, None)

    def path_of(self, file_id):
        """„Wurzel/Unterordner/…“ einer Datei – für Tests der Ordnerstruktur."""
        parts, parent = [], self.files[file_id]["parent"]
        while parent:
            name, parent = self.folders[parent]
            parts.insert(0, name)
        return "/".join(parts)

    # Kalender
    def create_calendar(self, summary):
        self._maybe_fail("create_calendar")
        calendar_id = f"cal-{next(_ids)}@group.calendar.google.com"
        self.calendars[calendar_id] = summary
        return calendar_id

    def calendar_exists(self, calendar_id):
        self._maybe_fail("calendar_exists")
        return calendar_id in self.calendars

    def insert_event(self, calendar_id, body):
        self._maybe_fail("insert_event")
        event_id = f"event-{next(_ids)}"
        self.events[(calendar_id, event_id)] = body
        return event_id

    def update_event(self, calendar_id, event_id, body):
        self._maybe_fail("update_event")
        if (calendar_id, event_id) not in self.events:
            raise GoogleError("weg", "not_found")
        self.events[(calendar_id, event_id)] = body

    def delete_event(self, calendar_id, event_id):
        self._maybe_fail("delete_event")
        self.events.pop((calendar_id, event_id), None)

    def revoke(self):
        self.revoked = True

    def by_key(self):
        """{app_key: body} aller Termine."""
        return {b["extendedProperties"]["private"]["app_key"]: b for b in self.events.values()}


def factory(fake):
    def for_connection(connection):
        if not connection or not connection.refresh_token:
            raise GoogleError(NOT_CONNECTED, "not_connected")
        return fake

    return for_connection
