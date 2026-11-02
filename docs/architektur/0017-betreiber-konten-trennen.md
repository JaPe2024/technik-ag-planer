# ADR 0017: Betreiber-Konten treten keiner AG bei

- **Status:** angenommen
- **Datum:** 2026-11-02

## Kontext

Pro E-Mail-Adresse gibt es ein Konto. Ein Konto, das schon existiert, tritt einer AG per Klick bei, ohne neues Passwort; so kann eine Person mit einem Login in mehreren AGs sein. Beim ersten Test auf dem Server ging eine Einladung an die Adresse des Betreibers, und dessen Konto wurde Owner einer AG. Damit läuft der Alltag in der App, auch auf dem Handy, über ein Konto mit Vollzugriff auf die ganze Installation.

## Entscheidungen

**Betreiber und AG-Mitglied sind getrennte Konten:** Konten mit `is_staff` oder `is_superuser` werden nicht eingeladen, können keine Einladung annehmen und nicht Owner werden. Die Prüfung liegt in `apps.organizations.services` (`invite`, `resend`, `find_open_invitation`, `accept`, `make_owner`), damit Oberfläche und Admin dieselbe Regel nutzen. Im Admin-Formular greift sie zusätzlich vor dem Speichern, damit keine AG ohne Owner entsteht.

**Beitritt per Klick bleibt für normale Konten:** Das ist für Mitglieder mehrerer AGs gewollt. Fremde kommen so nicht hinein, weil ohne Anmeldung das Passwort des Kontos verlangt wird.

## Folgen

- Wer eine Installation betreibt und selbst in einer AG mitarbeitet, braucht zwei Adressen.
- Ein Owner erfährt beim Einladen, dass eine Adresse zu einem Betreiber-Konto gehört. Das nehmen wir für die klare Meldung in Kauf.
- Bestehende Mitgliedschaften werden nicht automatisch entfernt. Ein Mitglied, das nachträglich im Admin zum Betreiber gemacht wird, bleibt Mitglied, bis es dort aus der AG entfernt wird; es kann aber nicht mehr Owner werden.
