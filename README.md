# Technik-AG Planer

Planungs-App für Technik-AGs an Schulen: Produktionen, Jobs und Crew, Kalender, Material, Board und Technik-Anfragen – als Django-Web-App für Handy, Tablet und Computer (PWA).

> **Stand:** Alle 12 Meilensteine sind umgesetzt. Vor dem Einsatz an einer Schule stehen noch echte Tests (Google, Handys), die Rechtstexte und die Abstimmung mit der Schule aus – siehe [Umsetzungsstand und „Vor dem Start“](docs/feature-liste.md#16-umsetzungsstand-und-entscheidungen).

## Was die App schon kann

- **Konten nur auf Einladung**, Anmeldung mit Zwei-Faktor (Authenticator-App), mehrere AGs je Konto, Rollen Owner, Admin, Lehrkraft und Schüler/in
- **Produktionen** mit Jobs, Crew (anfragen, einteilen, Konfliktwarnung), To-dos, Aufsicht, Kopieren und „Kürzlich gelöscht“
- **Dashboard „Was steht an?“** mit nächster Produktion und „Meine Jobs“
- **Kalender** (Monat, Woche, Agenda), Termine und Terminserien, Stundenraster, „Nicht verfügbar“, Übernahme in den privaten Kalender (Google, Apple, `.ics`)
- **Board** als Chat der AG mit Systemmeldungen, Chats je Produktion, Moderation und Zähler für ungelesene Nachrichten
- **Material** mit Kategorien, Bestand, Links, Defektmeldungen und Materialsätzen; Planung je Produktion mit Konfliktwarnung und Packliste zum Abhaken
- **Technik anfragen** über einen öffentlichen Link ohne Konto; Anfragen erscheinen in der Produktionsliste und werden in einer geteilten Ansicht zur Produktion
- **PDFs** mit Vorschau zum Herunterladen, Teilen und Drucken: Call Sheet je Job und je Produktion, Freistellungsliste für die Schule, Packliste, Einsatzübersicht
- **Team:** Fähigkeiten mit Filter und Vorschlägen beim Einteilen, Einsatzübersicht mit Stundenkorrektur, Schuljahreswechsel, Konto löschen (Einsätze bleiben als „Ehemaliges Mitglied“)
- **Google-Anbindung:** Dateien (Produktionen, Material, Defektfotos, Anfragen) im Google Drive der AG, alle Kalendereinträge automatisch im Google-Kalender der AG – [Einrichtung](docs/installation/google-cloud.md)
- **Als App installierbar** (Home-Bildschirm, Vollbild) mit **Push-Mitteilungen** zu Crew-Anfragen, Änderungen, Technik-Anfragen, Board und Chats sowie Erinnerung vor eigenen Jobs
- **Landingpage, Hilfe & FAQ, „Über die App“** und Seiten für Impressum, Datenschutz und Nutzungsbedingungen
- **Django-Admin** für den Betreiber: AGs anlegen, Owner einladen, Konten verwalten, Datenexport, Änderungsprotokoll

## Schnellstart (Entwicklung)

Voraussetzungen: Docker mit Compose und `make`. Für Arbeit ohne Docker zusätzlich [uv](https://docs.astral.sh/uv/) und für die PDFs die Bibliothek Pango (z. B. `apt install libpango-1.0-0 libpangoft2-1.0-0`).

```sh
make dev            # App auf http://localhost:8000, Test-Mails (Mailpit) auf http://localhost:8025
make migrate        # in einem zweiten Terminal: Datenbank einrichten
make beispieldaten  # zwei Beispiel-AGs mit Konten, Produktionen, Terminen, Board, Material und Anfragen (gibt den Anfrage-Link aus)
make superuser      # Betreiber-Konto für den Django-Admin (http://localhost:8000/admin/)
```

Beispielkonten (Passwort = Name vor dem @, z. B. `owner@example.org` / `owner`; nach einer Änderung `make reset-db && make beispieldaten`):

| Anmeldung | Rolle |
| --- | --- |
| `owner@example.org` | Owner der Technik-AG Nord |
| `admin@example.org` | Admin |
| `lehrer@example.org` | Lehrkraft |
| `schueler@example.org` | Schülerin (Emma), auch Mitglied der Technik-AG Süd |
| `ben@example.org` | Schüler |
| `sued@example.org` | Owner der Technik-AG Süd |

Weitere Befehle:

```sh
make test       # Tests gegen PostgreSQL
make lint       # Code prüfen (ruff)
make format     # Code formatieren
make reset-db   # Entwicklungs-Datenbank neu aufsetzen (z. B. nach größeren Modelländerungen)
make help       # alle Befehle
```

Die Entwicklungsumgebung braucht keine `.env`. Nach neuen Abhängigkeiten (`uv add …` in `app/`) einmal `make build`.

## Betrieb

Kurzfassung – Details in [docs/installation/](docs/installation/README.md):

```sh
cp .env.example .env   # Werte eintragen, v. a. Domain, Passwörter, Secret Key
docker compose -f deploy/docker-compose.yml up -d
```

Caddy holt automatisch ein HTTPS-Zertifikat für `DOMAIN`. Migrationen laufen beim Start des Web-Containers. Den Django-Admin für den Betreiber beschreibt [docs/betrieb/django-admin.md](docs/betrieb/django-admin.md).

## Aufbau

| Ordner | Inhalt |
| --- | --- |
| `app/` | Django-Projekt: `config/` (Settings, URLs, Celery), `apps/` (Fach-Apps), `templates/`, `static/`, `tests/` |
| `deploy/` | Dockerfile, Compose für Betrieb und Entwicklung, Caddy |
| `docs/` | Feature-Liste, Architektur-Entscheidungen, Anleitungen – Übersicht in [docs/README.md](docs/README.md) |
| `.github/` | CI, Release-Workflow, Vorlagen für Issues und Pull Requests |

## Stack

Django 5.2 (Python 3.13), PostgreSQL, Redis, Celery, Docker, Caddy – Details in [ADR 0002](docs/architektur/0002-stack.md).

## Lizenz

Quelloffen (source-available) unter der [PolyForm Noncommercial License 1.0.0](LICENSE). Nutzung, Änderung und Weitergabe für nicht-kommerzielle Zwecke sind erlaubt – Schulen und andere Bildungseinrichtungen ausdrücklich eingeschlossen. Kommerzielle Nutzung ist nicht erlaubt. Für Beiträge gilt die Zustimmung in der Pull-Request-Vorlage. Sicherheitslücken bitte nicht als öffentliches Issue, sondern [privat über GitHub](https://github.com/LABSTORM-MG/technik-ag-planer/security/advisories/new) melden.
