"""Inhalte für „Hilfe & FAQ“ (Abschnitt 10). `roles` leer = für alle sichtbar."""

from dataclasses import dataclass, field

from apps.organizations.permissions import Role

PLANNERS = {Role.OWNER, Role.ADMIN, Role.TEACHER}


@dataclass(frozen=True)
class Question:
    question: str
    answer: str
    roles: set = field(default_factory=set)


TOPICS = [
    (
        "Anmeldung und Konto",
        [
            Question(
                "Wie bekomme ich ein Konto?",
                "Nur per Einladung: Der Owner deiner AG lädt dich mit deiner E-Mail-Adresse ein. "
                "Über den Link in der Mail setzt du Namen und Passwort. Der Link gilt 7 Tage.",
            ),
            Question(
                "Ich habe mein Passwort vergessen.",
                "Auf der Anmeldeseite „Passwort vergessen“ antippen – du bekommst einen Link zum "
                "Zurücksetzen per E-Mail.",
            ),
            Question(
                "Was ist die Zwei-Faktor-Anmeldung?",
                "Zusätzlich zum Passwort fragt die App einen Code aus einer Authenticator-App ab "
                "(z. B. Google Authenticator, Aegis, 2FAS). Einrichten unter Einstellungen → Meine "
                "Zwei-Faktor-Anmeldung. Handy verloren? Der Betreiber der App setzt sie zurück.",
            ),
            Question(
                "Wie lösche ich mein Konto?",
                "Einstellungen → Konto löschen. Deine Einsätze und Nachrichten bleiben ohne deinen "
                "Namen als „Ehemaliges Mitglied“ erhalten. Owner übertragen vorher die Ownership.",
            ),
        ],
    ),
    (
        "App und Mitteilungen",
        [
            Question(
                "Wie installiere ich die App auf dem Handy?",
                "Android (Chrome): Menü ⋮ → „App installieren“ bzw. „Zum Startbildschirm "
                "hinzufügen“. "
                "iPhone (Safari): Teilen-Symbol → „Zum Home-Bildschirm“. Danach die App vom "
                "Home-Bildschirm öffnen.",
            ),
            Question(
                "Wie bekomme ich Push-Mitteilungen?",
                "Einstellungen → Benachrichtigungen → „Auf diesem Gerät aktivieren“ und erlauben. "
                "Dort lässt sich jede Art einzeln abschalten. Auf dem iPhone geht das nur in der "
                "App vom Home-Bildschirm. E-Mails verschickt die App dafür nie.",
            ),
            Question(
                "Wann kommt die Erinnerung vor meinem Job oder Termin?",
                "Standardmäßig am Vorabend um 18 Uhr mit Uhrzeit und Treffpunkt. Unter "
                "Einstellungen → "
                "Benachrichtigungen lässt sich das ändern, z. B. auf „3 Stunden vorher“.",
            ),
        ],
    ),
    (
        "Planung",
        [
            Question(
                "Wie nehme ich eine Crew-Anfrage an?",
                "Auf dem Dashboard unter „Meine Jobs“ oder in der Produktion auf „Annehmen“ bzw. "
                "„Ablehnen“ tippen.",
            ),
            Question(
                "Ich kann an einem Tag nicht – was tun?",
                "Unter „+ Neu“ → „Nicht verfügbar“ eintragen, ganztägig oder mit Uhrzeit bzw. "
                "Schulstunden. Wer dich dann einteilen will, bekommt eine Warnung.",
            ),
            Question(
                "Wie bekomme ich die Termine in meinen Kalender?",
                "Jeder Eintrag hat „In privaten Kalender“: Google, Apple oder als Datei. "
                "Übernommen wird eine Kopie, spätere Änderungen kommen dort nicht an. "
                "Hat die AG ein "
                "Google-Konto verbunden, kannst du den AG-Kalender abonnieren, sobald der Owner "
                "ihn "
                "für deine Google-Adresse freigegeben hat (Link in der Kalender-Ansicht).",
            ),
            Question(
                "Wo sehe ich meine Stunden?",
                "Einstellungen → Einsatzübersicht. Dort gibt es auch ein PDF, z. B. für eine "
                "AG-Bescheinigung.",
            ),
            Question(
                "Wie erstelle ich eine Freistellungsliste?",
                "In der Produktion bei den Jobs auf „Freistellungsliste“. Sie enthält alle "
                "zugesagten Schülerinnen und Schüler mit den betroffenen Schulstunden.",
                PLANNERS,
            ),
            Question(
                "Wie kommen Technik-Anfragen von Lehrkräften herein?",
                "Über den öffentlichen Link „Technik anfragen“ (Einstellungen). Neue Anfragen "
                "erscheinen oben in der Produktionsliste und lassen sich direkt zur Produktion "
                "machen. Die Ankreuzliste im Formular pflegt ihr unter Einstellungen → "
                "Technik-Auswahl.",
                PLANNERS,
            ),
        ],
    ),
    (
        "Board, Material und Dateien",
        [
            Question(
                "Wer liest das Board und die Chats?",
                "Alle Mitglieder der AG. Push-Mitteilungen aus einem Produktions-Chat bekommen "
                "aber "
                "nur die Eingeteilten und die Aufsicht.",
            ),
            Question(
                "Ein Gerät ist kaputt.",
                "Im Material das Gerät öffnen → „Defekt melden“, gern mit Foto. Es fehlt dann im "
                "verfügbaren Bestand, bis es repariert ist.",
            ),
            Question(
                "Wo liegen hochgeladene Dateien?",
                "Im Google Drive der AG, nicht auf dem Server der App. Öffnen kannst du sie über "
                "die "
                "App, ohne eigenen Google-Zugang.",
            ),
        ],
    ),
    (
        "Für Owner",
        [
            Question(
                "Wie verbinde ich das Google-Konto der AG?",
                "Einstellungen → Google-Konto → „Mit Google verbinden“ und mit einem normalen "
                "Google-Konto der AG (kein Schulkonto) anmelden. Beim Hinweis „nicht überprüft“ "
                "auf „Erweitert → Weiter“ und bei Drive und Kalender das Häkchen setzen.",
                {Role.OWNER},
            ),
            Question(
                "Was macht der Schuljahreswechsel?",
                "Alle Jahrgangsstufen rücken eins hoch, aus Q2 wird „Extern“. Am besten in den "
                "Sommerferien auslösen; die Vorschau zeigt vorher, was sich ändert.",
                {Role.OWNER},
            ),
            Question(
                "Ich verlasse die Schule.",
                "Unter Organisation verwalten die Ownership an eine Schülerin oder einen Schüler "
                "übertragen. Ohne Übergabe kann der Betreiber den Owner im Django-Admin wechseln.",
                {Role.OWNER},
            ),
        ],
    ),
]


def topics_for(role):
    result = []
    for title, questions in TOPICS:
        visible = [q for q in questions if not q.roles or role in q.roles]
        if visible:
            result.append((title, visible))
    return result
