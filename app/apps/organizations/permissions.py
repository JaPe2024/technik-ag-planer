"""Rollen und Rechte – verbindlich nach der Tabelle in Abschnitt 2 der Feature-Liste.

Ein Test vergleicht diese Datei Zeile für Zeile mit docs/feature-liste.md.
"""

from enum import Enum

from django.db import models


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    TEACHER = "teacher", "Lehrkraft"
    STUDENT = "student", "Schüler/in"


O, A, T, S = Role.OWNER, Role.ADMIN, Role.TEACHER, Role.STUDENT  # noqa: E741 – Kürzel wie in der Tabelle
ALL = frozenset({O, A, T, S})


class Perm(Enum):
    """Wert = (Funktion laut Tabelle, Rollen mit „ja“)."""

    MANAGE_PRODUCTIONS = ("Produktionen anlegen und bearbeiten", {O, A, T})
    MANAGE_CREW = ("Crew anfragen und einteilen", {O, A, T})
    RESPOND_TO_REQUESTS = ("Anfragen annehmen und ablehnen (eigene Jobs)", ALL)
    BE_SUPERVISOR = ("Als Aufsicht eintragen", {T})
    MANAGE_INVENTORY = ("Material anlegen, bearbeiten, archivieren", {O, A, T})
    REPORT_DEFECT = ("Defekt melden", ALL)
    USE_BOARD = ("Board lesen und schreiben", ALL)
    INVITE_MEMBERS = ("Mitglieder einladen und Rollen vergeben", {O})
    MANAGE_CATEGORIES_AND_INQUIRY_LINK = (
        "Kategorien und „Technik anfragen“-Link verwalten",
        {O, A},
    )
    CREATE_RELEASE_LIST = ("Freistellungsliste erstellen", {O, A, T})
    MANAGE_2FA_AND_DISSOLVE = ("Zwei-Faktor-Pflicht, Organisation auflösen", {O})
    MANAGE_KITS = ("Materialsätze anlegen und bearbeiten", {O, A})
    MODERATE_MESSAGES = ("Nachrichten anderer löschen (Moderation)", {O, A, T})
    # Schüler/innen sehen nur ihre eigene Übersicht („nur eigene“)
    VIEW_ALL_ASSIGNMENTS = ("Einsatzübersicht aller Mitglieder sehen", {O, A, T})
    MANAGE_ORG_CONFIG = (
        "Google-Konto, Stundenraster, Fähigkeiten und Status-Werte verwalten",
        {O},
    )
    HANDLE_INQUIRIES = (
        "Technik-Anfragen sehen, übernehmen und als erledigt markieren",
        {O, A, T},
    )
    MANAGE_TECH_OPTIONS = ("Technik-Auswahl für Anfragen verwalten", {O, A, T})
    CREATE_EVENTS = ("Termine anlegen", {O, A, T})
    OWN_UNAVAILABILITY = ("Eigene „Nicht verfügbar“-Einträge", ALL)
    CORRECT_HOURS = ("Stunden in der Einsatzübersicht korrigieren", {O, A, T})
    TRIGGER_SCHOOL_YEAR_CHANGE = ("Schuljahreswechsel auslösen", {O})

    @property
    def label(self):
        return self.value[0]

    @property
    def roles(self):
        return frozenset(self.value[1])


def role_has_perm(role, perm: Perm) -> bool:
    return role in perm.roles


class OrgPerms:
    """Für Templates: {% if org_perms.INVITE_MEMBERS %} …"""

    def __init__(self, membership):
        self._role = membership.role if membership else None

    def __getattr__(self, name):
        try:
            perm = Perm[name]
        except KeyError:
            raise AttributeError(name) from None
        return self._role is not None and role_has_perm(self._role, perm)

    def __getitem__(self, name):
        return getattr(self, name)
