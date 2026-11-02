"""Gliederung der Einstellungen (Abschnitt 10)."""

from dataclasses import dataclass

from .permissions import Perm


@dataclass(frozen=True)
class Entry:
    label: str
    subtitle: str
    url_name: str
    owner_only: bool = False
    perm: Perm | None = None


CUSTOMIZE_URL = "organizations:customize"

# Unterseite „AG anpassen“: alles, was je AG einstellbar ist
CUSTOMIZE_GROUPS = [
    (
        "Produktionen",
        [
            Entry(
                "Kategorien",
                "Produktions-Kategorien verwalten und sortieren",
                "productions:categories",
                perm=Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK,
            ),
            Entry(
                "Status-Werte",
                "Status für Produktionen mit Name und Farbe",
                "productions:statuses",
                owner_only=True,
            ),
            Entry(
                "Fähigkeiten",
                "Fähigkeiten zur Auswahl anlegen, umbenennen, sortieren, löschen",
                "productions:skills",
                owner_only=True,
            ),
        ],
    ),
    (
        "Material",
        [
            Entry(
                "Material-Kategorien",
                "Kategorien für Material verwalten und sortieren",
                "inventory:categories",
                perm=Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK,
            ),
        ],
    ),
    (
        "Technik-Anfragen",
        [
            Entry(
                "Technik anfragen",
                "Öffentlichen Anfrage-Link verwalten",
                "inquiries:settings",
                perm=Perm.MANAGE_CATEGORIES_AND_INQUIRY_LINK,
            ),
            Entry(
                "Technik-Auswahl",
                "Ankreuzliste im Anfrage-Formular verwalten und sortieren",
                "inquiries:tech_options",
                perm=Perm.MANAGE_TECH_OPTIONS,
            ),
        ],
    ),
    (
        "Schule",
        [
            Entry(
                "Stundenraster",
                "Unterrichtsstunden mit Beginn und Ende festlegen",
                "scheduling:periods",
                owner_only=True,
            ),
            Entry(
                "Schuljahreswechsel",
                "Alle Jahrgangsstufen um eins erhöhen, Q2 wird „Extern“",
                "organizations:school_year",
                owner_only=True,
            ),
        ],
    ),
    (
        "Verbindungen und Sicherheit",
        [
            Entry(
                "Google-Konto",
                "Google-Konto der AG für Drive und Kalender verbinden",
                "google_sync:settings",
                owner_only=True,
            ),
            Entry(
                "Zwei-Faktor für alle Mitglieder",
                "Pflicht ein/aus",
                "organizations:require_2fa",
                owner_only=True,
            ),
        ],
    ),
]

GROUPS = [
    (
        "AG",
        [
            Entry(
                "AG anpassen",
                "Kategorien, Stundenraster, Anfragen, Google und alles, was je AG einstellbar ist",
                CUSTOMIZE_URL,
            ),
            Entry(
                "Mitglieder",
                "Liste mit Anzahl; einladen und Rollen vergeben nur durch den Owner",
                "organizations:members",
            ),
            Entry(
                "Einsatzübersicht",
                "Einsätze und Stunden je Mitglied, als PDF",
                "productions:hours",
            ),
            Entry(
                "Kürzlich gelöscht",
                "Gelöschte Produktionen 7 Tage lang wiederherstellen",
                "productions:trash",
                perm=Perm.MANAGE_PRODUCTIONS,
            ),
            Entry(
                "Organisation verwalten",
                "Ownership übertragen, verlassen oder auflösen",
                "organizations:manage",
            ),
        ],
    ),
    (
        "Für mich",
        [
            Entry(
                "Benachrichtigungen",
                "Push-Mitteilungen aktivieren und einstellen",
                "notifications:settings",
            ),
            Entry(
                "Nicht verfügbar",
                "Tage oder Zeiträume, an denen du nicht kannst",
                "scheduling:unavailability_list",
            ),
            Entry(
                "Meine Fähigkeiten",
                "Eigene Fähigkeiten aus der Liste auswählen",
                "productions:my_skills",
            ),
            Entry("Hilfe & FAQ", "Kurze Antworten auf häufige Fragen", "core:help"),
            Entry("Über die App", "Alle Funktionen auf einen Blick", "core:about"),
        ],
    ),
    (
        "Konto",
        [
            Entry(
                "Name und Jahrgangsstufe ändern", "Frei wählbarer Anzeigename", "accounts:profile"
            ),
            Entry("Passwort ändern", "Eigenes Passwort neu setzen", "accounts:password_change"),
            Entry(
                "Meine Zwei-Faktor-Anmeldung",
                "Status, Einrichtung per Authenticator-App",
                "accounts:two_factor",
            ),
            Entry("Konto löschen", "Eigenes Konto dauerhaft löschen", "accounts:delete"),
        ],
    ),
]

CUSTOMIZE_URL_NAMES = {entry.url_name for _, entries in CUSTOMIZE_GROUPS for entry in entries}


def _visible(groups, membership):
    result = []
    for title, entries in groups:
        visible = [
            e
            for e in entries
            if (not e.owner_only or membership.is_owner)
            and (e.perm is None or membership.has_perm(e.perm))
        ]
        if visible:
            result.append((title, visible))
    return result


def visible_customize_groups(membership):
    return _visible(CUSTOMIZE_GROUPS, membership)


def visible_groups(membership):
    """Die Zeile „AG anpassen“ erscheint nur, wenn die Unterseite etwas zu bieten hat."""
    has_customize = bool(visible_customize_groups(membership))
    result = []
    for title, entries in _visible(GROUPS, membership):
        rows = [e for e in entries if e.url_name != CUSTOMIZE_URL or has_customize]
        if rows:
            result.append((title, rows))
    return result
