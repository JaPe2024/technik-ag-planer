# Technik-AG Planer – Feature-Liste

Oct 16, 2026 · @Lennart

Diese Liste beschreibt alle Funktionen des Technik-AG Planers, einer Planungs-App für Technik-AGs an Schulen. Sie ist die verbindliche Spezifikation für die Umsetzung, die der Projektinhaber selbst mit Claude Code durchführt (Vorgehen siehe Abschnitt 15).

## 1. Plattform, Geräte und Navigation

Die App wird als Django-Web-App entwickelt und läuft im Browser auf Handy, Tablet und Computer. Eine Veröffentlichung im App Store bzw. bei Google Play ist eventuell später möglich, gehört aber nicht zum ersten Umfang.

**Technik**

- Web-App auf Basis von Django (Python): Backend, Datenbank und Oberfläche
- Installierbar als App auf dem Home-Bildschirm (PWA) mit Push-Mitteilungen
- Responsives Layout: Handy und Tablet hochkant mit Menüleiste unten, Tablet quer und Computer mit Seitenleiste
- Dunkles, modernes Design (dunkle Grautöne statt reinem Schwarz) mit zwei Blautönen als Akzent (siehe Farben unten); Kategorien und Status farbig
- Oberfläche komplett auf Deutsch
- Ausgelegt auf bis zu 5 AGs und rund 100 Nutzer im ersten Jahr; kein Offline-Modus und kein Datenimport nötig
- Der Quellcode wird öffentlich gestellt (Lizenz siehe Abschnitt 13); Zugangsdaten wie Google- oder Mail-Passwörter stehen nur in der Server-Konfiguration, nie im Code

**Farben**

Das Design ist dunkel und modern: kein reines Schwarz, sondern sehr dunkle Grautöne mit leichtem Blaustich, in Ebenen abgestuft. Akzente kommen aus zwei Blautönen. Kein Logo und kein Name einer Schule oder Organisation in der Oberfläche – schlicht und auf das Nötige reduziert.

| Farbe | Wert (Richtwert) | Einsatz |
| --- | --- | --- |
| Hintergrund | #0F1115 | Seitenhintergrund |
| Fläche | #171A21 | Karten, Seitenleiste, Bottom-Sheets |
| Fläche erhöht | #1F232C | Eingabefelder, Hover, ausgewählte Elemente |
| Linie | #2A2F3A | Rahmen und Trennlinien |
| Dunkelblau | #003397 | Haupt-Buttons, aktiver Menüpunkt, eigene Board-Nachrichten – immer mit heller Schrift |
| Hellblau (Flieder) | #8787FF | Akzente: Links, kleine Überschriften, Badges, Icons, Hervorhebung „heute“ im Kalender |
| Text | #F2F3F5 | Haupttext |
| Text gedämpft | #9AA0AC | Untertitel, Zeitangaben, Platzhalter |

Dunkelblau direkt auf dem dunklen Hintergrund ist zu kontrastarm für Text und Icons (ca. 1,7 : 1). Dort deshalb Hellblau (ca. 6 : 1) oder den hellen Text verwenden. Die Grauwerte sind Richtwerte und werden als Design-Tokens (CSS-Variablen) zentral angelegt. Signalfarben für Status (z. B. grün für „Bestätigt“, gelb/orange für „In Planung“ und „angefragt“) bleiben davon unabhängig.

**Navigation am Computer (Seitenleiste)**

- Großer Button „+ Neu“
- Menüpunkte: Dashboard, Kalender, Produktionen, Material, Board, Einstellungen
- Zähler-Badge am Board für ungelesene Nachrichten
- Unten: Name und E-Mail des angemeldeten Nutzers

**Navigation am Handy (Leiste unten)**

- Home, Kalender, zentraler „+“-Button, Produktionen, Mehr
- „Mehr“ öffnet ein Menü mit Material und Board; Badge mit Anzahl ungelesener Nachrichten auf „Mehr“ und „Board“
- Zahnrad oben rechts öffnet die Einstellungen

**Formulare**

- Erfassen und Bearbeiten als Bottom-Sheet (Handy) mit Schließen-Button und Wischgriff
- Pflichtfelder mit Sternchen markiert

## 2. Konto, Organisation, Rollen und Rechte

Jede Technik-AG ist eine eigene Organisation; ein Konto kann in mehreren Organisationen Mitglied sein.

**Registrierung und Anmeldung**

- Keine offene Registrierung: Konten entstehen nur über Einladungen
- Der Betreiber legt im Django-Admin eine AG (Organisation) an und trägt den Owner mit seiner E-Mail-Adresse ein
- Der Owner erhält automatisch eine Einladungs-E-Mail mit Link, setzt sein Passwort und ist damit freigeschaltet
- Nur der Owner lädt weitere Mitglieder per E-Mail ein und vergibt dabei die Rolle
- Eingeladene setzen über den Link ihren Namen und ihr Passwort; der Name ist frei wählbar (auch ein Spitzname); alle außer Lehrkräften wählen zusätzlich ihre Jahrgangsstufe aus 5, 6, 7, 8, 9, 10, EF, Q1, Q2 (Pflichtfeld, u. a. für die Freistellungsliste); Einladungslinks sind nur einmal gültig und laufen nach einer festen Frist ab (z. B. 7 Tage)
- Offene Einladungen anzeigen, erneut senden oder zurückziehen
- Anmeldung mit E-Mail und Passwort, optional Zwei-Faktor-Anmeldung per Authenticator-App (TOTP)
- „Passwort vergessen“ mit Link zum Zurücksetzen per E-Mail
- Abmelden

**Verwaltung durch den Betreiber (Django-Admin)**

- AGs anlegen, umbenennen, deaktivieren und löschen
- Owner festlegen oder wechseln, Owner-Einladung erneut senden
- Übersicht über alle Konten; Konten sperren oder löschen
- Datenexport einer AG (alle Daten der Organisation, z. B. als Archiv mit CSV- oder JSON-Dateien) – nur im Django-Admin, nicht für Owner oder Mitglieder
- Internes Änderungsprotokoll: wer hat was wann geändert; Einträge werden nach 7 Tagen automatisch gelöscht; nur im Django-Admin einsehbar
- Der Django-Admin ist nur für den Betreiber zugänglich, nicht für Owner oder Mitglieder

**Organisation**

- Organisationen legt nur der Betreiber im Django-Admin an
- Zwischen Organisationen wechseln mit einem Tippen („Wechseln“)
- Daten einer Organisation sehen nur ihre Mitglieder (Mandantentrennung)
- Organisation verwalten: Ownership übertragen, Organisation verlassen oder auflösen
- Schuljahreswechsel: Der Owner löst ihn in den Einstellungen aus; alle Jahrgangsstufen rücken eins hoch (5 → 6 … 10 → EF → Q1 → Q2), aus Q2 wird „Extern“ – Abgänger behalten ihr Konto und ihre Daten
- Verlässt der Owner die Schule ohne Übergabe, bleibt alles unverändert; bei Bedarf wechselt der Betreiber den Owner im Django-Admin
- Löscht ein Mitglied sein Konto, bleiben seine Einsätze, Board-Nachrichten und Einträge in Call Sheets anonymisiert erhalten (z. B. „Ehemaliges Mitglied“)

**Google-Konto der AG (Drive und Kalender)**

- Der Owner verbindet in den Einstellungen ein normales Google-Konto der AG (kein Google Workspace for Education der Schule) über die Google-Anmeldung (OAuth 2.0); dieselbe Verbindung gilt für Google Drive (Dateien) und Google Kalender (Termine, siehe Abschnitt 9)
- Einmalige Einrichtung durch den Betreiber: ein Google-Cloud-Projekt mit OAuth-Zugang und aktivierter Drive- und Kalender-API; die Owner klicken danach nur noch „Mit Google verbinden“. Weil jede selbst gehostete Installation ihr eigenes Projekt braucht, gehört eine Schritt-für-Schritt-Anleitung dafür ins Repository
- Drive-Zugriff nur auf Dateien, die die App selbst anlegt (Scope „drive.file“), kein Vollzugriff auf das Drive
- Kalender-Zugriff gilt bei Google als sensibel. Ohne Verifizierung durch Google sehen Owner beim Verbinden einen Hinweis „nicht verifizierte App“ und können trotzdem fortfahren; das Projekt muss dafür auf „In Produktion“ stehen, denn im Testmodus laufen Verbindungen nach 7 Tagen ab. Eine Verifizierung ist optional und kann später erfolgen
- Alle Dateien, die in der App hochgeladen werden, speichert die App im Google Drive dieses Kontos, nicht auf dem eigenen Server
- Hochgeladene Dateien sind z. B. Anhänge an Produktionen, Dateien zum Material und Fotos bei Defektmeldungen
- Die App legt im Drive einen eigenen Ordner an, mit Unterordnern z. B. je Produktion und für Material
- Mitglieder öffnen und laden Dateien über die App hoch; sie brauchen keinen eigenen Zugang zum Google-Konto
- Verbundenes Konto anzeigen, trennen und neu verbinden – nur durch den Owner
- Ohne verbundenes Google-Konto ist kein Upload möglich; die App zeigt eine verständliche Fehlermeldung (z. B. „Kein Google-Konto verbunden – bitte den Owner fragen“)
- Ist der Speicher im Google Drive voll, schlägt der Upload ebenfalls mit Fehlermeldung fehl (z. B. „Google-Drive-Speicher ist voll“)
- Wird das Konto getrennt oder die Organisation aufgelöst, bleiben alle Dateien im Google Drive erhalten; die App löscht dort nichts. Ausnahme: Löscht jemand in der App eine Datei oder einen Eintrag mit Dateien (z. B. eine alte Produktion), entfernt die App die Datei auch im Drive – bei Produktionen erst nach Ablauf der 7 Tage unter „Kürzlich gelöscht“

**Rollen**

Vorgesehen sind die Rollen Owner, Admin, Lehrkraft und Schüler/in. Owner und Admins sind bewusst Schülerinnen bzw. Schüler – nach dem Prinzip „Schüler lernen von Schülern“; Lehrkräfte haben eine eigene, begleitende Rolle. Die eigene Rolle wird in den Einstellungen als Badge angezeigt. Die Tabelle legt die Rechte verbindlich fest.

| Funktion | Owner | Admin | Lehrkraft | Schüler/in |
| --- | --- | --- | --- | --- |
| Produktionen anlegen und bearbeiten | ja | ja | ja | nein |
| Crew anfragen und einteilen | ja | ja | ja | nein |
| Anfragen annehmen und ablehnen (eigene Jobs) | ja | ja | ja | ja |
| Als Aufsicht eintragen | – | – | ja | – |
| Material anlegen, bearbeiten, archivieren | ja | ja | ja | nein |
| Defekt melden | ja | ja | ja | ja |
| Board lesen und schreiben | ja | ja | ja | ja |
| Mitglieder einladen und Rollen vergeben | ja | nein | nein | nein |
| Kategorien und „Technik anfragen“-Link verwalten | ja | ja | nein | nein |
| Freistellungsliste erstellen | ja | ja | ja | nein |
| Zwei-Faktor-Pflicht, Organisation auflösen | ja | nein | nein | nein |
| Materialsätze anlegen und bearbeiten | ja | ja | nein | nein |
| Nachrichten anderer löschen (Moderation) | ja | ja | ja | nein |
| Einsatzübersicht aller Mitglieder sehen | ja | ja | ja | nur eigene |
| Google-Konto, Stundenraster, Fähigkeiten und Status-Werte verwalten | ja | nein | nein | nein |
| Technik-Anfragen sehen, übernehmen und als erledigt markieren | ja | ja | ja | nein |
| Termine anlegen | ja | ja | ja | nein |
| Eigene „Nicht verfügbar“-Einträge | ja | ja | ja | ja |
| Stunden in der Einsatzübersicht korrigieren | ja | ja | ja | nein |
| Schuljahreswechsel auslösen | ja | nein | nein | nein |

## 3. Dashboard („Was steht an?“)

Die Startseite zeigt auf einen Blick, was als Nächstes ansteht.

- Kopfzeile mit heutigem Datum (z. B. „Freitag, 16. Oktober“), Titel „Was steht an?“ und Name des Nutzers
- Karte „Nächste Produktion“: Name, Datum, Startzeit, nächster Job (z. B. „Aufbau“) und Treffpunkt (z. B. „Bühneneingang“)
- Kachel „Kommende Produktionen“ mit Anzahl, führt zur Produktionsliste
- Kachel „Crew-Anfragen offen“ mit Anzahl, führt zu den offenen Anfragen
- Umschalter „Produktionen“ / „Meine Jobs“
- Liste kommender Produktionen: Datumskachel (Tag und Monat), Name, Zeitraum, Anzahl Jobs, Ort, Status-Badge („Bestätigt“ grün, „In Planung“ orange)
- „Meine Jobs“: nur die Jobs, in denen der Nutzer eingeteilt oder angefragt ist

## 4. Kalender und „Neu anlegen“

Der Kalender zeigt Produktionen, Jobs, Termine und Abwesenheiten der ganzen AG oder nur die eigenen.

**Kalender**

- Ansichten: Monat, Woche, Agenda
- Filter: „Alle“ oder „Meine“
- Buttons „Heute“ und „+ Termin“, Pfeile für vorherigen und nächsten Zeitraum
- Monatsraster Mo–So, Tage außerhalb des Monats abgeblendet, heutiger Tag hervorgehoben
- Einträge als farbige Balken je Tag (Farbe nach Kategorie), mehrtägige Produktionen über mehrere Tage
- Einträge mit Uhrzeit davor (z. B. „14:00 AG-Treffen“), Jobs als „Produktion – Job“, Produktionen in Planung mit Zusatz „(In Planung)“; „Nicht verfügbar“-Einträge grau und gestrichelt umrandet („Nicht verfügbar: Name“)
- Überlauf-Hinweis „+1“, wenn nicht alle Einträge in die Zelle passen
- Tagesdetail unter dem Raster: ausgewählter Tag mit Liste der Einträge oder „Keine Termine an diesem Tag“
- „+ Termin an diesem Tag“ legt direkt einen Termin am gewählten Datum an
- Alle Einträge werden automatisch in den Google Kalender des AG-Kontos übertragen (siehe Abschnitt 9)

**Stundenraster**

- Der Owner legt in den Einstellungen die Unterrichtsstunden der Schule fest: Nummer, Beginn und Ende (z. B. 1. Stunde 8:00–8:45), Pausen dazwischen; das Raster gilt an allen Schultagen gleich
- Zeiten lassen sich überall wahlweise als Uhrzeit oder als Schulstunde eingeben (z. B. „ab der 5. Stunde“) – bei Jobs, Terminen und „Nicht verfügbar“; die App rechnet über das Raster in Uhrzeiten um
- Die Freistellungsliste nennt die betroffenen Schulstunden

**„+ Neu“-Menü**

1. **Termin** – einfacher Termin, z. B. AG-Treffen; auch als wiederkehrende Serie (wöchentlich, alle 2 Wochen, monatlich) mit Enddatum, z. B. bis zum Schuljahresende – einzelne Termine der Serie lassen sich verschieben oder absagen, ohne die ganze Serie zu ändern. Felder: Titel (Pflicht), Datum (Pflicht), Beginn und Ende, Ort, Notizen; optional „Leute einteilen oder anfragen“
2. **Produktion** – Veranstaltung mit Jobs und Crew (siehe Abschnitt 5)
3. **Nicht verfügbar** – Tage oder Zeiträume, an denen man nicht kann (siehe Abschnitt 9); Schülerinnen und Schüler sehen im Menü nur diesen Punkt

## 5. Produktionen, Jobs und Crew

Eine Produktion ist eine Schulveranstaltung (z. B. Schulkonzert, Abiball); sie besteht aus Jobs wie Aufbau, Show und Abbau, für die Crew eingeteilt wird.

**Produktionsliste**

- Bereich „Anfragen“ oben mit Zähler: eingegangene Technik-Anfragen (z. B. „Elternabend · Do., 05.11.2026 · 19:00–21:30 Uhr · Aula · von Frau Muster“), antippbar – sichtbar für Owner, Admins und Lehrkräfte (siehe Abschnitt 6)
- Suche „Produktion suchen …“
- Filter-Chips: Alle plus jede Kategorie (Schulfest, Theater, Konzert, Sonstiges) mit Farbpunkt
- Kommende Produktionen als Karten (Datumskachel, Name, Zeitraum, Anzahl Jobs, Ort, Status)
- „Vergangene Produktionen anzeigen“ ausklappbar, mit Anzahl

**Produktion anlegen und bearbeiten**

- Name der Produktion (Pflicht)
- Kategorie als Chip-Auswahl, mit Link „Kategorien bearbeiten“
- Von / Bis (Datum, vorbelegt mit heute)
- Status: standardmäßig „In Planung“ und „Bestätigt“; weitere Status-Werte (z. B. „Abgesagt“) legt der Owner mit Name und Farbe in den Einstellungen an
- „Ort & Adresse“ ausklappbar
- Notizen
- Bereich „Jobs“ mit „+ Job“
- Eigener Chat für die Produktion ein/aus (siehe Abschnitt 8)
- Entwürfe werden automatisch zwischengespeichert; Buttons „Entwurf verwerfen“ und „Speichern“
- Beim Anlegen erscheint automatisch eine Systemnachricht im Board („Neue Produktion: …“)

**Produktion – Detailansicht**

- Kopf mit Name, Zeitraum und Status als Dropdown zum direkten Ändern
- Buttons „Kopieren“ (Produktion duplizieren) und „Bearbeiten“
- Abschnitt Ort mit Name (z. B. Aula) und „Navigation starten“
- Button „Chat“ öffnet den Chat der Produktion (siehe Abschnitt 8)
- Abschnitt Jobs mit Buttons „Call Sheet gesamt“, „Freistellungsliste“ und „+ Job“; je Job ein Button „Crew“ zum Anfragen und Einteilen und ein Link „Call Sheet (PDF)“
- Abschnitt To-dos: Aufgaben zur Produktion anlegen („+ To-do“) und abhaken
- Abschnitt Dateien: beliebig viele Dateien und Links je Produktion, z. B. Bühnenplan, Patchliste, Ablaufplan; gespeichert im Google Drive der AG im Unterordner der Produktion
- Material, das für die Produktion geplant ist, mit Menge – einzeln oder als ganzer Materialsatz hinzugefügt (siehe Abschnitt 7); Konfliktwarnung, wenn die Menge zusammen mit zeitlich überlappenden Produktionen den Bestand übersteigt – berechnet über den Zeitraum der Produktion (Von–Bis), weil Material der Produktion zugeordnet wird
- Packliste: Sobald Material eingeplant ist, erzeugt die App daraus eine Packliste – als Checkliste zum Abhaken von Ausgabe und Rückgabe und als PDF; die Nutzung ist freiwillig, nichts muss abgehakt werden
- Lehrkräfte lassen sich als Aufsicht eintragen

**Jobs**

- Job mit Name (z. B. Aufbau, Show), Datum, Start- und Endzeit
- Treffpunkt je Job (erscheint auf dem Dashboard)
- Crew-Mitglieder je Job mit Position/Rolle (z. B. FOH, Bühne, Monitor)
- Status je Person: angefragt (orange) oder zugesagt (grün); Person entfernen per „×“
- Call Sheet je Job als PDF

**Crew anfragen und einteilen**

- Schülerinnen und Schüler für Jobs anfragen oder direkt einteilen; Konfliktwarnung, wenn die Person zu dieser Zeit „nicht verfügbar“ ist oder schon in einem anderen Job eingeteilt ist (Einteilen nach Bestätigung trotzdem möglich)
- Anfragen mit einem Tippen annehmen oder ablehnen
- Zähler „Crew-Anfragen offen“ auf dem Dashboard
- Push-Mitteilung bei neuer Anfrage und bei Änderungen

**Fähigkeiten (Skillset)**

- Der Owner legt in den Einstellungen fest, welche Fähigkeiten zur Auswahl stehen (z. B. Licht, Ton, Bühne, Kamera); er kann sie umbenennen, sortieren und löschen
- Jedes Mitglied wählt seine Fähigkeiten selbst aus dieser Liste aus (Einstellungen → „Meine Fähigkeiten“)
- Fähigkeiten erscheinen in der Mitgliederliste und beim Einteilen
- Beim Einteilen lassen sich Mitglieder nach Fähigkeit filtern; die App schlägt passende Personen vor

**Einsatzübersicht**

- Je Mitglied eine Übersicht aller Einsätze: Produktion, Job, Datum und Stunden, mit Summe – die Stunden berechnet die App aus den Job-Zeiten, für die die Person zugesagt war, und aus Terminen, in die sie eingeteilt war (z. B. AG-Treffen); Owner, Admins und Lehrkräfte können die tatsächlichen Stunden je Person korrigieren, etwa wenn der Abbau länger dauert
- Filter nach Zeitraum, z. B. Schuljahr oder Halbjahr
- Export als PDF, z. B. als Grundlage für eine Zeugnisbemerkung oder eine AG-Bescheinigung
- Owner, Admins und Lehrkräfte sehen die Übersicht aller Mitglieder; jedes Mitglied sieht seine eigene

**Löschen**

- Gelöschte Produktionen 7 Tage lang unter „Kürzlich gelöscht“ wiederherstellbar

## 6. Technik anfragen (externer Link)

Lehrkräfte und Schulleitung ohne Konto können über einen Link Technik für eine Veranstaltung anfragen.

- Öffentlicher Link je Organisation, ohne Anmeldung nutzbar
- Link in den Einstellungen aktivieren und deaktivieren; Status wird angezeigt („Link ist aktiv“)
- Einfacher Spam-Schutz (z. B. unsichtbares Feld und Begrenzung der Anfragen pro Stunde)

**Anfrage-Formular**

Das Formular muss auch für Lehrkräfte ohne Technikkenntnisse einfach auszufüllen sein: Alltagssprache, wenige Pflichtfelder, fast alles als Freitext.

| Bereich | Felder | Eingabe |
| --- | --- | --- |
| Wer fragt an | Name, E-Mail-Adresse, Funktion (z. B. Lehrkraft, Schulleitung, SV) | Name und E-Mail Pflicht (die Schule kommuniziert per Mail), Funktion optional, Freitext |
| Was | Name der Veranstaltung, Art | Name als Freitext; Art als Auswahl aus den Kategorien der AG; beides optional |
| Wann | Datum, Beginn und Ende, Aufbau ab / Abbau bis | Datum Pflicht (Datumsauswahl), Zeiten optional |
| Wo | Ort bzw. Raum | Freitext, optional |
| Welche Technik | z. B. Mikrofone, Musik abspielen, Licht, Beamer und Leinwand, Laptop anschließen | einfache Ankreuzliste in Alltagssprache plus Freitext, optional |
| Ablauf | Programm bzw. Ablauf der Veranstaltung | Freitext, Link oder PDF-Upload (Ablage im Google Drive der AG), optional |
| Ansprechperson am Tag | Name, Telefonnummer | Freitext, optional |

**Anfragen bearbeiten**

- Owner, Admins und Lehrkräfte sehen eingegangene Anfragen oben in der Produktionsliste, mit Zähler (gemäß Rechte-Tabelle in Abschnitt 2)
- Beim Öffnen einer Anfrage teilt sich der Bildschirm: auf Tablet quer und Computer links die Anfrage, rechts das Formular „Neue Produktion“; auf dem Handy oben ein Umschalter „Anfrage | Produktion“ zum Hin- und Herwechseln
- Datum und Uhrzeiten werden automatisch in die Produktion übernommen; alle anderen Felder der Anfrage haben einen Kopieren-Button, die Felder der Produktion einen Einfügen-Button
- Die E-Mail-Adresse ist anklickbar und öffnet das Mailprogramm; Rückmeldungen an die Lehrkraft laufen per Mail außerhalb der App
- Es gibt kein Annehmen oder Ablehnen: Ein Button „Erledigt“ entfernt die Anfrage aus der Liste (archiviert), egal ob daraus eine Produktion wurde

## 7. Material

Das Material-Modul verwaltet die Technik der AG mit Kategorien, Bestand und Planung je Produktion.

**Materialliste**

- Alle Materialien mit Kategorie und Bestand
- Suche, Filter nach Kategorie, Anzeige von defektem und archiviertem Material

**Material anlegen**

- Name (Pflicht), z. B. „Lichtpult“
- Kategorie als Chip-Auswahl (z. B. Licht, Audio) mit „Kategorien bearbeiten“; eigene Kategorien für Material, getrennt von Produktions-Kategorien
- Bestand als Zahl, leer = „beliebig“ (unbegrenzt, z. B. Verbrauchsmaterial)
- Notizen, z. B. Lagerort, Zubehör, Besonderheiten
- Links und Dateien (beliebig viele, „+ Link“ und „+ Datei“), z. B. Handbuch, Datenblatt oder Foto; hochgeladene Dateien werden im Google Drive der AG gespeichert

**Material bearbeiten**

- Alle Felder wie beim Anlegen
- Button „Defekt melden“ – mit Menge, kurzer Beschreibung und optional Foto; defekte Geräte werden vom verfügbaren Bestand abgezogen und zählen bei der Konfliktwarnung nicht mit; Status „defekt“ → „in Reparatur“ → „repariert“, danach wieder verfügbar
- Abschnitt „Geplant“: Produktionen, in denen das Material eingeplant ist, mit Zeitraum und Menge (z. B. „Schulkonzert · 18.–19.10.2026 · × 6“); Überbuchungen werden markiert
- „Archivieren“ statt Löschen

**Materialsätze**

- Owner und Admins legen Materialsätze für Aufbauten an, die sich wiederholen, z. B. „Große Audioanlage“ oder „Bühnenlicht Aula“: Name, optional Beschreibung und die enthaltenen Materialien mit Menge
- Beim Planen einer Produktion lässt sich ein ganzer Satz auf einmal auswählen; alle enthaltenen Materialien werden mit ihren Mengen eingeplant
- Danach lassen sich einzelne Positionen für diese Produktion anpassen oder entfernen, ohne den Satz selbst zu ändern
- Konfliktwarnung und Packliste behandeln Material aus einem Satz wie einzeln geplantes Material
- Sätze bearbeiten, kopieren und löschen; Änderungen an einem Satz gelten nur für künftige Planungen, bereits geplante Produktionen bleiben unverändert

## 8. Board

Das Board ist ein gemeinsamer Chat für die ganze AG, ergänzt um automatische Systemmeldungen.

- Nachrichten mit Name des Absenders (farbig), Text und Uhrzeit
- Datumstrenner („Gestern“, „Heute“, „Mi., 14.10.2026“)
- Systemmeldungen mit Info-Symbol, z. B. „Neue Produktion: Theater-Premiere“; Antippen öffnet die jeweilige Produktion – Systemmeldungen gibt es für: neue Produktion; Status, Datum oder Ort einer Produktion geändert; Produktion gelöscht; Job mit offenen Plätzen 3 Tage vorher (z. B. „Aufbau Schulkonzert: noch 2 Plätze frei“); Material defekt gemeldet bzw. wieder verfügbar; neues Mitglied beigetreten
- Eigene Nachrichten rechtsbündig in Dunkelblau, fremde linksbündig in Grau
- Eingabefeld „Nachricht schreiben …“ mit Senden-Button
- Eigene Nachrichten bearbeiten (mit Hinweis „bearbeitet“) und löschen
- Moderation: Lehrkräfte, Admins und Owner können Nachrichten aller Mitglieder löschen
- Menü „…“ oben rechts öffnet – wie „Mehr“ in der Handy-Navigation – die Bereiche Material und Board
- Zähler ungelesener Nachrichten in der Navigation
- Push-Mitteilung bei neuer Nachricht

**Chats je Produktion**

- Jede Produktion kann einen eigenen Chat haben (beim Anlegen oder später aktivierbar)
- Oben im Board eine waagerecht scrollbare Leiste mit runden Kreisen, einer je Produktions-Chat, mit Kategorie-Farbe und Name darunter
- Ein farbiger Ring und ein Zähler zeigen neue Nachrichten an; Chats mit neuen Nachrichten stehen vorne
- Antippen eines Kreises öffnet den Chat; zusätzlich erreichbar direkt aus der Produktion
- Gleiche Funktionen wie im Board: bearbeiten, löschen, Moderation
- Alle Mitglieder können jeden Produktions-Chat lesen und schreiben; Push-Mitteilungen bekommt aber nur, wer in der Produktion eingeteilt ist. 3 Tage nach dem Ende der Produktion verschwindet der Chat aus der Leiste; über die Produktion bleibt er erreichbar

## 9. Nicht verfügbar, Benachrichtigungen, Google-Kalender und PDFs

Diese Funktionen gelten für alle Mitglieder und begleiten Planung und Einteilung.

**Nicht verfügbar**

- Abwesenheiten eintragen – über „+ Neu“ oder Einstellungen → „Nicht verfügbar“
- Ganze Tage oder Zeiträume mit Uhrzeit von–bis (z. B. Di. 8:00–13:00) oder in Schulstunden (z. B. „1.–4. Stunde“), auch über mehrere Tage
- Einträge erscheinen im Kalender
- Beim Einteilen einer Person, die zu dieser Zeit nicht verfügbar ist, zeigt die App eine Konfliktwarnung (siehe Abschnitt 5)

**Push-Mitteilungen**

- Zu Anfragen, Änderungen und Erinnerungen; vor jedem eigenen Job kommt automatisch eine Erinnerung, standardmäßig am Vorabend (z. B. 18 Uhr) mit Job, Uhrzeit und Treffpunkt – der Zeitpunkt lässt sich in den Benachrichtigungs-Einstellungen ändern
- Einstellungen → „Benachrichtigungen“: aktivieren und einzeln einstellen; Benachrichtigungen kommen nur als Push, nicht per E-Mail. E-Mails verschickt die App nur für Einladungen und „Passwort vergessen“, per SMTP – z. B. über ein Postfach der eigenen Domain (noreply@…) oder einen EU-Mailanbieter

**Google-Kalender und ICS-Export**

- Alle Einträge aus dem Kalender der App (Produktionen, Jobs, Termine, Nicht-verfügbar-Einträge) werden automatisch in den Google Kalender des verbundenen AG-Kontos übertragen – in einen eigenen Kalender, den die App dort anlegt
- Übertragen wird alles, was Google Kalender unterstützt: Titel, Datum und Uhrzeit (auch ganztägig und mehrtägig), Ort mit Adresse, Beschreibung (z. B. Notizen, Treffpunkt, Jobs mit eingeteilter Crew, Status), Farbe nach Kategorie und ein Link zurück zum Eintrag in der App
- Jeder Google-Termin speichert unsichtbar die ID des App-Eintrags; darüber werden Änderungen und Löschungen in der App automatisch nachgezogen
- Die Übertragung läuft nur in eine Richtung (App → Google); Änderungen direkt im Google Kalender werden beim nächsten Abgleich überschrieben
- Bilder und Dateien werden nicht in den Kalender kopiert: Die App ordnet sie über die Eintrags-ID zu und zeigt sie nur in der App; optional können sie zusätzlich als Drive-Anhang am Google-Termin hängen
- Ohne verbundenes Google-Konto findet keine Übertragung statt; nach dem Verbinden werden bestehende Einträge nachgeholt
- Wird das Konto getrennt, bleibt der Kalender im Google-Konto bestehen
- Mitglieder können den Google-Kalender der AG über eine Freigabe abonnieren
- Es gibt nur diesen einen Kalender, kein persönliches Abo; stattdessen lässt sich jeder einzelne Eintrag als .ics-Datei exportieren (Button z. B. „In Kalender übernehmen“), passend für Google Kalender, Outlook oder Apple Kalender
- Nicht-verfügbar-Einträge der Mitglieder kommen mit in den AG-Kalender, aber zurückhaltend in Grau (in Google die Farbe „Graphit“) und mit klarem Titel, z. B. „Nicht verfügbar: Emma Schulz“

**PDFs**

- Call Sheet je Job und je Produktion
- Freistellungsliste für die Schule: welche Schüler wann vom Unterricht freigestellt werden müssen, mit Name, Jahrgangsstufe und den betroffenen Schulstunden laut Stundenraster – drucken oder exportieren; zunächst ein eigenes Format (Veranstaltung, Datum, Name, Jahrgangsstufe, betroffene Stunden, Aufsicht führende Lehrkraft), später ggf. an eine Vorlage der Schule angepasst
- Vorschau vor dem Teilen oder Drucken

## 10. Einstellungen

Die Einstellungen sind in fünf Gruppen gegliedert; oben steht die eigene Rolle als Badge.

| Gruppe | Eintrag | Funktion / Untertitel |
| --- | --- | --- |
| Team | Mitglieder | Liste mit Anzahl und Fähigkeiten; einladen und Rollen vergeben nur durch den Owner |
| Team | Organisation verwalten | Ownership übertragen, verlassen oder auflösen |
| Planung | Kategorien | Produktions-Kategorien verwalten und sortieren (Name, Farbe) |
| Planung | Technik anfragen | Öffentlichen Anfrage-Link verwalten, Status „Link ist aktiv“ |
| Planung | Kürzlich gelöscht | Gelöschte Produktionen 7 Tage lang wiederherstellen |
| Planung | Google-Konto | Google-Konto der AG für Drive und Kalender verbinden, Status anzeigen, trennen (nur Owner) |
| Planung | Stundenraster | Unterrichtsstunden mit Beginn und Ende festlegen (nur Owner) |
| Planung | Fähigkeiten | Fähigkeiten zur Auswahl anlegen, umbenennen, sortieren, löschen (nur Owner) |
| Planung | Status-Werte | Status für Produktionen mit Name und Farbe anlegen und sortieren (nur Owner) |
| Planung | Schuljahreswechsel | Alle Jahrgangsstufen um eins erhöhen, Q2 wird „Extern“ (nur Owner) |
| Datenschutz | Zwei-Faktor für alle Mitglieder | Pflicht ein/aus, Standard „Aus – freiwillig je Person“ |
| Für mich | Benachrichtigungen | Push-Mitteilungen aktivieren und einstellen |
| Für mich | Nicht verfügbar | Tage oder Zeiträume, an denen man nicht kann |
| Für mich | Meine Fähigkeiten | Eigene Fähigkeiten aus der Liste des Owners auswählen |
| Für mich | Hilfe & FAQ | Kurze Antworten auf häufige Fragen |
| Für mich | Über die App | Alle Funktionen auf einen Blick |
| Konto | Name und Jahrgangsstufe ändern | Frei wählbarer Anzeigename; Jahrgangsstufe (nicht für Lehrkräfte) |
| Konto | Passwort ändern | Eigenes Passwort neu setzen |
| Konto | Meine Zwei-Faktor-Anmeldung | Status, Einrichtung per Authenticator-App |
| Konto | Konto löschen | Eigenes Konto dauerhaft löschen |
| Konto | Abmelden | Zeigt die E-Mail-Adresse |

## 11. Sicherheit und Datenschutz

Die App speichert nur, was für die Planung nötig ist, und richtet sich an Schulen mit minderjährigen Nutzern.

- Strikte Trennung der Daten je Organisation
- Rollenbasierte Sichtbarkeit: jede Rolle sieht nur, was sie braucht
- Zwei-Faktor-Anmeldung (TOTP), auf Wunsch Pflicht für alle Mitglieder
- Keine Werbung, kein Tracking
- Gelöschte Produktionen nach 7 Tagen endgültig entfernt
- Eigenes Konto selbst löschen
- Hosting privat und lokal auf einem eigenen Server (App und Datenbank), nicht bei einem Cloud-Anbieter; der Server muss trotzdem über eine eigene Domain mit HTTPS aus dem Internet erreichbar sein – nötig für den Zugriff vom Handy, Push-Mitteilungen und die Google-Anmeldung; Auslieferung z. B. als Docker-Setup mit Anleitung für Installation, Updates und Backups
- Rechtstexte: Datenschutzerklärung, Nutzungsbedingungen, Impressum – werden nach der Entwicklung und vor dem Start erstellt
- Datensparsam: Namen sind frei wählbar; die App fragt nur E-Mail-Adresse, Name und Jahrgangsstufe ab
- Organisatorisch, nicht Teil der Entwicklung: Einsatz der App und Nutzung von Google vor dem Start mit Schulleitung und Datenschutzbeauftragter der Schule abstimmen; klären, ob für Schülerinnen und Schüler unter 16 eine Einwilligung der Eltern nötig ist

## 12. Landingpage und Kosten

**Landingpage**

- Hero mit Claim, Button „Zur App“, Hinweis, dass Konten nur auf Einladung vergeben werden
- Funktionsübersicht mit Screenshots für Handy und Computer
- Abschnitte Geräte, Sicherheit und Datenschutz, Kosten
- „So startest du“ in drei Schritten: Einladung annehmen, Passwort setzen, Team einladen
- Fußzeile mit Impressum, Datenschutz, Nutzungsbedingungen

**Kosten**

- Alle Funktionen kostenlos, kein Bezahlmodell

## 13. Lizenz

Der Quellcode wird öffentlich unter der **PolyForm Noncommercial License 1.0.0** veröffentlicht ([Lizenztext](https://polyformproject.org/licenses/noncommercial/1.0.0/)).

- Erlaubt: Code ansehen, nutzen und ändern für private und nicht-kommerzielle Zwecke; Schulen und andere Bildungseinrichtungen sind ausdrücklich eingeschlossen
- Nicht erlaubt: jede kommerzielle Nutzung, z. B. die App als bezahlten Dienst anbieten oder verkaufen
- Änderungen müssen nicht veröffentlicht werden
- Bezeichnung nach außen: „quelloffen“ (source-available), nicht „Open Source“, weil kommerzielle Nutzung ausgeschlossen ist
- Die Lizenzdatei (LICENSE) liegt im Hauptverzeichnis des Repositorys
- Der Code wird vom Projektinhaber selbst mit Unterstützung von Claude Code entwickelt; der Projektinhaber legt die Lizenz fest und kann bei Bedarf einzelnen Dritten gesondert eine kommerzielle Nutzung erlauben
- Beiträge Dritter (Pull Requests) werden nur angenommen, wenn die beitragende Person zustimmt, dass ihr Beitrag unter denselben Bedingungen genutzt und gesondert lizenziert werden darf (Zustimmung in der Pull-Request-Vorlage)

## 14. Repository-Struktur (Monorepo)

Code, Deployment, Dokumentation und Organisation liegen gemeinsam in einem Git-Repository `technik-ag-planer`. Die Struktur ist ein Vorschlag und darf bei der Umsetzung begründet angepasst werden (Entscheidung als ADR in `docs/architektur/` festhalten).

```
technik-ag-planer/
├── README.md                  Überblick, Schnellstart, Links in docs/
├── CLAUDE.md                  Projektregeln für Claude Code (siehe Abschnitt 15)
├── LICENSE                    PolyForm Noncommercial 1.0.0
├── CHANGELOG.md               Versionsverlauf (auch in der App verlinkt)
├── Makefile                   Kurzbefehle: make dev, make test, make lint
├── .env.example               Alle Konfigurationswerte ohne echte Geheimnisse
├── .gitignore / .editorconfig
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml             Linting und Tests bei jedem Push und Pull Request
│   │   └── release.yml        Docker-Image bauen und bei Versions-Tag veröffentlichen
│   ├── ISSUE_TEMPLATE/        Vorlagen für Fehler und Wünsche
│   └── pull_request_template.md
│
├── app/                       Django-Projekt
│   ├── manage.py
│   ├── pyproject.toml         Abhängigkeiten und Tool-Konfiguration
│   ├── config/                settings (base, dev, prod), urls, wsgi/asgi, Hintergrund-Tasks
│   ├── apps/
│   │   ├── accounts/          Konten, Einladungen, Login, 2FA, Jahrgangsstufe
│   │   ├── organizations/     AGs, Rollen und Rechte, Schuljahreswechsel, Einstellungen
│   │   ├── productions/       Produktionen, Jobs, Crew, To-dos, Status-Werte, Kategorien, Fähigkeiten
│   │   ├── scheduling/        Termine, Serien, Nicht verfügbar, Stundenraster, ICS-Export
│   │   ├── inquiries/         Technik-Anfragen über den öffentlichen Link
│   │   ├── inventory/         Material, Materialsätze, Defekte, Packliste
│   │   ├── board/             Board, Produktions-Chats, Systemmeldungen
│   │   ├── notifications/     Push-Mitteilungen, Erinnerungen, E-Mails (Einladung, Passwort)
│   │   ├── google_sync/       Google-Anmeldung, Drive-Ablage, Kalender-Übertragung
│   │   ├── documents/         PDFs: Call Sheet, Freistellungsliste, Einsatzübersicht, Packliste
│   │   └── audit/             Internes Änderungsprotokoll (7 Tage)
│   ├── templates/             HTML-Vorlagen
│   ├── static/                CSS, JavaScript, Icons, Web-App-Manifest, Service Worker
│   ├── locale/de/             Texte der Oberfläche
│   └── tests/                 Übergreifende Tests (zusätzlich Tests je App)
│
├── deploy/
│   ├── Dockerfile
│   ├── docker-compose.yml     Betrieb: Web, Worker, Datenbank, Cache, Webserver
│   ├── docker-compose.dev.yml Entwicklung mit Live-Reload und Test-Mailserver
│   ├── caddy/Caddyfile        Webserver mit automatischem HTTPS
│   └── backup/                Skripte für Sicherung und Wiederherstellung
│
├── docs/
│   ├── feature-liste.md       Diese Feature-Liste
│   ├── installation/          Server einrichten, Google-Cloud-Projekt, Mail (SMTP), Updates, Backups
│   ├── architektur/           Überblick und Entscheidungen (ADRs, z. B. „Warum Django“)
│   ├── betrieb/               Django-Admin: AGs und Owner anlegen, Datenexport, Protokoll
│   ├── handbuch/              Anleitungen für Owner und Mitglieder, Inhalte für „Hilfe & FAQ“
│   └── rechtliches/           Vorlagen für Datenschutzerklärung, Nutzungsbedingungen, Impressum
│
└── scripts/                   Hilfsskripte, z. B. Entwicklungsumgebung einrichten, Beispieldaten
```

**Dienste im Betrieb (docker-compose.yml)**

| Dienst | Aufgabe |
| --- | --- |
| web | Django-App (z. B. mit Gunicorn) |
| worker | Hintergrundaufgaben: Push-Erinnerungen, Google-Kalender-Abgleich, Systemmeldungen, Aufräumen nach 3 bzw. 7 Tagen |
| db | PostgreSQL-Datenbank |
| cache | Redis für Warteschlange und Cache |
| caddy | Webserver mit automatischem HTTPS-Zertifikat für die eigene Domain |

**Arbeitsweise**

- Hauptzweig `main` ist immer lauffähig; Änderungen kommen über Pull Requests mit grüner CI
- Versionen nach Semantic Versioning (z. B. 1.2.0) mit Git-Tag; jeder Tag erzeugt ein Docker-Image und einen Eintrag im CHANGELOG
- Geheimnisse (Datenbank-Passwort, Google-Zugangsdaten, Mail-Zugang, Push-Schlüssel) stehen nur in der `.env` auf dem Server, nie im Repository
- Updates auf dem Server: neues Image ziehen, Container neu starten, Datenbank-Migrationen laufen automatisch

## 15. Umsetzung mit Claude Code

Der Projektinhaber setzt die App selbst mit Claude Code um. Diese Feature-Liste liegt als `docs/feature-liste.md` im Repository und ist die Referenz für alle Meilensteine. Gebaut wird in Etappen, nicht in einem Durchlauf.

**CLAUDE.md**

Im Hauptverzeichnis liegt eine kurze `CLAUDE.md`, die Claude Code bei jeder Sitzung automatisch liest. Sie enthält nur die dauerhaft gültigen Regeln, keine Kopie der Feature-Liste:

- Stack: Django, PostgreSQL, Redis, Docker, Caddy; Projektstruktur laut Abschnitt 14
- Oberfläche komplett auf Deutsch; Farben ausschließlich über die Design-Tokens aus Abschnitt 1
- Mandantentrennung: Jede Abfrage wird nach Organisation gefiltert, jede View prüft Rolle und Recht laut Rechte-Tabelle (Abschnitt 2)
- Keine Geheimnisse im Code, nur in `.env`
- Jede neue Funktion bekommt Tests; `make test` und `make lint` müssen grün sein
- Verweis auf `docs/feature-liste.md` und den aktuellen Meilenstein

**Ablauf je Meilenstein**

1. Neuen Branch anlegen
2. Claude Code im Plan-Modus den betreffenden Abschnitt der Feature-Liste lesen und einen Umsetzungsplan vorschlagen lassen; Plan prüfen und freigeben
3. Umsetzen lassen, inklusive Tests und Migrationen
4. Selbst lokal durchklicken, auch auf dem Handy
5. Pull Request mit grüner CI, dann in `main` übernehmen
6. Offene Punkte und Abweichungen in der Feature-Liste bzw. als ADR festhalten

**Meilensteine**

| Nr. | Meilenstein | Inhalt (Abschnitte) |
| --- | --- | --- |
| 1 | Grundgerüst | Django-Projekt, Docker-Setup (dev und prod), CI, Makefile, Grundlayout mit Seitenleiste und Handy-Navigation, Design-Tokens (1, 14) |
| 2 | Konten und Organisationen | Einladungen, Login, Passwort vergessen, 2FA, Jahrgangsstufe, Organisationen, Rollen und Rechte, Mandantentrennung mit Tests, Django-Admin, Änderungsprotokoll (2, 11) |
| 3 | Produktionen | Produktionen, Jobs, Crew, Kategorien, Status-Werte, To-dos, Kopieren, „Kürzlich gelöscht“, Dashboard (3, 5) |
| 4 | Kalender und Zeiten | Kalenderansichten, Termine und Serien, Stundenraster, „Nicht verfügbar“, Konfliktwarnungen, ICS-Export (4, 9) |
| 5 | Board | Board, Systemmeldungen, Produktions-Chats, Moderation, ungelesene Nachrichten (8) |
| 6 | Material | Material, Defekte, Materialsätze, Bestandsplanung mit Konfliktwarnung, Packliste (7) |
| 7 | Technik-Anfragen | Öffentlicher Link, Anfrage-Formular, Spam-Schutz, geteilte Ansicht Anfrage/Produktion (6) |
| 8 | PDFs | Call Sheets, Freistellungsliste, Packliste, Einsatzübersicht als PDF mit Vorschau (9) |
| 9 | Team-Funktionen | Fähigkeiten, Einsatzübersicht mit Stundenkorrektur, Schuljahreswechsel, Konto löschen mit Anonymisierung (2, 5) |
| 10 | Google-Anbindung | OAuth-Verbindung, Drive-Ablage, Kalender-Übertragung, Anleitung für das Google-Cloud-Projekt (2, 9) |
| 11 | PWA und Push | Web-App-Manifest, Service Worker, Web Push, Erinnerungen, Benachrichtigungs-Einstellungen (1, 9) |
| 12 | Abschluss | Einstellungen vollständig, Hilfe & FAQ, Landingpage, Installations- und Betriebsdoku, Sicherheits-Review (10, 12, 14) |

**Hinweise zu den schwierigen Teilen**

- Die Mandantentrennung (Meilenstein 2) ist das Fundament; Tests, die prüfen, dass eine AG nie Daten einer anderen sieht, entstehen dort zuerst und laufen danach bei jeder Änderung mit
- Die Google-Anbindung (Meilenstein 10) wird bewusst spät gebaut und mit einem echten Google-Konto getestet
- Push-Mitteilungen früh auf einem echten iPhone ausprobieren: Web Push funktioniert dort nur, wenn die App auf dem Home-Bildschirm installiert ist
- Vor dem Start einen gezielten Sicherheits-Review durchführen (Rechteprüfung in jeder View, Mandantentrennung, öffentlicher Anfrage-Link); idealerweise schaut zusätzlich eine erfahrene Person drüber, weil die App von Minderjährigen genutzt wird

## 16. Umsetzungsstand und Entscheidungen

Dieser Abschnitt wird nach jedem Meilenstein fortgeschrieben (Schritt 6 im Ablauf oben). Die Abschnitte 1–15 bleiben die Spezifikation; hier steht, was davon umgesetzt ist und wo bewusst ergänzt oder abgewichen wurde.

**Stand der Meilensteine**

| Nr. | Meilenstein | Stand | Pull Request |
| --- | --- | --- | --- |
| 1 | Grundgerüst | fertig | #1 |
| 2 | Konten und Organisationen | fertig | #2 |
| 3 | Produktionen | fertig | #3, #4 |
| 4 | Kalender und Zeiten | fertig | #5 |
| 5 | Board | fertig | #7 |
| 6 | Material | fertig | #8 |
| 7 | Technik-Anfragen | fertig | #9 |
| 8 | PDFs | fertig (Einsatzübersicht-PDF in M9) | #10 |
| 9 | Team-Funktionen | fertig | #11 |
| 10 | Google-Anbindung | fertig (echter Test mit Google-Konto steht aus) | #12 |
| 11 | PWA und Push | fertig (Test auf echten Handys steht aus) | #13 |
| 12 | Abschluss | fertig | #14 |
| – | Wartung 1: Termin-Erinnerungen, Einladungen aufräumen | fertig | #15 |

**Ergänzungen und Abweichungen**

| Bereich | Entscheidung | Begründung | Festgehalten in |
| --- | --- | --- | --- |
| Struktur | Zusätzliche App `apps/core/` für Grundlayout, Navigation, Platzhalter und Health-Check | Gemeinsames gehört in keine Fach-App | ADR 0003 |
| Mitglieder | Der Owner kann Mitglieder aus der AG entfernen | Sonst bliebe nur das Sperren des ganzen Kontos durch den Betreiber | ADR 0004 |
| 2FA | Keine Wiederherstellungscodes; bei verlorenem Handy setzt der Betreiber die 2FA im Django-Admin zurück | Einfacher für Schülerinnen und Schüler | ADR 0004 |
| Django-Admin | Im Betrieb nur mit bestätigter Zwei-Faktor-Anmeldung | Zugang zu allen Daten aller AGs | ADR 0004, `docs/betrieb/django-admin.md` |
| Ownership | Lehrkräfte können nicht Owner werden | „Owner und Admins sind bewusst Schülerinnen bzw. Schüler“ (Abschnitt 2) | ADR 0004 |
| Farben | Kategorien und Status wählen aus einer festen Palette mit 12 Farben, keine freie Farbwahl | Kontrast auf dunklem Grund, alle Farben als Design-Tokens, eindeutige Zuordnung zu Google-Kalender-Farben | ADR 0005 |
| Status | „In Planung“ und „Bestätigt“ sind System-Status: umbenennbar, nicht löschbar. Wird ein eigener Status gelöscht, fallen seine Produktionen auf „In Planung“ zurück | Kalender und Dashboard brauchen sie | ADR 0005 |
| To-dos | Alle Mitglieder dürfen To-dos anlegen, abhaken und löschen | Entscheidung des Projektinhabers (die Rechte-Tabelle regelt To-dos nicht) | ADR 0005 |
| Crew | Ablehnen einer Anfrage entfernt den Eintrag | Status je Person ist laut Abschnitt 5 nur „angefragt“ oder „zugesagt“ | ADR 0005 |
| Entwürfe | Entwürfe werden im Browser gespeichert (nicht auf dem Server) | Daten bleiben auf dem Gerät | ADR 0005 |
| Serien | Eine Serie erzeugt einzelne Termine; Rhythmus und Enddatum lassen sich nachträglich nicht ändern (stattdessen „alle folgenden“ löschen und neu anlegen) | Einzeln geänderte Termine bleiben verlässlich erhalten, passt zu einzelnen Google-Terminen | ADR 0006 |
| Termine | Abgesagte Serientermine bleiben durchgestrichen sichtbar; Termine ohne Uhrzeit sind ganztägig; Termine haben die Akzentfarbe | Absagen sollen auffallen; Termine haben keine Kategorie | ADR 0006 |
| Nicht verfügbar | Von–Bis ist ein durchgehender Zeitraum (z. B. Di. 8:00 bis Mi. 13:00) | Einfach einzugeben, eindeutig für Konfliktwarnungen | ADR 0006 |
| Board | Aktualisierung alle 10 Sekunden (Polling) statt WebSockets; Änderungen und Löschungen anderer erscheinen nach dem Neuladen | Keine zusätzlichen Dienste im Betrieb | ADR 0007 |
| Board | Der Zähler in der Navigation zählt Board und die Chats eigener Produktionen (Crew oder Aufsicht); die Chat-Leiste zeigt alle | Dieselbe Regel wie für Push-Mitteilungen | ADR 0007 |
| Board | Zusätzliche Systemmeldung „Produktion wiederhergestellt“; Systemmeldungen kann nur die Moderation löschen | Löschen wird sonst nie zurückgenommen | ADR 0007 |
| Jobs | Neues optionales Feld „Benötigte Personen“; die Detailansicht zeigt „x von y besetzt“ | Grundlage für „noch X Plätze frei“ (Entscheidung des Projektinhabers) | ADR 0007 |
| Board | Absendernamen in einer festen Palette-Farbe je Konto | Wiedererkennbar ohne eigene Farbwahl | ADR 0007 |
| Material | Konfliktwarnung nach Spitzenbedarf je Tag über alle nicht gelöschten Produktionen (unabhängig vom Status); „Trotzdem einplanen“ möglich | Nacheinander liegende Produktionen brauchen Material nicht gleichzeitig; eigene Status kann die App nicht deuten | ADR 0008 |
| Material | Materialsätze werden beim Einplanen kopiert; schon geplantes Material wird um die Menge erhöht; archiviertes Material wird übersprungen | „Änderungen an einem Satz gelten nur für künftige Planungen“ (Abschnitt 7) | ADR 0008 |
| Material | Material-Kategorien verwalten Owner und Admins (wie Produktions-Kategorien); die Packliste dürfen alle abhaken | Die Rechte-Tabelle nennt nur „Kategorien“ bzw. regelt die Packliste nicht | ADR 0008 |
| Material | Dateien und Fotos (Material, Defektmeldung) erst mit der Google-Drive-Anbindung (M10); bis dahin Links | Uploads landen laut Abschnitt 2 nur im Drive der AG | ADR 0008 |
| Material | „Produktion kopieren“ übernimmt das geplante Material (ohne Packlisten-Haken) | Wiederkehrende Veranstaltungen brauchen meist dieselbe Technik | ADR 0008 |
| Anfragen | Token des Anfrage-Links im Klartext gespeichert; unbekannte und deaktivierte Links zeigen dieselbe Seite | Der Link muss immer wieder angezeigt werden; nicht erkennbar, ob ein Token existiert | ADR 0009 |
| Anfragen | Spam-Schutz: unsichtbares Feld, höchstens 5 Anfragen pro Stunde je IP und 30 je Link | „Einfacher Spam-Schutz“ (Abschnitt 6) ohne Captcha | ADR 0009 |
| Anfragen | Uhrzeiten werden als vorgeschlagene Jobs übernommen (Aufbau, Veranstaltung, Abbau) | Eine Produktion selbst hat keine Uhrzeiten | ADR 0009 |
| Anfragen | Erledigte Anfragen werden nach 180 Tagen endgültig gelöscht | Kontaktdaten von Personen ohne Konto; Datensparsamkeit (Abschnitt 11) | ADR 0009 |
| PDFs | Erzeugung mit WeasyPrint aus denselben Templates wie die Vorschau; neue App `apps/documents/` ohne eigene Daten; Druck-Tokens für weißes Papier | Kein zusätzlicher Dienst, Vorschau und PDF stimmen überein | ADR 0010 |
| PDFs | Call Sheets und Packliste als PDF für alle Mitglieder; Freistellungsliste laut Rechte-Tabelle | Die Rechte-Tabelle regelt Call Sheets und Packliste nicht; die Crew braucht ihr Call Sheet | ADR 0010 |
| PDFs | Freistellungsliste: nur zugesagte Crew ohne Lehrkräfte und „Extern“, eine Zeile je Person und Tag, ohne Wochenenden | Wer nur angefragt ist, ist nicht sicher dabei; Lehrkräfte und Externe werden nicht freigestellt | ADR 0010 |
| PDFs | Einsatzübersicht als PDF erst in M9 | Die Einsatzübersicht selbst entsteht erst in M9 (Abschnitt 15) | ADR 0010 |
| Konto löschen | Konten werden endgültig gelöscht; Einsätze und Termin-Teilnahmen bleiben mit leerer Mitgliedschaft als „Ehemaliges Mitglied“ erhalten – auch beim Entfernen eines Mitglieds und beim Verlassen der AG. Owner übertragen vorher die Ownership | Keine personenbezogenen Reste; vorher löschte das Entfernen alle Einsätze mit | ADR 0011 |
| Einsatzübersicht | Zählt zugesagte Jobs und Termine bis heute; Korrektur je Einsatz; Schuljahr 1.8.–31.7., 2. Halbjahr ab 1.2. | Nachweis geleisteter Einsätze, z. B. für eine AG-Bescheinigung | ADR 0011 |
| Fähigkeiten | Vorschläge beim Einteilen: freie Mitglieder mit der Fähigkeit, wer im Schuljahr am wenigsten eingesetzt war zuerst | Arbeit gleichmäßig verteilen | ADR 0011 |
| Schuljahreswechsel | Je AG und je Konto höchstens einmal in 180 Tagen; Vorschau vor dem Auslösen | Konten in mehreren AGs nicht doppelt hochstufen | ADR 0011 |
| Google | Nur die Scopes `drive.file` und `calendar.app.created`; den Kalender gibt der Owner in Google selbst frei, die App zeigt den Abo-Link | So wenig Zugriff auf das Google-Konto wie möglich | ADR 0012 |
| Google | Kalender-Übertragung als Gesamtvergleich (gebündelt nach Änderungen, nach dem Verbinden und nachts) statt einzelner Änderungen | Robust gegen verpasste Änderungen; Änderungen in Google werden überschrieben (Abschnitt 9) | ADR 0012 |
| Google | Refresh-Token verschlüsselt gespeichert (Schlüssel aus `DJANGO_SECRET_KEY`) | Zugang zum Google-Konto der AG | ADR 0012 |
| Dateien | Produktionen bekommen den Abschnitt „Dateien“ (Drive-Dateien und Links); Dateien und Links verwalten, wer Produktionen bearbeiten darf; „Kopieren“ übernimmt nur Links | Die Rechte-Tabelle regelt Dateien nicht; Drive-Dateien gehören zur Produktion | ADR 0012 |
| Dateien | Browser zeigt nur Fotos und PDFs direkt an, alles andere wird heruntergeladen; Anfrage-Formular nimmt nur echte PDFs bis 10 MB | Hochgeladene Dateien dürfen nie als Seite der App laufen; öffentliches Formular | ADR 0012 |
| Organisation | „Organisation auflösen“ funktioniert jetzt auch mit Produktionen (Status-Schutz `RESTRICT` statt `PROTECT`) | Fehler aus M3 | ADR 0012 |
| PWA | Service Worker nur für Push, kein Zwischenspeichern; App-Icon in drei Entwürfen, voreingestellt „Fader“ | Kein Offline-Modus (Abschnitt 1); schlicht ohne Logo | ADR 0013 |
| Push | Abo je Gerät, Einstellungen je Konto (für alle AGs); jede Art einzeln abschaltbar; wer etwas auslöst, bekommt keine Mitteilung | Ein Handy gehört einer Person; keine Mitteilung über eigene Änderungen | ADR 0013 |
| Push | Erinnerung standardmäßig am Vorabend um 18 Uhr, alternativ einige Stunden vorher; bei verschobenem Job erneut | Abschnitt 9 | ADR 0013 |
| Push | Board-Nachrichten an alle, Chat-Nachrichten an Eingeteilte und Aufsicht | Regel wie der Zähler in der Navigation | ADR 0013 |
| Startseite | Nicht Angemeldete sehen unter `/` die Landingpage, Angemeldete das Dashboard; Screenshots automatisch aus den Beispieldaten | Gleiche Startadresse für die installierte App | ADR 0014 |
| Rechtliches | Impressum, Datenschutz, Nutzungsbedingungen trägt der Betreiber im Django-Admin ein; Vorlagen in `docs/rechtliches/` (ohne Rechtsberatung) | Jede Installation hat einen eigenen Betreiber | ADR 0014 |
| Sicherheit | Content-Security-Policy ohne `unsafe-inline`; Test ordnet jede View als öffentlich, Konto-View oder AG-geprüft ein; Push nur an Push-Dienste der Browser; Anfragen am Proxy höchstens 30 MB | Ergebnis des Sicherheits-Reviews (`docs/sicherheit/review-2026-10.md`) | ADR 0014 |
| Betrieb | Backup-Skripte für Datenbank und `.env` (14 Tage), Dateien liegen im Drive der AGs | Abschnitt 14 | ADR 0014 |
| Betrieb | Optionale Ergänzung für den Betrieb hinter einem vorgeschalteten Reverse Proxy: Caddy spricht nur HTTP und glaubt Weiterleitungs-Header nur von `TRUSTED_PROXY` | Server ohne eigene öffentliche Adresse; sonst Weiterleitungsschleife und falsche Besucher-Adressen | ADR 0016 |
| Push | Erinnerungen auch vor zugesagten Terminen mit Uhrzeit (gleiche Einstellungen wie bei Jobs) | Idee aus Abschnitt 16 | ADR 0015 |
| Datenschutz | Erledigte Einladungen (abgelaufen, zurückgezogen, angenommen) werden nach 30 Tagen gelöscht | Datensparsamkeit (Abschnitt 11) | ADR 0015 |
| Google | Kein Drive-Anhang am Google-Termin; der Termin verlinkt in die App | Dateien liegen privat im Drive der AG – Abonnenten könnten Anhänge nicht öffnen | ADR 0015 |
| Entwicklung | Beispielkonten `owner@example.org`, `lehrer@…`, `schueler@…` …, Passwort jeweils der Name vor dem @ (M6–M11 mit Login ohne @; seit M12 wieder E-Mail-Eingabe) | Schneller durchklicken (Entscheidung des Projektinhabers) | README |
| Repository | Kein `CONTRIBUTING.md` und kein `SECURITY.md`: Die Zustimmung zur Lizenz steht in der Pull-Request-Vorlage, Sicherheitslücken werden privat über GitHub gemeldet | Entscheidung des Projektinhabers, weniger Dateien | Abschnitt 13 |

**Vor dem Start**

Alle Meilensteine sind umgesetzt. Vor dem Einsatz an der Schule stehen noch aus:

- Echter Durchlauf der Google-Anbindung mit einem Google-Cloud-Projekt und einem Google-Konto der AG (`docs/installation/google-cloud.md`); bisher nur gegen eine Attrappe getestet
- Test auf echten Handys über HTTPS (Android und iPhone mit App vom Home-Bildschirm): Installation, Icon und Vollbild, Push aktivieren, Test-Mitteilung, Crew-Anfrage; App-Icon auswählen (`docs/design/app-icon/`)
- Rechtstexte vervollständigen und im Django-Admin eintragen (`docs/rechtliches/`)
- Einsatz der App und Nutzung von Google mit Schulleitung und Datenschutzbeauftragter abstimmen; klären, ob für Schülerinnen und Schüler unter 16 eine Einwilligung der Eltern nötig ist (Abschnitt 11)
- Sicherheits-Review durch eine erfahrene Person (Bericht: `docs/sicherheit/review-2026-10.md`)
- Server einrichten mit Backups (cron) und Kopie außer Haus (`docs/betrieb/README.md`); erste Version taggen (`v1.0.0`)

**Ideen für später**

- Freistellungsliste an eine Vorlage der Schule anpassen (Abschnitt 9) – sobald die Vorlage vorliegt
