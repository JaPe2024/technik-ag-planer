# ADR 0020: „In privaten Kalender“ statt .ics-Knöpfen

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Einträge ließen sich nur als .ics-Datei herunterladen. Mitglieder mussten die Datei danach selbst öffnen. Eine Webseite darf nichts ohne Rückfrage in einen privaten Kalender eintragen, der Weg dorthin lässt sich aber verkürzen.

## Entscheidungen

**Auswahl im Bottom-Sheet:** Ein Knopf „In privaten Kalender“ öffnet Google Kalender, Apple Kalender und klein „Datei herunterladen“. Die Reihenfolge richtet sich nach dem User-Agent: iPhone, iPad und Mac zuerst Apple, sonst Google. iPadOS meldet sich als Mac. Die letzte Wahl wird nicht gespeichert.

**Google ohne Datei:** Ein Link auf `calendar.google.com/calendar/render?action=TEMPLATE` füllt den Termin vor, gespeichert wird bei Google. Die Beschreibung wird auf 1000 Zeichen gekürzt, damit der Link nicht zu lang wird.

**Apple über dieselbe Datei:** Der Link liefert die .ics-Datei mit `Content-Disposition: inline`, der Download mit `attachment`. Ein `webcal:`-Link scheidet aus, weil der Kalender die Datei dann ohne Anmeldung in der App abrufen müsste.

**Eine Datenquelle:** Datei und Google-Link entstehen aus demselben `IcsEvent`. Das Feld `internal` erscheint nur in der Datei; dort steht die Crew eines Jobs. So landen keine Namen von Mitgliedern aus der App im Google-Link.

**Produktion als ein Eintrag:** Der Google-Link kann nur einen Termin vorfüllen. Wie die Datei übernimmt er die Produktion als einen Ganztags-Eintrag, die Jobs stehen in der Beschreibung. Wer die Uhrzeiten einzeln braucht, übernimmt die Jobs.

## Folgen

- Übernommen wird eine Kopie, spätere Änderungen kommen nicht an. Dafür bleibt das Abo des Google-Kalenders der AG.
- Beim Tippen auf Google sendet der Browser Titel, Zeit, Ort und Beschreibung an Google. Selbst eingetragene Notizen können Namen enthalten; die Datenschutz-Vorlage weist darauf hin.
- Das Verhalten des Apple-Links in der installierten App und das von Android lässt sich nur am echten Gerät prüfen.
