"""Technik-Auswahl: Liste je AG, Rechte, Mandantentrennung, alte Anfragen, Migration."""

from importlib import import_module

import pytest
from django.apps import apps as django_apps
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inquiries.models import DEFAULT_TECH_OPTIONS, Inquiry, TechOption
from apps.inquiries.services import link_for
from apps.organizations.models import Organization
from apps.organizations.permissions import Role

LIST_URL = "inquiries:tech_options"


def _member(org, owner, make_member, role):
    return owner if role == Role.OWNER else make_member(org, role)


def _names(org):
    return list(TechOption.objects.for_org(org).values_list("name", flat=True))


def _submit(link, **extra):
    data = {
        "requester_name": "Frau Muster",
        "requester_email": "muster@schule.example",
        "date": timezone.localdate().isoformat(),
        **extra,
    }
    return Client().post(reverse("inquiries:public", args=[link.token]), data)


@pytest.fixture
def active_other_link(other_org):
    link = link_for(other_org)
    link.is_active = True
    link.save()
    return link


# ---------- Startwerte ----------


def test_new_org_gets_default_options(org):
    assert _names(org) == DEFAULT_TECH_OPTIONS


def test_defaults_are_not_added_twice(org):
    TechOption.objects.for_org(org).delete()
    org.save()

    assert _names(org) == []


# ---------- Formular ----------


def test_form_shows_only_options_of_this_org(org, other_org, active_link):
    TechOption.objects.create(organization=org, name="Nebelmaschine", position=9)
    TechOption.objects.create(organization=other_org, name="Fremde Bühne", position=9)

    content = Client().get(reverse("inquiries:public", args=[active_link.token])).content.decode()

    assert "Nebelmaschine" in content
    assert "Fremde Bühne" not in content


def test_form_stores_text_of_chosen_option(org, active_link):
    TechOption.objects.create(organization=org, name="Nebelmaschine", position=9)

    _submit(active_link, tech_needs=["Nebelmaschine", "Licht"])

    assert Inquiry.objects.get().tech_needs == ["Nebelmaschine", "Licht"]


@pytest.mark.parametrize("value", ["Fremde Bühne", "mikrofone", "<script>"])
def test_form_rejects_unknown_or_foreign_value(org, other_org, active_link, value):
    TechOption.objects.create(organization=other_org, name="Fremde Bühne", position=9)

    response = _submit(active_link, tech_needs=[value])

    assert response.status_code == 200
    assert "tech_needs" in response.context["form"].errors
    assert not Inquiry.objects.exists()


def test_empty_list_hides_checklist_and_form_still_works(org, active_link):
    TechOption.objects.for_org(org).delete()

    content = Client().get(reverse("inquiries:public", args=[active_link.token])).content.decode()
    assert 'name="tech_needs"' not in content
    assert 'name="tech_notes"' in content

    response = _submit(active_link, tech_notes="Zwei Mikrofone")

    assert response.status_code == 302
    inquiry = Inquiry.objects.get()
    assert inquiry.tech_needs == []
    assert inquiry.tech_notes == "Zwei Mikrofone"


def test_changing_list_keeps_existing_inquiry(org, owner, login, active_link):
    _submit(active_link, tech_needs=["Licht", "Mikrofone"])
    client = login(owner.user, org)
    licht = TechOption.objects.for_org(org).get(name="Licht")
    mics = TechOption.objects.for_org(org).get(name="Mikrofone")

    client.post(reverse("inquiries:tech_option_edit", args=[licht.pk]), {"name": "Scheinwerfer"})
    client.post(reverse("inquiries:tech_option_delete", args=[mics.pk]))

    inquiry = Inquiry.objects.get()
    assert inquiry.tech_needs == ["Licht", "Mikrofone"]
    content = client.get(reverse("inquiries:detail", args=[inquiry.pk])).content.decode()
    assert "Licht, Mikrofone" in content


# ---------- Verwaltung und Rechte ----------


@pytest.mark.parametrize(
    ("role", "allowed"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_rights_per_role(org, owner, make_member, login, role, allowed):
    client = login(_member(org, owner, make_member, role).user, org)
    item = TechOption.objects.for_org(org).first()
    expected = 200 if allowed else 403

    assert client.get(reverse(LIST_URL)).status_code == expected
    assert client.get(reverse("inquiries:tech_option_edit", args=[item.pk])).status_code == expected

    client.post(reverse(LIST_URL), {"name": "Nebelmaschine"})
    client.post(reverse("inquiries:tech_option_move", args=[item.pk]), {"richtung": "1"})
    client.post(reverse("inquiries:tech_option_delete", args=[item.pk]))

    names = _names(org)
    assert ("Nebelmaschine" in names) is allowed
    assert (item.name in names) is not allowed


@pytest.mark.parametrize(
    ("role", "visible"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.TEACHER, True), (Role.STUDENT, False)],
)
def test_menu_entry_per_role(org, owner, make_member, login, role, visible):
    client = login(_member(org, owner, make_member, role).user, org)

    content = client.get(reverse("organizations:settings")).content.decode()

    assert ("Technik-Auswahl" in content) is visible


def test_teacher_still_cannot_manage_public_link(org, make_member, login):
    client = login(make_member(org, Role.TEACHER).user, org)

    assert client.get(reverse("inquiries:settings")).status_code == 403


@pytest.mark.parametrize(
    "name",
    ["inquiries:tech_option_edit", "inquiries:tech_option_delete", "inquiries:tech_option_move"],
)
def test_foreign_option_returns_404(org, other_org, owner, login, name):
    foreign = TechOption.objects.for_org(other_org).first()
    client = login(owner.user, org)

    assert client.post(reverse(name, args=[foreign.pk]), {"name": "Gekapert"}).status_code == 404

    foreign.refresh_from_db()
    assert foreign.name != "Gekapert"


def test_create_appends_and_move_reorders(org, owner, login):
    client = login(owner.user, org)

    client.post(reverse(LIST_URL), {"name": "Nebelmaschine"})
    assert _names(org)[-1] == "Nebelmaschine"

    new = TechOption.objects.for_org(org).get(name="Nebelmaschine")
    client.post(reverse("inquiries:tech_option_move", args=[new.pk]), {"richtung": "-1"})
    assert _names(org)[-2] == "Nebelmaschine"


def test_list_can_be_emptied_and_page_still_renders(org, owner, login):
    client = login(owner.user, org)
    for item in TechOption.objects.for_org(org):
        client.post(reverse("inquiries:tech_option_delete", args=[item.pk]))

    assert _names(org) == []
    assert client.get(reverse(LIST_URL)).status_code == 200


# ---------- Migration ----------


def test_migration_converts_old_keys_and_seeds_orgs(org, make_inquiry):
    migration = import_module("apps.inquiries.migrations.0002_techoption")
    TechOption.objects.for_org(org).delete()
    inquiry = make_inquiry(org, tech_needs=["mikrofone", "beamer", "unbekannt"])

    migration.forwards(django_apps, None)

    inquiry.refresh_from_db()
    assert inquiry.tech_needs == ["Mikrofone", "Beamer und Leinwand", "unbekannt"]
    assert _names(org) == DEFAULT_TECH_OPTIONS
    assert TechOption.objects.count() == 5 * Organization.objects.count()

    migration.backwards(django_apps, None)

    inquiry.refresh_from_db()
    assert inquiry.tech_needs == ["mikrofone", "beamer", "unbekannt"]
