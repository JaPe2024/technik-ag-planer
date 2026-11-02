# Betrieb

Für den Betreiber einer Installation. Einrichtung: [../installation/README.md](../installation/README.md). Django-Admin (AGs, Owner, Konten, Datenexport, Protokoll): [django-admin.md](django-admin.md).

Alle Befehle aus dem Hauptverzeichnis des Repositorys auf dem Server; `dc` steht für `docker compose -f deploy/docker-compose.yml`.

## Überblick

| Dienst | Aufgabe |
| --- | --- |
| `web` | Django (Gunicorn); führt beim Start die Datenbank-Migrationen aus |
| `worker` | Celery mit Zeitplan: Push-Erinnerungen (alle 10 Min.), Google-Kalender-Abgleich (nach Änderungen und nachts), Systemmeldungen, Aufräumen (Protokoll und Papierkorb nach 7 Tagen, erledigte Einladungen nach 30 Tagen, erledigte Anfragen nach 180 Tagen) |
| `db` | PostgreSQL |
| `cache` | Redis (Warteschlange, Cache, Login-Sperren) |
| `caddy` | HTTPS mit automatischem Zertifikat |

Dateien liegen nicht auf dem Server, sondern im Google Drive der jeweiligen AG.

## Updates

```sh
git pull                                   # bzw. eine bestimmte Version: git checkout v1.0.0
dc up -d --build
dc ps                                      # alles „healthy“/„running“?
```

Mit veröffentlichten Images (Git-Tag `vX.Y.Z` erzeugt `ghcr.io/labstorm-mg/technik-ag-planer:X.Y.Z`): in der `.env` `APP_VERSION=X.Y.Z` setzen, dann `dc pull && dc up -d`. Migrationen laufen automatisch. Vorher eine Sicherung machen (siehe unten) und den [CHANGELOG](../../CHANGELOG.md) lesen. Die Version steht in der App unter Einstellungen → Über die App.

## Zugangsdaten ändern

```sh
git pull
deploy/betrieb/zugangsdaten.sh
```

Das Skript fragt jeden Schritt einzeln ab (`y`/`n`): Datenbank-Passwort (mit Sicherung vorab, Eintrag in der `.env` und Neustart der App), Passwort eines Betreiber-Kontos und passwortfreies sudo ein- oder ausschalten. Bevor es passwortfreies sudo entfernt, prüft es dein Passwort, damit du dich nicht aussperrst. Mitglieder der Gruppen `docker` und `lxd` haben auf dem Server auch ohne sudo faktisch Root-Rechte.

## Backups

Gesichert werden die **Datenbank** und die **`.env`** (enthält Geheimnisse – sicher aufbewahren).

```sh
deploy/backup/backup.sh                    # legt backups/datenbank_<datum>.dump und env_<datum> an
```

Täglich per cron (als Benutzer mit Docker-Rechten, `crontab -e`):

```
30 2 * * * cd /opt/technik-ag-planer && deploy/backup/backup.sh >> backups/backup.log 2>&1
```

- Aufbewahrung: 14 Tage (`BACKUP_KEEP_DAYS=30 deploy/backup/backup.sh` für länger); Ordner mit `BACKUP_DIR` änderbar.
- Die Sicherungen zusätzlich **auf ein anderes Gerät** kopieren (z. B. per `rsync` auf ein NAS oder verschlüsselt in einen Cloud-Speicher) – eine Sicherung auf demselben Server hilft bei einem Plattenschaden nicht.
- Sicherungen enthalten personenbezogene Daten Minderjähriger: nur verschlüsselt außer Haus lagern und nicht länger als nötig aufbewahren.

**Wiederherstellen** (ersetzt alle aktuellen Daten):

```sh
deploy/backup/restore.sh backups/datenbank_2026-10-18_023000.dump
```

Auf einem neuen Server: Repository holen, die gesicherte `.env` zurückkopieren, `dc up -d`, dann `restore.sh`. Einmal im Halbjahr eine Wiederherstellung auf einem Testrechner ausprobieren.

## Überwachung und Logs

- Health-Check: `https://<domain>/healthz/` liefert `{"status": "ok"}`, wenn App und Datenbank laufen – geeignet für einen externen Uptime-Monitor.
- Logs: `dc logs -f web`, `dc logs -f worker`, `dc logs -f caddy`
- Speicherplatz: `docker system df`; alte Images mit `docker image prune` entfernen.

## Typische Aufgaben

| Aufgabe | So geht's |
| --- | --- |
| Neue AG mit Owner | Django-Admin → AGs ([django-admin.md](django-admin.md#3-ag-und-owner-anlegen)) |
| Owner wechseln | Django-Admin ([django-admin.md](django-admin.md#4-owner-wechseln)) |
| Konto sperren | Django-Admin → Konten → „aktiv“ entfernen |
| Zwei-Faktor zurücksetzen (Handy verloren) | Django-Admin → Konten → TOTP-Geräte des Kontos löschen |
| Datenexport einer AG | Django-Admin → AGs → Aktion „Datenexport“ |
| Rechtstexte (Impressum, Datenschutz, Nutzungsbedingungen) | Django-Admin → Rechtstexte (Vorlagen: [../rechtliches/](../rechtliches/README.md)) |
| Google-Anbindung | [../installation/google-cloud.md](../installation/google-cloud.md) |
| Push-Schlüssel | `dc exec web python manage.py vapid_schluessel` → `.env` (Wechsel = alle Geräte aktivieren Push neu) |

## Probleme

| Symptom | Ursache und Lösung |
| --- | --- |
| Seite nicht erreichbar, kein Zertifikat | DNS-Eintrag und Ports 80/443 prüfen, `dc logs caddy` |
| Keine Einladungs-Mails | `EMAIL_…` in der `.env` prüfen, Fehler in `dc logs web` |
| Keine Push-Mitteilungen | VAPID-Schlüssel gesetzt? `worker` läuft? Auf dem iPhone nur aus der App vom Home-Bildschirm |
| Keine Termine im Google-Kalender | `worker` läuft? Einstellungen → Google-Konto zeigt den letzten Fehler |
| „Verbindung zu Google abgelaufen“ | Cloud-Projekt auf „In Produktion“? Owner verbindet neu ([google-cloud.md](../installation/google-cloud.md#probleme)) |
| Nach `DJANGO_SECRET_KEY`-Wechsel | Alle sind abgemeldet, Google-Verbindungen müssen neu verbunden werden |
