"""Öffentliches Anfrage-Formular: ohne Anmeldung, Spam-Schutz, inaktive Links."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inquiries.models import Inquiry
from apps.productions.models import Category


@pytest.fixture
def anonymous():
    return Client()


def _data(**overrides):
    data = {
        "requester_name": "Frau Muster",
        "requester_email": "muster@schule.example",
        "date": (timezone.localdate() + timedelta(days=10)).isoformat(),
    }
    data.update(overrides)
    return data


def test_form_without_login_shows_only_org_name(anonymous, org, active_link):
    response = anonymous.get(reverse("inquiries:public", args=[active_link.token]))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Technik anfragen" in content and org.name in content
    assert "Beamer und Leinwand" in content
    assert "Konzert" in content  # Kategorien der AG als „Art“


def test_submit_minimal_inquiry(anonymous, org, active_link):
    response = anonymous.post(reverse("inquiries:public", args=[active_link.token]), _data())

    assert response.url == reverse("inquiries:public_thanks", args=[active_link.token])
    inquiry = Inquiry.objects.get()
    assert inquiry.organization == org and inquiry.requester_name == "Frau Muster"
    assert anonymous.get(response.url).status_code == 200


def test_submit_full_inquiry(anonymous, org, active_link):
    category = Category.objects.for_org(org).get(name="Konzert")
    anonymous.post(
        reverse("inquiries:public", args=[active_link.token]),
        _data(
            requester_role="Schulleitung",
            event_name="Weihnachtskonzert",
            category=category.pk,
            start_time="18:00",
            end_time="20:00",
            setup_from="16:00",
            teardown_until="21:00",
            location="Aula",
            tech_needs=["Mikrofone", "Licht"],
            tech_notes="Klavier abnehmen",
            schedule="Chor, dann Orchester",
            schedule_link="https://example.org/ablauf.pdf",
            contact_name="Herr Beispiel",
            contact_phone="0221 123",
        ),
    )
    inquiry = Inquiry.objects.get()
    assert inquiry.category == category
    assert inquiry.tech_needs == ["Mikrofone", "Licht"]
    assert inquiry.schedule_link == "https://example.org/ablauf.pdf"


@pytest.mark.parametrize("missing", ["requester_name", "requester_email", "date"])
def test_required_fields(anonymous, active_link, missing):
    response = anonymous.post(
        reverse("inquiries:public", args=[active_link.token]), _data(**{missing: ""})
    )
    assert response.status_code == 200
    assert not Inquiry.objects.exists()


def test_end_before_start_rejected(anonymous, active_link):
    anonymous.post(
        reverse("inquiries:public", args=[active_link.token]),
        _data(start_time="20:00", end_time="19:00"),
    )
    assert not Inquiry.objects.exists()


def test_category_of_other_org_rejected(anonymous, other_org, active_link):
    foreign = Category.objects.for_org(other_org).first()
    anonymous.post(
        reverse("inquiries:public", args=[active_link.token]), _data(category=foreign.pk)
    )
    assert not Inquiry.objects.exists()


def test_inactive_unknown_or_renewed_link_is_404(anonymous, org, active_link):
    url = reverse("inquiries:public", args=[active_link.token])
    assert anonymous.get(reverse("inquiries:public", args=["gibt-es-nicht"])).status_code == 404

    active_link.renew()
    response = anonymous.get(url)
    assert response.status_code == 404
    assert "nicht aktiv" in response.content.decode()

    active_link.is_active = False
    active_link.save()
    assert anonymous.get(reverse("inquiries:public", args=[active_link.token])).status_code == 404
    assert anonymous.post(url, _data()).status_code == 404
    assert not Inquiry.objects.exists()


def test_deactivated_org_link_is_404(anonymous, org, active_link):
    org.is_active = False
    org.save()
    assert anonymous.get(reverse("inquiries:public", args=[active_link.token])).status_code == 404


def test_honeypot_pretends_success_but_saves_nothing(anonymous, active_link):
    response = anonymous.post(
        reverse("inquiries:public", args=[active_link.token]), _data(website="spam.example")
    )
    assert response.status_code == 302
    assert not Inquiry.objects.exists()


def test_limit_per_ip(anonymous, active_link, settings):
    settings.INQUIRY_MAX_PER_IP_HOUR = 2
    url = reverse("inquiries:public", args=[active_link.token])
    for _ in range(2):
        assert anonymous.post(url, _data()).status_code == 302
    response = anonymous.post(url, _data())
    assert response.status_code == 200
    assert "später noch einmal" in response.content.decode()
    assert Inquiry.objects.count() == 2


def test_limit_per_link_across_ips(anonymous, active_link, settings):
    settings.INQUIRY_MAX_PER_LINK_HOUR = 2
    url = reverse("inquiries:public", args=[active_link.token])
    for n in range(3):
        anonymous.post(url, _data(), REMOTE_ADDR=f"10.0.0.{n}")
    assert Inquiry.objects.count() == 2


def test_tokens_of_two_orgs_never_mix(anonymous, org, other_org, active_link):
    from apps.inquiries.services import link_for

    other = link_for(other_org)
    other.is_active = True
    other.save()
    anonymous.post(reverse("inquiries:public", args=[other.token]), _data())

    assert Inquiry.objects.get().organization == other_org
    content = anonymous.get(reverse("inquiries:public", args=[other.token])).content.decode()
    assert other_org.name in content and org.name not in content
