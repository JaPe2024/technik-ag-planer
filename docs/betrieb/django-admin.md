# Django-Admin für den Betreiber

Der Django-Admin ist nur für den Betreiber der Installation, nicht für Owner oder Mitglieder. Er liegt unter `/admin/`, im Betrieb besser unter einem eigenen Pfad (`DJANGO_ADMIN_URL` in der `.env`).

## 1. Betreiber-Konto anlegen

```sh
# Betrieb
docker compose -f deploy/docker-compose.yml exec web python manage.py createsuperuser
# Entwicklung
make superuser
```

Betreiber-Konten treten keiner AG bei und können nicht Owner werden. Wer auch selbst in einer AG mitarbeitet, nimmt dafür eine zweite E-Mail-Adresse.

## 2. Zwei-Faktor-Anmeldung einrichten

Im Betrieb lässt der Admin nur Konten mit bestätigter Zwei-Faktor-Anmeldung herein (`DJANGO_ADMIN_REQUIRE_2FA=true`, Standard).

1. Unter `/anmelden/` mit dem Betreiber-Konto anmelden. Weil das Konto zu keiner AG gehört, erscheint die Seite „Keine AG“.
2. Dort „Zwei-Faktor-Anmeldung einrichten“ öffnen, den QR-Code mit einer Authenticator-App scannen und den Code bestätigen.
3. Danach `/admin/` öffnen – bei der Anmeldung über `/anmelden/` wird der Code abgefragt, und der Admin ist erreichbar.

In der Entwicklung ist die Pflicht ausgeschaltet.

## 3. AG und Owner anlegen

1. **AGs → AG hinzufügen**
2. Name eintragen, „E-Mail des Owners“ ausfüllen, speichern.
3. Der Owner bekommt automatisch eine Einladung (7 Tage gültig, einmal nutzbar) und setzt darüber Name, Jahrgangsstufe und Passwort.

Weitere Mitglieder lädt danach nur der Owner in der App ein (Einstellungen → Mitglieder).

## 4. Owner wechseln

In der AG das Feld „E-Mail des Owners“ ändern:

- Ist die Person schon Mitglied, wird sie sofort Owner; der bisherige Owner wird Admin.
- Sonst bekommt sie eine Owner-Einladung; der Wechsel passiert beim Annehmen.

Owner-Einladung erneut senden: in der AG-Liste die AG markieren → Aktion „Owner-Einladung erneut senden“.

## 5. AG deaktivieren oder löschen

- **Deaktivieren** (Aktion oder Häkchen „aktiv“): Mitglieder kommen nicht mehr in die AG, die Daten bleiben erhalten.
- **Löschen**: entfernt die AG mit allen Daten in der App. Dateien im Google Drive der AG bleiben erhalten.

## 6. Konten

**Konten** zeigt alle Konten mit AGs und 2FA-Status. Aktionen:

- **Konten sperren** / **Sperre aufheben** – gesperrte Konten können sich nicht anmelden
- **Zwei-Faktor-Anmeldung zurücksetzen** – z. B. wenn jemand das Handy verloren hat; die Person kann 2FA danach neu einrichten
- Löschen über die Detailseite

## 7. Datenexport einer AG

AG-Liste → AG markieren → Aktion **„Daten exportieren (ZIP)“**. Das Archiv enthält je Datenart eine JSON-Datei (AG, Konten der Mitglieder, Mitgliedschaften, Einladungen; spätere Versionen ergänzen weitere Daten). Passwörter und Einladungs-Tokens sind nicht enthalten.

## 8. Änderungsprotokoll

**Änderungsprotokoll** zeigt, wer wann was angelegt, geändert oder gelöscht hat. Einträge werden nach 7 Tagen automatisch gelöscht (täglich um 3:15 Uhr durch den Worker). Das Protokoll ist schreibgeschützt.
