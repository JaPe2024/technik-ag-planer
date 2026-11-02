# Datenschutzerklärung – Vorlage

> Vorlage ohne Rechtsberatung. Abschnitte mit `[…]` ergänzen, alles mit Schule und Datenschutzbeauftragter abstimmen. Die Angaben zu Daten und Fristen entsprechen dem Stand der Software (Feature-Liste, Abschnitte 2, 9, 11 und 16).

## 1. Verantwortlicher

[Name und Anschrift des Betreibers bzw. der Schule]
E-Mail: [datenschutz@…]
Datenschutzbeauftragte/r: [Name, Kontakt – z. B. der Schule bzw. des Schulträgers]

## 2. Zweck

Der Technik-AG Planer dient der Organisation von Technik-AGs an Schulen: Planung von Veranstaltungen (Produktionen), Einteilung der Crew, Termine, Material, Absprachen und Nachweise über geleistete Einsätze. Es gibt keine Werbung, kein Tracking und keine Weitergabe an Dritte zu eigenen Zwecken.

## 3. Welche Daten verarbeitet werden

**Konto:** E-Mail-Adresse, frei wählbarer Name (auch Spitzname), Jahrgangsstufe (nicht bei Lehrkräften), Passwort (nur als Hash), optional Zwei-Faktor-Schlüssel, Rolle je AG, Zeitpunkt der Registrierung.

**Nutzung in der AG:** Einteilungen zu Jobs und Terminen (inkl. Position, Status, Stunden und Korrekturen), „Nicht verfügbar“-Einträge mit optionaler privater Notiz, Fähigkeiten, Board- und Chat-Nachrichten, Lesestand, To-dos, Defektmeldungen, hochgeladene Dateien.

**Technik-Anfragen über den öffentlichen Link (Personen ohne Konto):** Name, E-Mail-Adresse, optional Funktion, Ansprechperson und Telefonnummer, Angaben zur Veranstaltung, optional ein PDF. Zum Schutz vor Missbrauch wird die IP-Adresse kurzzeitig (höchstens eine Stunde) im Zwischenspeicher gezählt, nicht dauerhaft gespeichert.

**Push-Mitteilungen (freiwillig):** je Gerät die vom Browser vergebene Push-Adresse mit Schlüsseln und die Gerätebezeichnung des Browsers.

**Technisch notwendig:** Sitzungs-Cookie (Anmeldung, bis zu 30 Tage), CSRF-Cookie, Server-Logs (IP-Adresse, Zeitpunkt, aufgerufene Seite) für [Anzahl] Tage. Fehlgeschlagene Anmeldeversuche werden kurzzeitig gezählt (Schutz vor Passwort-Raten).

## 4. Rechtsgrundlagen

[Mit der Schule klären, z. B. Art. 6 Abs. 1 lit. e DSGVO i. V. m. dem Schulgesetz des Landes für schulische Veranstaltungen, Art. 6 Abs. 1 lit. a DSGVO (Einwilligung) für freiwillige Funktionen wie Push-Mitteilungen, Art. 6 Abs. 1 lit. f DSGVO für Sicherheit und Missbrauchsschutz. Bei Schülerinnen und Schülern unter 16 ggf. Einwilligung der Eltern.]

## 5. Empfänger und Dienstleister

- **Hosting:** Die App und die Datenbank laufen auf einem eigenen Server [Standort, ggf. Anbieter des Servers/Rechenzentrums].
- **Google (Google Ireland Limited):** Verbindet eine AG ein Google-Konto, werden hochgeladene Dateien im Google Drive dieses Kontos gespeichert und alle Kalendereinträge (Produktionen, Jobs mit eingeteilter Crew, Termine, „Nicht verfügbar: Name“ – ohne private Notiz) in einen Google-Kalender dieses Kontos übertragen. Google kann Daten in Drittländern (u. a. USA) verarbeiten. [Rechtsgrundlage, Auftragsverarbeitung bzw. Nutzungsbedingungen des Google-Kontos, Drittlandübermittlung prüfen.]
- **Google-Kalender-Link (nur auf eigenen Wunsch):** Wählt jemand bei „In privaten Kalender“ den Google Kalender, sendet der Browser Titel, Zeit, Ort, Beschreibung und den Link zum Eintrag an Google, damit der Termin dort vorausgefüllt erscheint. Namen von Mitgliedern setzt die App nicht ein; selbst eingetragene Notizen können jedoch Teil der Beschreibung sein. Ohne diesen Klick findet keine Übermittlung statt.
- **Push-Dienste der Browser-Hersteller** (Google, Mozilla, Apple, Microsoft): Push-Mitteilungen werden verschlüsselt über den Dienst des jeweiligen Browsers zugestellt; der Inhalt ist für den Dienst nicht lesbar.
- **E-Mail-Versand:** Einladungen und „Passwort vergessen“ über [Mail-Anbieter/eigener Mailserver].

## 6. Speicherdauer

| Daten | Dauer |
| --- | --- |
| Konto | bis zur Löschung durch die Person selbst oder den Betreiber; Einsätze und Nachrichten bleiben danach ohne Namen („Ehemaliges Mitglied“) erhalten |
| Gelöschte Produktionen | 7 Tage im Papierkorb, danach endgültig (inkl. Dateien im Drive) |
| Internes Änderungsprotokoll | 7 Tage |
| Erledigte Technik-Anfragen | 180 Tage nach „Erledigt“, danach endgültig (inkl. PDF im Drive) |
| Einladungen (E-Mail-Adresse, Rolle) | bis 30 Tage nach Annahme, Ablauf oder Rückzug |
| Sicherungen (Backups) | 14 Tage [anpassen] |
| Server-Logs | [Anzahl] Tage |

## 7. Rechte der Betroffenen

Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit, Widerspruch und Widerruf erteilter Einwilligungen (Art. 15–21 DSGVO) sowie Beschwerde bei der zuständigen Aufsichtsbehörde [Name der Landesdatenschutzbehörde]. Das eigene Konto lässt sich jederzeit selbst löschen (Einstellungen → Konto löschen); Name und Jahrgangsstufe lassen sich selbst ändern. Anfragen an: [Kontakt].

## 8. Sicherheit

Verschlüsselte Verbindung (HTTPS), Passwörter nur als Hash, optional bzw. auf Wunsch der AG verpflichtend Zwei-Faktor-Anmeldung, strikte Trennung der Daten je AG, Rechte je Rolle, Zugang des Betreibers zum Verwaltungsbereich nur mit Zwei-Faktor-Anmeldung.

Stand: [Datum]
