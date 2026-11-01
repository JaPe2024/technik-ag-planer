# ADR 0016: Betrieb hinter einem vorgeschalteten Reverse Proxy

- **Status:** angenommen
- **Datum:** 2026-11-01

## Kontext

Die erste Installation läuft auf einer VM ohne eigene öffentliche Adresse. Ein vorgeschalteter Reverse Proxy (Nginx Proxy Manager auf einem externen Server) übernimmt HTTPS und erreicht die VM über ein VPN. Das Standard-Setup geht davon aus, dass Caddy direkt am Internet hängt: Es holt selbst ein Zertifikat, leitet HTTP auf HTTPS um und ersetzt die Weiterleitungs-Header. Dahinter entstünde eine Weiterleitungsschleife, und Django sähe alle Besucher mit derselben Adresse. Die Login-Sperre und die Grenzen des Anfrage-Formulars würden dann alle gemeinsam treffen.

## Entscheidungen

**Caddy bleibt als interne Schicht:** Eine Ergänzung (`deploy/docker-compose.proxy.yml`, `deploy/caddy/Caddyfile.proxy`) lässt Caddy nur HTTP auf Port 80 sprechen. Upload-Grenze, Komprimierung und Sicherheits-Header bleiben an einer Stelle, Django und die übrigen Dienste ändern sich nicht. Das Standard-Setup bleibt unverändert.

**Header nur vom eingetragenen Proxy:** Caddy glaubt `X-Forwarded-Proto` und `X-Real-IP` nur von der Adresse in `TRUSTED_PROXY`. Die Client-Adresse kommt aus `X-Real-IP`, weil Clients den Anfang von `X-Forwarded-For` frei setzen können und Django den ersten Eintrag auswertet (`apps.accounts.throttle.client_ip`). Caddy gibt Django deshalb nur die geprüfte Adresse weiter.

**Port 80 zusätzlich per Firewall begrenzt:** Von Docker veröffentlichte Ports umgehen `ufw`. Die Regel gehört daher in die Kette `DOCKER-USER` (`docs/installation/README.md`).

## Folgen

- Der vorgeschaltete Proxy muss `X-Real-IP` und `X-Forwarded-Proto` setzen; der Nginx Proxy Manager tut das von selbst.
- Wechselt die Adresse, mit der der Proxy bei Caddy ankommt, muss `TRUSTED_PROXY` angepasst werden. Sonst leitet Django wegen `X-Forwarded-Proto: http` endlos auf HTTPS um.
- Geprüft wurde die Konfiguration mit echten Containern (eingetragener Proxy und fremder Absender mit gefälschten Headern), nicht in der Test-Suite, weil dort kein Caddy läuft.
