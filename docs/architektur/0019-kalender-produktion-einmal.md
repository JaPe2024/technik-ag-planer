# ADR 0019: Kalender zeigt eine Produktion je Tag nur einmal

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Der Kalender zeigte an einem Tag den Ganztags-Eintrag der Produktion und zusätzlich jeden ihrer Jobs. Beim Testen wirkte das wie doppelte Termine, obwohl es nur eine Produktion gab.

## Entscheidungen

**Zusammenfassung nur in der Anzeige:** `calendar_entries` liefert weiter alle Einträge. `without_covered_productions` und `month_bars` in `apps/scheduling/calendar.py` bereiten sie für die Ansichten auf.

**Monatsraster:** ein Balken je Produktion und Tag, mit der frühesten Job-Uhrzeit und dem Namen der Produktion.

**Woche, Agenda, Tagesliste:** Die Jobs bleiben einzeln sichtbar, weil dort ihre Zeiten zählen. Der Eintrag der Produktion entfällt an Tagen mit Jobs und bleibt an Tagen ohne Job, zum Beispiel bei mehrtägigen Produktionen.

## Folgen

- Mit dem Filter „Meine“ zählen nur die eigenen Jobs, die Uhrzeit im Balken ist dann die des frühesten eigenen Jobs.
- Der Link der Produktion führt weiterhin über die Job-Einträge zur Produktion. Die `.ics`-Datei für die ganze Produktion bleibt auf der Produktionsseite verfügbar, in der Tagesliste steht an Tagen mit Jobs nur noch die des Jobs.
