#!/usr/bin/env bash
# Zugangsdaten auf dem Server ändern. Fragt jeden Schritt einzeln ab, nichts wird gespeichert
# oder angezeigt, außer der neuen .env:
#   1. Passwort der Datenbank (auch in der .env)
#   2. Passwort eines Betreiber-Kontos
#   3. Passwortfreies sudo für den aktuellen Benutzer ein- oder ausschalten
#
#   deploy/betrieb/zugangsdaten.sh          (aus einem beliebigen Ordner)
#
# Einstellbar: COMPOSE (Standard: mit Proxy-Datei, wenn TRUSTED_PROXY in der .env steht)
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ ! -f .env ]; then
  echo "Keine .env gefunden. Bitte im Repository auf dem Server ausführen." >&2
  exit 1
fi

if [ -z "${COMPOSE:-}" ]; then
  COMPOSE="docker compose -f deploy/docker-compose.yml"
  if grep -q '^TRUSTED_PROXY=.' .env; then
    COMPOSE="$COMPOSE -f deploy/docker-compose.proxy.yml"
  fi
fi

SUDO_FILE="/etc/sudoers.d/90-$(id -un)"

ask() {  # ask "Frage" → 0 bei y/j
  local answer
  read -r -p "$1 (y/n) " answer
  case "$answer" in
    y | Y | j | J) return 0 ;;
    *) return 1 ;;
  esac
}

read_twice() {  # read_twice "Bezeichnung" → Wert in NEW_SECRET
  local again
  read -r -s -p "$1: " NEW_SECRET
  echo
  read -r -s -p "$1 wiederholen: " again
  echo
  if [ "$NEW_SECRET" != "$again" ]; then
    echo "Die Eingaben stimmen nicht überein." >&2
    return 1
  fi
}

env_value() {
  grep -m1 "^$1=" .env | cut -d= -f2-
}

wait_for_web() {
  for _ in $(seq 1 36); do
    if $COMPOSE ps web --format '{{.Status}}' </dev/null | grep -q '(healthy)'; then
      return 0
    fi
    sleep 5
  done
  return 1
}

set_db_role() {  # set_db_role "Passwort" – nur Zeichen aus check_db_password
  printf "ALTER ROLE \"%s\" PASSWORD '%s';\n" "$(env_value POSTGRES_USER)" "$1" |
    $COMPOSE exec -T db sh -c 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null
}

write_db_password() {
  sed -i -E \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$1|" \
    -e "s|^(DATABASE_URL=[a-z]+://[^:]+:)[^@]*@|\1$1@|" \
    .env
}

change_db_password() {
  local old new
  old="$(env_value POSTGRES_PASSWORD)"
  read -r -s -p "Neues Datenbank-Passwort (leer = zufällig erzeugen): " new
  echo
  if [ -z "$new" ]; then
    new="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
  else
    local again
    read -r -s -p "Wiederholen: " again
    echo
    if [ "$new" != "$again" ]; then
      echo "Die Eingaben stimmen nicht überein, nichts geändert." >&2
      return 1
    fi
  fi
  # Steht in einer URL und in der .env, deshalb nur unkritische Zeichen
  if ! printf '%s' "$new" | grep -Eq '^[A-Za-z0-9_-]{16,}$'; then
    echo "Bitte mindestens 16 Zeichen aus A-Z, a-z, 0-9, _ und -. Nichts geändert." >&2
    return 1
  fi

  echo "Sicherung vor der Änderung …"
  if ! COMPOSE="$COMPOSE" sh deploy/backup/backup.sh </dev/null; then
    echo "Sicherung fehlgeschlagen, nichts geändert." >&2
    return 1
  fi

  if ! set_db_role "$new"; then
    echo "Die Datenbank hat das neue Passwort nicht angenommen, nichts geändert." >&2
    return 1
  fi
  write_db_password "$new"

  if $COMPOSE up -d web worker </dev/null >/dev/null 2>&1 && wait_for_web &&
    $COMPOSE exec -T web python manage.py check --database default </dev/null >/dev/null 2>&1; then
    echo "Datenbank-Passwort geändert, die App läuft."
    return 0
  fi

  echo "Die App startet mit dem neuen Passwort nicht. Stelle das alte wieder her …" >&2
  set_db_role "$old"
  write_db_password "$old"
  $COMPOSE up -d web worker </dev/null >/dev/null 2>&1 || true
  return 1
}

change_operator_password() {
  local default email
  default="$($COMPOSE exec -T web python manage.py shell -c "
from django.contrib.auth import get_user_model
print('ANTWORT', *get_user_model().objects.filter(is_staff=True).values_list('email', flat=True))
" </dev/null 2>/dev/null | sed -n 's/^ANTWORT //p')"
  echo "Betreiber-Konten: ${default:-keine gefunden}"
  read -r -p "E-Mail des Kontos [${default%% *}]: " email
  email="${email:-${default%% *}}"
  read_twice "Neues Passwort für $email" || return 1
  # Das Passwort geht über die Standardeingabe, nicht über die Befehlszeile
  if printf '%s' "$NEW_SECRET" | $COMPOSE exec -T -e ZIEL_EMAIL="$email" web python manage.py shell -c "
import os, sys
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
user = get_user_model().objects.filter(email__iexact=os.environ['ZIEL_EMAIL'], is_staff=True).first()
if user is None:
    print('Kein Betreiber-Konto mit dieser Adresse.'); sys.exit(1)
password = sys.stdin.read()
try:
    validate_password(password, user)
except ValidationError as error:
    print(' '.join(error.messages)); sys.exit(1)
user.set_password(password)
user.save(update_fields=['password'])
print('Betreiber-Passwort geändert. Bestehende Anmeldungen sind damit abgemeldet.')
" 2>&1 | grep -v 'objects imported'; then
    NEW_SECRET=""
    return 0
  fi
  NEW_SECRET=""
  return 1
}

toggle_sudo() {
  local me
  me="$(id -un)"
  if [ -e "$SUDO_FILE" ]; then
    echo "Passwortfreies sudo ist für $me aktiv ($SUDO_FILE)."
    ask "Entfernen? Danach fragt sudo nach deinem Passwort" || return 0
    echo "Zur Sicherheit: Bitte dein Passwort von $me eingeben, damit du dich nicht aussperrst."
    if ! su -s /bin/sh -c true "$me"; then
      echo "Passwort falsch, sudo bleibt unverändert." >&2
      return 1
    fi
    sudo rm -f "$SUDO_FILE" || return 1
    sudo -k
    echo "Passwortfreies sudo entfernt. sudo geht weiter, fragt aber nach dem Passwort."
  else
    echo "Passwortfreies sudo ist für $me nicht aktiv."
    ask "Einschalten? (nur vorübergehend sinnvoll)" || return 0
    local temp
    temp="$(mktemp)"
    printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$me" >"$temp"
    if sudo visudo -cf "$temp" >/dev/null; then
      sudo install -m 440 -o root -g root "$temp" "$SUDO_FILE" || return 1
      echo "Passwortfreies sudo eingeschaltet."
    else
      echo "Regel ungültig, nichts geändert." >&2
    fi
    rm -f "$temp"
  fi
}

failed=0
if ask "1. Datenbank-Passwort ändern? Die App startet dabei kurz neu"; then
  change_db_password || failed=1
fi
if ask "2. Betreiber-Passwort ändern?"; then
  change_operator_password || failed=1
fi
if ask "3. Passwortfreies sudo prüfen oder ändern?"; then
  toggle_sudo || failed=1
fi

if [ "$failed" -ne 0 ]; then
  echo "Fertig, aber mindestens ein Schritt ist fehlgeschlagen (siehe oben)." >&2
  exit 1
fi
echo "Fertig."
