"""Landingpage, Rechtliches, Hilfe & FAQ, Über die App (M12)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import LegalPage
from apps.organizations.permissions import Role


@pytest.mark.django_db
def test_landing_for_anonymous():
    content = Client().get("/").content.decode()
    for text in [
        "Zur App",
        "nur auf Einladung",
        "So startest du",
        "kostenlos",
        "Impressum",
        "landing/handy-dashboard.png",
    ]:
        assert text in content
    assert "Crew-Anfragen offen" not in content  # nicht das Dashboard


def test_dashboard_for_members(member_client):
    content = member_client.get("/").content.decode()
    assert "Was steht an?" in content and "So startest du" not in content


def test_screenshots_exist(settings):
    for name in ["handy-dashboard", "handy-produktion", "handy-material", "computer-kalender"]:
        assert (settings.BASE_DIR / "static" / "landing" / f"{name}.png").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "kind"),
    [
        ("core:imprint", "impressum"),
        ("core:privacy", "datenschutz"),
        ("core:terms", "nutzungsbedingungen"),
    ],
)
def test_legal_pages(url_name, kind):
    url = reverse(url_name)
    assert "Noch nicht hinterlegt" in Client().get(url).content.decode()
    LegalPage.objects.create(kind=kind, content="Verantwortlich: Max Muster\n\nmax@example.org <b>")
    content = Client().get(url).content.decode()
    assert "Max Muster" in content and 'href="mailto:max@example.org"' in content
    assert "<b>" not in content  # Text wird nicht als HTML ausgeführt


@pytest.mark.django_db
def test_legal_links_on_public_pages(org):
    from apps.inquiries.services import link_for

    link = link_for(org)
    link.is_active = True
    link.save()
    for url in ["/", reverse("accounts:login"), reverse("inquiries:public", args=[link.token])]:
        assert reverse("core:privacy") in Client().get(url).content.decode(), url


def test_help_by_role(org, owner, login, member_client):
    owner_page = login(owner.user, org).get(reverse("core:help")).content.decode()
    student_page = member_client.get(reverse("core:help")).content.decode()
    assert "Was macht der Schuljahreswechsel?" in owner_page
    assert "Was macht der Schuljahreswechsel?" not in student_page
    assert "Wie installiere ich die App auf dem Handy?" in student_page


def test_help_for_teachers(org, make_member, login):
    client = login(make_member(org, Role.TEACHER).user, org)
    content = client.get(reverse("core:help")).content.decode()
    assert "Freistellungsliste" in content and "Google-Konto der AG" not in content


def test_about(member_client, settings):
    settings.APP_VERSION = "1.2.3"
    content = member_client.get(reverse("core:about")).content.decode()
    assert "Version 1.2.3" in content
    assert "PolyForm Noncommercial" in content and "quelloffen" in content
    assert reverse("core:imprint") in content


def test_settings_has_no_placeholders_and_shows_status(org, owner, login):
    from apps.inquiries.services import link_for

    link = link_for(org)
    link.is_active = True
    link.save()
    client = login(owner.user, org)
    content = client.get(reverse("organizations:settings")).content.decode()
    assert "folgt in M" not in content
    assert "Link ist aktiv" in client.get(reverse("organizations:customize")).content.decode()
    assert reverse("core:help") in content and reverse("core:about") in content
