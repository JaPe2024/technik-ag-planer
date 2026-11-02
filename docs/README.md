# Dokumentation

| Dokument | Inhalt |
| --- | --- |
| [feature-liste.md](feature-liste.md) | Verbindliche Spezifikation (Abschnitte 1–15) und Umsetzungsstand mit allen Entscheidungen (Abschnitt 16) |
| [architektur/](architektur/) | Architektur-Entscheidungen (ADRs), siehe unten |
| [installation/](installation/README.md) | Server einrichten, `.env`, Start, Google-Cloud-Projekt, Push-Schlüssel |
| [betrieb/](betrieb/README.md) | Betrieb: Updates, Backups und Wiederherstellung, Logs, typische Aufgaben und Probleme; [Django-Admin](betrieb/django-admin.md) |
| [handbuch/](handbuch/README.md) | Anleitungen für Owner und Mitglieder |
| [rechtliches/](rechtliches/README.md) | Vorlagen für Impressum, Datenschutzerklärung, Nutzungsbedingungen |
| [sicherheit/](sicherheit/review-2026-10.md) | Sicherheits-Review vor dem Start |
| [design/app-icon/](design/app-icon/) | Entwürfe für das App-Icon |

## Erweiterungen im Fork

- [Materialerweiterung – Entwicklerübergabe](entwicklung/materialerweiterung.md): Funktionsumfang, Modelle, Migrationen, Teststand und offene Übernahmeprüfungen zu Meilenstein 13.
- [Material und Scans – Bedienungsanleitung](handbuch/material-scans.md).

## Architektur-Entscheidungen

| Nr. | Titel |
| --- | --- |
| [0001](architektur/0001-repository-struktur.md) | Monorepo-Struktur |
| [0002](architektur/0002-stack.md) | Technischer Stack (Django, uv, Celery, kein JS-Build) |
| [0003](architektur/0003-core-app.md) | App `core` für Grundlayout |
| [0004](architektur/0004-konten-und-mandanten.md) | Konten, Mandantentrennung und Rechte |
| [0005](architektur/0005-produktionen.md) | Produktionen – Farben, Status, Löschen, Formulare |
| [0006](architektur/0006-kalender-und-zeiten.md) | Kalender, Serien, Schulstunden und ICS |
| [0007](architektur/0007-board.md) | Board, Produktions-Chats und Systemmeldungen |
| [0008](architektur/0008-material.md) | Material, Defekte, Materialsätze und Packliste |
| [0009](architektur/0009-technik-anfragen.md) | Technik-Anfragen über einen öffentlichen Link |
| [0010](architektur/0010-pdfs.md) | PDFs mit WeasyPrint |
| [0011](architektur/0011-team-funktionen.md) | Fähigkeiten, Einsatzübersicht, Schuljahreswechsel, Konto löschen |
| [0012](architektur/0012-google-anbindung.md) | Google-Anbindung: Drive und Kalender |
| [0013](architektur/0013-pwa-und-push.md) | PWA und Push-Mitteilungen |
| [0014](architektur/0014-abschluss.md) | Landingpage, Rechtstexte, CSP, Sicherheits-Test, Backups |
| [0015](architektur/0015-erinnerungen-und-einladungen.md) | Erinnerungen vor Terminen, Einladungen aufräumen |
| [0016](architektur/0016-betrieb-hinter-reverse-proxy.md) | Betrieb hinter Reverse Proxy |
| [0017](architektur/0017-betreiber-konten-trennen.md) | Betreiber-Konten trennen |
| [0018](architektur/0018-technik-auswahl.md) | Technik-Auswahl je AG |
| [0019](architektur/0019-kalender-produktion-einmal.md) | Kalender: Produktion einmal anzeigen |
| [0020](architektur/0020-material-einzelgeraete.md) | Optionaler QR-Modus und gemischte Materialverwaltung (Fork, zur Übernahmeprüfung) |

Neue Entscheidungen bekommen die nächste Nummer und einen Eintrag in Abschnitt 16 der Feature-Liste.
