"""Google-Konto verbinden und trennen (nur Owner), Token verschlüsselt."""

import pytest
from django.urls import reverse

from apps.google_sync import oauth
from apps.google_sync.google_api import SCOPES
from apps.google_sync.models import GoogleConnection, SyncedEvent
from apps.organizations.permissions import Role

TOKENS = {"refresh_token": "neuer-token", "scopes": sorted(SCOPES), "email": "ag@gmail.com"}


@pytest.fixture
def owner_client(org, owner, login):
    return login(owner.user, org)


def _pending(client, org, state="abc"):
    session = client.session
    session[oauth.SESSION_KEY] = {"state": state, "verifier": "v", "organization": org.pk}
    session.save()


def test_page_without_server_setup(owner_client, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    content = owner_client.get(reverse("google_sync:settings")).content.decode()
    assert "docs/installation/google-cloud.md" in content


def test_connect_redirects_to_google(owner_client, google):
    response = owner_client.post(reverse("google_sync:connect"))
    assert response.url.startswith("https://accounts.google.com/")
    assert "calendar.app.created" in response.url and "drive.file" in response.url
    assert "access_type=offline" in response.url
    assert owner_client.session[oauth.SESSION_KEY]["state"] in response.url


def test_callback_connects_and_syncs(
    org, owner_client, google, monkeypatch, make_production, django_capture_on_commit_callbacks
):
    make_production(org, "Schulkonzert")
    monkeypatch.setattr(oauth, "exchange_code", lambda code, verifier: dict(TOKENS))
    _pending(owner_client, org)
    with django_capture_on_commit_callbacks(execute=True):
        response = owner_client.get(
            reverse("google_sync:callback") + "?state=abc&code=xyz", follow=True
        )

    connection = GoogleConnection.objects.get(organization=org)
    assert connection.account_email == "ag@gmail.com"
    assert connection.refresh_token == "neuer-token"
    assert "neuer-token" not in connection.refresh_token_encrypted  # verschlüsselt
    assert connection.calendar_id in google.calendars  # Kalender angelegt
    assert [b["summary"] for b in google.events.values()] == ["Schulkonzert"]  # nachgeholt
    assert "Verbunden mit ag@gmail.com" in response.content.decode()


def test_callback_rejects_wrong_state(org, owner_client, google, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda code, verifier: dict(TOKENS))
    _pending(owner_client, org, state="richtig")
    owner_client.get(reverse("google_sync:callback") + "?state=falsch&code=xyz")
    assert not GoogleConnection.objects.exists()


def test_callback_requires_all_scopes(org, owner_client, google, monkeypatch):
    tokens = {**TOKENS, "scopes": ["openid"]}
    monkeypatch.setattr(oauth, "exchange_code", lambda code, verifier: tokens)
    _pending(owner_client, org)
    response = owner_client.get(
        reverse("google_sync:callback") + "?state=abc&code=xyz", follow=True
    )
    assert not GoogleConnection.objects.exists()
    assert "Google Drive, Google Kalender" in response.content.decode()


def test_callback_cancelled(org, owner_client, google):
    _pending(owner_client, org)
    owner_client.get(reverse("google_sync:callback") + "?state=abc&error=access_denied")
    assert not GoogleConnection.objects.exists()


def test_disconnect_keeps_calendar(org, owner_client, connected, google):
    owner_client.post(reverse("google_sync:sync_now"))
    calendar_id = GoogleConnection.objects.get().calendar_id
    owner_client.post(reverse("google_sync:disconnect"))

    connection = GoogleConnection.objects.get()
    assert google.revoked and not connection.is_connected
    assert connection.calendar_id == calendar_id and calendar_id in google.calendars


def test_reconnect_with_other_account_starts_fresh(org, owner, connected, google):
    from apps.google_sync import services

    connected.calendar_id = "alter-kalender"
    connected.save()
    SyncedEvent.objects.create(organization=org, key="x:1", google_event_id="e", checksum="c")

    services.connect(org, owner.user, **{**TOKENS, "email": "technik-ag@gmail.com"})
    assert GoogleConnection.objects.get().calendar_id == "alter-kalender"  # dasselbe Konto

    services.connect(org, owner.user, **TOKENS)  # anderes Konto
    connection = GoogleConnection.objects.get()
    assert connection.calendar_id == "" and not SyncedEvent.objects.exists()


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner(org, make_member, login, google, role):
    client = login(make_member(org, role).user, org)
    assert client.get(reverse("google_sync:settings")).status_code == 403
    assert client.get(reverse("google_sync:callback")).status_code == 403
    for name in ["connect", "disconnect", "sync_now"]:
        assert client.post(reverse(f"google_sync:{name}")).status_code == 403


def test_settings_menu_links_google(owner_client):
    content = owner_client.get(reverse("organizations:settings")).content.decode()
    assert reverse("google_sync:settings") in content


# ---------- Hinweis in den Einstellungen ----------

HINT = "Noch kein Google-Konto verbunden"


@pytest.fixture
def configured(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"


def _settings_page(client):
    return client.get(reverse("organizations:settings")).content.decode()


def test_owner_sees_google_hint_with_link(org, owner, login, configured):
    content = _settings_page(login(owner.user, org))

    assert HINT in content
    assert reverse("google_sync:settings") in content


def test_no_hint_when_connected(org, owner, login, configured, connected):
    assert HINT not in _settings_page(login(owner.user, org))


def test_no_hint_without_google_project(org, owner, login, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""

    assert HINT not in _settings_page(login(owner.user, org))


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner_sees_hint(org, make_member, login, configured, role):
    assert HINT not in _settings_page(login(make_member(org, role).user, org))
