# ADR 0021: Unterseite „AG anpassen“ und ehrlicher Google-Status

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Die Einstellungen waren auf dem Handy mehrere Bildschirme lang, und was je AG einstellbar ist, lag verstreut. Außerdem galt eine Google-Verbindung als „verbunden“, sobald ein Token gespeichert war, auch wenn der Abgleich längst scheiterte. Beim endgültigen Löschen einer Produktion blieb ihr leerer Ordner im Drive liegen.

## Entscheidungen

**Eigene Unterseite:** `organizations:customize` sammelt alle AG-Einstellungen nach Bereichen (`CUSTOMIZE_GROUPS`). Die Rechte der Zielseiten bleiben unverändert, jede Rolle sieht nur ihre Einträge. Wer dort nichts sieht, bekommt weder die Zeile noch die Seite. Unterseiten führen zurück zu „AG anpassen“.

**Ganze Zeile als Link:** Die Zeile ist ein echtes `<a>` statt eines darübergelegten Klickbereichs. Das ist einfacher, in Tests prüfbar und für Tastatur und Screenreader eindeutig.

**Status aus dem letzten Abgleich:** `last_error` gilt als Problem, die Einstellungen zeigen dem Owner die Meldung und „Verbindung prüfen“. Vorübergehende Störungen unterscheiden wir bewusst nicht von Dauerfehlern: Der nächste erfolgreiche Abgleich löscht die Meldung von selbst.

**Ordner in den Papierkorb:** Ein Ordner kann Dateien enthalten, die jemand selbst abgelegt hat und die die App nicht sehen kann. Deshalb kommt er in den Papierkorb des Drive, statt endgültig gelöscht zu werden. Scheitert das, läuft das Aufräumen trotzdem weiter.

## Folgen

- Fehler beim Hochladen setzen `last_error` nicht, der Status spiegelt nur den Kalender-Abgleich.
- Neue AG-Einstellungen gehören in `CUSTOMIZE_GROUPS`.
