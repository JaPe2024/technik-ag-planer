# ADR 0019: Kalender zeigt Produktion und Jobs nicht doppelt

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Der Kalender zeigte an einem Tag den Ganztags-Eintrag der Produktion und zusätzlich jeden ihrer Jobs. Beim Testen wirkte das wie doppelte Termine, obwohl es nur eine Produktion gab. Ein erster Versuch fasste die Jobs im Monatsraster zu einem Balken zusammen. Einzelne Jobs erwiesen sich aber als nützlicher.

## Entscheidungen

**Zusammenfassung nur in der Anzeige:** `calendar_entries` liefert weiter alle Einträge. `without_covered_productions` in `apps/scheduling/calendar.py` bereitet sie für die Ansichten auf.

**In allen Ansichten gilt dieselbe Regel:** Die Jobs bleiben einzeln sichtbar. Der Eintrag der Produktion entfällt an Tagen mit Jobs und bleibt an Tagen ohne Job, zum Beispiel bei mehrtägigen Produktionen.

## Folgen

- Mit dem Filter „Meine“ zählen nur die eigenen Jobs. An Tagen ohne eigenen Job bleibt der Eintrag der Produktion stehen, wenn man in ihr eingeteilt ist.
- Die `.ics`-Datei der ganzen Produktion bleibt auf der Produktionsseite verfügbar. In der Tagesliste steht an Tagen mit Jobs nur noch die des jeweiligen Jobs.
