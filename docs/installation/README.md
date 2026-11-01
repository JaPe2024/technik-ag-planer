# Installation auf dem eigenen Server

Danach geht es im Betrieb weiter: Updates, Backups und typische Aufgaben stehen in [../betrieb/README.md](../betrieb/README.md).

## Voraussetzungen

- Ein eigener Server (z. B. ein kleiner Rechner oder eine VM) mit Docker und Docker Compose
- Eine eigene Domain, deren DNS-Eintrag auf den Server zeigt (z. B. `planer.example.org`)
- Die Ports 80 und 443 sind aus dem Internet erreichbar – Caddy holt darüber automatisch das HTTPS-Zertifikat. HTTPS ist Pflicht, u. a. für die Nutzung als App auf dem Handy
- Ein Postfach für ausgehende Mails (SMTP), z. B. `noreply@…` der eigenen Domain oder ein EU-Mailanbieter. Die App verschickt nur Einladungen und „Passwort vergessen“

## 1. Code holen und konfigurieren

```sh
git clone https://github.com/LABSTORM-MG/technik-ag-planer.git
cd technik-ag-planer
cp .env.example .env
```

In der `.env` mindestens eintragen:

| Wert | Hinweis |
| --- | --- |
| `DJANGO_SECRET_KEY` | Langer Zufallswert, z. B. `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS`, `DOMAIN`, `SITE_URL` | Die eigene Domain |
| `ACME_EMAIL` | Kontakt für Let's Encrypt |
| `POSTGRES_PASSWORD` und `DATABASE_URL` | Dasselbe sichere Passwort an beiden Stellen |
| `EMAIL_…`, `DEFAULT_FROM_EMAIL` | Zugangsdaten des Mail-Postfachs |
| `DJANGO_ADMIN_URL` | Am besten ein schwer zu erratender Pfad statt `admin/` |

Die `.env` enthält Geheimnisse – sie gehört nie ins Repository (steht in `.gitignore`).

## 2. Starten

```sh
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml ps        # alle Dienste „healthy“ bzw. „running“
```

Beim Start des Web-Containers laufen die Datenbank-Migrationen automatisch. Die Dienste: `web` (Django), `worker` (Hintergrundaufgaben), `db` (PostgreSQL), `cache` (Redis), `caddy` (HTTPS).

### Variante: hinter einem vorgeschalteten Reverse Proxy

Übernimmt ein anderer Proxy (z. B. Nginx Proxy Manager) das HTTPS, spricht Caddy nur HTTP auf Port 80 (ADR 0016):

1. In der `.env` `TRUSTED_PROXY` auf die Adresse setzen, mit der der Proxy beim Server ankommt. `ACME_EMAIL` entfällt, `DOMAIN` wird nicht ausgewertet.
2. Im Proxy die Domain auf `http://<server>:80` weiterleiten und dort das Zertifikat und „Force SSL“ einrichten. HSTS setzt die App selbst, Websockets werden nicht gebraucht.
3. Starten – in allen Befehlen dieser Anleitung beide Dateien angeben:

   ```sh
   docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.proxy.yml up -d --build
   ```

4. Port 80 nur für den Proxy öffnen. Von Docker veröffentlichte Ports umgehen `ufw`, die Regel gehört deshalb ans Ende von `/etc/ufw/after.rules` (Netzwerkkarte und Adresse anpassen), danach `sudo ufw reload`:

   ```
   *filter
   :DOCKER-USER - [0:0]
   -A DOCKER-USER -i ens18 -p tcp -m conntrack --ctorigdstport 80 --ctdir ORIGINAL ! -s 192.0.2.10 -j DROP
   COMMIT
   ```

## 3. Betreiber-Konto und erste AG

```sh
docker compose -f deploy/docker-compose.yml exec web python manage.py createsuperuser
```

Danach Zwei-Faktor-Anmeldung einrichten und die erste AG mit Owner anlegen – Schritt für Schritt in [../betrieb/django-admin.md](../betrieb/django-admin.md).

## 4. Google-Anbindung (optional, empfohlen)

Für Dateiablage im Google Drive und den Google-Kalender der AGs braucht die Installation einmalig ein Google-Cloud-Projekt: [google-cloud.md](google-cloud.md). Ohne sie funktioniert die App, nur Datei-Uploads und die Kalender-Übertragung fehlen.

## 5. Push-Mitteilungen

Für Push-Mitteilungen braucht der Server ein VAPID-Schlüsselpaar:

```sh
docker compose -f deploy/docker-compose.yml exec web python manage.py vapid_schluessel
```

Die drei ausgegebenen Zeilen (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_ADMIN_EMAIL` – dort eine echte Kontaktadresse eintragen) in die `.env` übernehmen und `docker compose -f deploy/docker-compose.yml up -d` ausführen. Danach aktiviert jedes Mitglied Push unter Einstellungen → Benachrichtigungen auf seinem Gerät. Auf dem iPhone geht das nur in der App vom Home-Bildschirm (Safari → Teilen → „Zum Home-Bildschirm“). Werden die Schlüssel später gewechselt, müssen alle Geräte Push neu aktivieren. Erinnerungen verschickt der `worker`-Container.

## 6. Rechtstexte und Backups

- Impressum, Datenschutzerklärung und Nutzungsbedingungen im Django-Admin unter **Rechtstexte** eintragen (Vorlagen: [../rechtliches/](../rechtliches/README.md)).
- Tägliche Sicherung per cron einrichten: [../betrieb/README.md#backups](../betrieb/README.md#backups).

## 7. Updates

Solange es noch keine veröffentlichte Version gibt:

```sh
git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

Ab der ersten Version (Git-Tag `vX.Y.Z`) gibt es fertige Images unter `ghcr.io/labstorm-mg/technik-ag-planer`; dann reichen `APP_VERSION=X.Y.Z docker compose -f deploy/docker-compose.yml pull` und `up -d`. Migrationen laufen in beiden Fällen automatisch.

## Probleme

- **Logs ansehen:** `docker compose -f deploy/docker-compose.yml logs -f web`
- **Kein Zertifikat:** DNS-Eintrag und Ports 80/443 prüfen, Logs von `caddy` ansehen
- **Keine Mails:** `EMAIL_…`-Werte prüfen; Fehler stehen in den Logs von `web`
