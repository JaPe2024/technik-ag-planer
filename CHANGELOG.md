# Changelog

Alle wichtigen Änderungen an diesem Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Bis zur ersten Version sind die Einträge nach Meilensteinen gegliedert.

## [Unveröffentlicht]

### Hinzugefügt

**Technik-Anfragen**

- Die Ankreuzliste „Welche Technik brauchen Sie?“ ist je AG einstellbar (Einstellungen → Technik-Auswahl, für Owner, Admins und Lehrkräfte)
- Offene Technik-Anfragen als Dashboard-Kachel und als Zähler am Navigationspunkt „Produktionen“, für Owner, Admins und Lehrkräfte

**Oberfläche**

- Einstellungen: Unterseite „AG anpassen“ für alles, was je AG einstellbar ist; die ganze Zeile ist anklickbar
- Hinweis für den Owner, solange kein Google-Konto verbunden ist oder der Abgleich fehlschlägt
- Behoben: Fehler beim Google-Abgleich zeigten weiter „verbunden“
- Behoben: Ordner endgültig gelöschter Produktionen blieben im Drive liegen; sie kommen jetzt in den Papierkorb
- „In privaten Kalender“ ersetzt alle .ics-Knöpfe: Auswahl aus Google Kalender (ohne Datei), Apple Kalender (direkter Dialog) und Datei herunterladen
- Nach dem Anlegen einer Produktion aus einer Anfrage fragt die App, ob die Anfrage erledigt ist
- Kalender: kein doppelter Eintrag mehr für Produktion und Jobs am selben Tag, aufgeräumter Kopfbereich
- Board: Das Eingabefeld macht die Seite auf dem Handy nicht mehr zu breit
- Board: Beim Senden bleibt die Tastatur offen, der Chat scrollt zuverlässig zur neuen Nachricht
- Board: Das Eingabefeld steht fest am unteren Bildschirmrand
- Crew und Termine: Schalter „Anfragen | Direkt einteilen“ im einheitlichen Stil; auch Erinnerungszeitpunkt und Serien-Auswahl nutzen ihn
- Produktionsseite: Ort und Notizen kompakt in einer Karte, Kopf des Jobs-Bereichs bricht sauber um

**Betrieb**

- Skript `deploy/betrieb/zugangsdaten.sh`: Datenbank- und Betreiber-Passwort ändern, passwortfreies sudo ein- oder ausschalten
- Gunicorn startet ohne ungenutzten Steuerzugang, die Fehlermeldung beim Start entfällt

**Sicherheit**

- Sicherheits-Updates: `certifi`, `brotli`, `brotlicffi`, `pyasn1`
- Betreiber-Konten können nicht mehr eingeladen werden, keiner AG beitreten und nicht Owner werden

**Betrieb**

- Optionale Ergänzung für den Betrieb hinter einem vorgeschalteten Reverse Proxy (`deploy/docker-compose.proxy.yml`)
- Behoben: Im Betrieb stürzte der Zeitplan des Workers ab (Datei nicht beschreibbar), sodass Erinnerungen, Aufräumen und nächtlicher Kalender-Abgleich ausfielen
- Behoben: Fontconfig-Fehlermeldungen im Betrieb (kein beschreibbarer Cache-Ordner)

**Wartung 1**

- Push-Erinnerung auch vor zugesagten Terminen mit Uhrzeit (z. B. AG-Treffen), mit Ort
- Erledigte Einladungen werden nach 30 Tagen automatisch gelöscht

**Meilenstein 12 – Abschluss**

- Landingpage unter `/` mit Screenshots, Funktionen, Geräte, Sicherheit, Kosten und „So startest du“
- Einstellungen → Hilfe & FAQ (je nach Rolle) und „Über die App“ (Funktionen, Version, Lizenz)
- Impressum, Datenschutz und Nutzungsbedingungen, eingetragen im Django-Admin; Vorlagen in `docs/rechtliches/`
- Status „Link ist aktiv“ bzw. „verbunden“ in der Einstellungsübersicht
- Backup- und Wiederherstellungs-Skripte (`deploy/backup/`), Betriebs-Doku und Handbuch für Owner und Mitglieder
- Sicherheits-Review mit Bericht; Content-Security-Policy; Test, der jede View als öffentlich oder geschützt einordnet

**Meilenstein 11 – PWA und Push**

- Als App auf dem Home-Bildschirm installierbar: Web-App-Manifest, Vollbild ohne Adressleiste, App-Icon (drei Entwürfe zur Auswahl)
- Push-Mitteilungen: Crew-Anfragen und Einteilungen, Änderungen an eigenen Jobs, neue Technik-Anfragen (Owner, Admins, Lehrkräfte), Board- und Chat-Nachrichten
- Erinnerung vor eigenen Jobs mit Uhrzeit und Treffpunkt – standardmäßig am Vorabend um 18 Uhr, einstellbar
- Einstellungen → Benachrichtigungen: auf diesem Gerät aktivieren, Test-Mitteilung, angemeldete Geräte, jede Art einzeln abschaltbar
- Befehl `vapid_schluessel` für die Push-Schlüssel des Servers

**Meilenstein 10 – Google-Anbindung**

- Einstellungen → Google-Konto (Owner): mit einem Google-Konto der AG verbinden, Status, „Jetzt abgleichen“, trennen
- Alle Kalendereinträge (Produktionen, Jobs, Termine, „Nicht verfügbar“) werden automatisch in einen eigenen Google-Kalender übertragen – mit Ort, Beschreibung, Crew, Farbe nach Kategorie und Link zurück in die App
- Abschnitt „Dateien“ in der Produktion mit Drive-Dateien und Links; Dateien zum Material, Fotos bei Defektmeldungen, PDF zum Ablauf im Anfrage-Formular – alles im Google Drive der AG, geöffnet über die App
- Link zum Abonnieren des Google-Kalenders in der Kalender-Ansicht
- Anleitung für das Google-Cloud-Projekt (`docs/installation/google-cloud.md`)

**Meilenstein 9 – Team-Funktionen**

- Fähigkeiten: Der Owner legt sie an, benennt sie um, sortiert und löscht sie; jedes Mitglied wählt unter „Meine Fähigkeiten“ seine eigenen; sie erscheinen in der Mitgliederliste
- Crew einteilen mit Filter nach Fähigkeit und Vorschlägen (frei, wer im Schuljahr am wenigsten eingesetzt war, zuerst)
- Einsatzübersicht je Mitglied mit Stunden aus Jobs und Terminen, Summe und Zeitraum-Filter (Schuljahr, Halbjahre, eigener Zeitraum); Gesamtübersicht für Owner, Admins und Lehrkräfte; Stunden korrigieren; Export als PDF mit Unterschriftszeile
- Schuljahreswechsel mit Vorschau: alle Jahrgangsstufen eins hoch, Q2 wird „Extern“; nur einmal je Schuljahr, auch über mehrere AGs
- Konto löschen: Einsätze, Board-Nachrichten und Call-Sheet-Einträge bleiben als „Ehemaliges Mitglied“ erhalten

**Meilenstein 8 – PDFs**

- Call Sheet je Job und „Call Sheet gesamt“ je Produktion mit Ort, Aufsicht, Jobs, Treffpunkt und Crew
- Freistellungsliste für die Schule (Owner, Admins, Lehrkräfte): Veranstaltung, Datum, Name, Jahrgangsstufe, betroffene Schulstunden laut Stundenraster und Aufsicht
- Packliste als PDF, nach Material-Kategorie gruppiert, mit Kästchen für Ausgabe und Rückgabe
- Vorschau vor dem Teilen oder Drucken mit „PDF herunterladen“, „Teilen“ und „Drucken“

**Meilenstein 7 – Technik-Anfragen**

- Öffentlicher Link „Technik anfragen“ je AG, ohne Anmeldung nutzbar; in den Einstellungen aktivieren, deaktivieren und neu erzeugen (Owner, Admins)
- Anfrage-Formular in Alltagssprache: Name, E-Mail und Datum Pflicht, sonst Freitext, Art aus den Kategorien der AG, Ankreuzliste für Technik
- Spam-Schutz mit unsichtbarem Feld und Begrenzung pro Stunde je IP und je Link
- Bereich „Anfragen“ mit Zähler oben in der Produktionsliste (Owner, Admins, Lehrkräfte)
- Geteilte Ansicht Anfrage | neue Produktion: Datum und Zeiten werden übernommen (Jobs Aufbau, Veranstaltung, Abbau), alles andere per Kopieren und Einfügen; Umschalter auf dem Handy
- „Erledigt“ archiviert Anfragen; erledigte Anfragen lassen sich wieder öffnen und werden nach 180 Tagen gelöscht

**Meilenstein 6 – Material**

- Materialliste mit Suche, Kategorie-Filter und den Ansichten „Defekt“ und „Archiviert“
- Material mit Kategorie (eigene Material-Kategorien), Bestand oder „beliebig“, Notizen und Links; archivieren statt löschen
- Defekt melden (alle Mitglieder) mit Menge und Beschreibung; Status „defekt“ → „in Reparatur“ → „repariert“; defekte Geräte fehlen im verfügbaren Bestand; Systemmeldungen im Board
- Materialsätze (Owner und Admins): anlegen, bearbeiten, kopieren, löschen; ganzen Satz in eine Produktion übernehmen
- Material in der Produktion einplanen, Menge ändern, entfernen; Konfliktwarnung nach Spitzenbedarf je Tag; Überbuchungen in Produktion und Material markiert („Geplant“)
- Packliste je Produktion zum Abhaken von Ausgabe und Rückgabe
- Beim Kopieren einer Produktion wird das geplante Material übernommen

### Geändert

- Anmeldung wieder mit E-Mail-Adresse; Beispielkonten heißen `owner@example.org` usw.
- Push-Mitteilungen nur noch an die Push-Dienste der Browser; Uploads am Webserver auf 30 MB begrenzt
- „Organisation auflösen“ funktioniert jetzt auch, wenn die AG Produktionen hat
- Mitglied entfernen und AG verlassen löschen die bisherigen Einsätze nicht mehr; sie bleiben als „Ehemaliges Mitglied“ erhalten
- Der Datenexport enthält auch Mehrfach-Zuordnungen (Aufsicht, Fähigkeiten)
- Beispielkonten melden sich mit kurzen Namen an (`owner`/`owner`, `lehrer`/`lehrer`, `schueler`/`schueler` …); das Login-Feld nimmt dafür bis M12 auch Namen ohne @ an

**Meilenstein 5 – Board** (#7)

- Board als gemeinsamer Chat der AG: Nachrichten mit farbigem Namen und Uhrzeit, Datumstrenner, eigene Nachrichten rechts; neue Nachrichten erscheinen ohne Neuladen
- Eigene Nachrichten bearbeiten („bearbeitet“) und löschen; Lehrkräfte, Admins und Owner können alle Nachrichten löschen
- Systemmeldungen: neue Produktion, Status, Datum oder Ort geändert, gelöscht und wiederhergestellt, neues Mitglied, „noch X Plätze frei“ 3 Tage vor einem Job
- Chats je Produktion: Leiste mit Kreisen oben im Board, ungelesene zuerst; Button „Chat“ in der Produktion
- Zähler ungelesener Nachrichten in Seitenleiste und „Mehr“
- Jobs mit „Benötigte Personen“ und Anzeige „x von y besetzt“

**Meilenstein 4 – Kalender und Zeiten** (#5)

- Kalender mit Monats-, Wochen- und Agenda-Ansicht, Filter „Alle“/„Meine“, Tagesdetail und „+ Termin an diesem Tag“
- Termine, auch als Serie (wöchentlich, alle 2 Wochen, monatlich) mit Enddatum; einzelne Termine verschieben oder absagen; Leute einteilen oder anfragen
- Stundenraster (Owner); Zeiten bei Jobs, Terminen und „Nicht verfügbar“ wahlweise als Schulstunde
- „Nicht verfügbar“ für alle Mitglieder, sichtbar im Kalender; Konfliktwarnung beim Einteilen zu Jobs und Terminen
- Export einzelner Einträge als `.ics` („In Kalender übernehmen“)

**Meilenstein 3 – Produktionen** (#3, #4)

- Produktionen mit Kategorie, Zeitraum, Status, Ort und Adresse („Navigation starten“), Notizen; Liste mit Suche, Kategorie-Filter und vergangenen Produktionen
- Jobs mit Datum, Zeiten und Treffpunkt; Crew anfragen oder direkt einteilen mit Position, Konfliktwarnung bei Überschneidungen; Anfragen annehmen oder ablehnen
- To-dos je Produktion (alle Mitglieder dürfen anlegen, abhaken und löschen), Lehrkräfte als Aufsicht, Kopieren von Produktionen
- „Kürzlich gelöscht“: 7 Tage wiederherstellbar, danach automatisch entfernt
- Kategorien (Owner, Admins) und Status-Werte (Owner) mit fester Palette aus 12 Farben
- Dashboard „Was steht an?“ mit nächster Produktion, Kacheln und „Meine Jobs“
- Formulare öffnen sich auf dem Handy im Bottom-Sheet; Entwürfe werden im Browser zwischengespeichert

**Meilenstein 2 – Konten und Organisationen** (#2)

- Konten nur auf Einladung: Einladungslinks (einmalig, 7 Tage gültig), Name und Jahrgangsstufe beim Beitritt, erneut senden und zurückziehen
- Anmeldung mit E-Mail und Passwort, Sperre nach 5 Fehlversuchen, „Passwort vergessen“, Abmelden
- Zwei-Faktor-Anmeldung per Authenticator-App (TOTP), auf Wunsch Pflicht für alle Mitglieder einer AG
- AGs mit Rollen Owner, Admin, Lehrkraft, Schüler/in; Rechte-Tabelle als Code, gegen die Feature-Liste getestet
- Mandantentrennung mit Tests; AG wechseln, Mitgliederliste, Rollen ändern, Mitglied entfernen, Ownership übertragen, AG verlassen und auflösen
- Einstellungen in den fünf Gruppen aus Abschnitt 10 mit Rollen-Badge
- Django-Admin für den Betreiber: AG mit Owner-Einladung anlegen, Owner wechseln, Konten sperren, 2FA zurücksetzen, Datenexport als ZIP; im Betrieb nur mit 2FA
- Internes Änderungsprotokoll, Einträge werden nach 7 Tagen gelöscht
- `make beispieldaten` und `make reset-db` für die lokale Entwicklung

**Meilenstein 1 – Grundgerüst** (#1)

- Repository-Grundstruktur, Feature-Liste, Lizenz und Projektregeln
- Django-Projekt (Django 5.2, Python 3.13) mit Settings für Entwicklung, Tests und Betrieb
- Grundlayout: Seitenleiste (Tablet quer, Computer), Leiste unten (Handy, Tablet hochkant), Bottom-Sheets für „+ Neu“ und „Mehr“
- Design-Tokens als CSS-Variablen; ein Test verhindert Farbwerte außerhalb der Tokens
- Docker-Setup für Betrieb (Web, Worker, PostgreSQL, Redis, Caddy mit HTTPS) und Entwicklung (Live-Reload, Mailpit)
- Health-Check `/healthz/`, Celery-Worker mit Beat
- Makefile, CI (Lint, Tests, Sicherheits-Check, Docker-Build) und Release-Workflow (Image nach GHCR)

### Entfernt

- `CONTRIBUTING.md` und `SECURITY.md`: Die Lizenz-Zustimmung steht in der Pull-Request-Vorlage, Sicherheitslücken werden privat über GitHub gemeldet
