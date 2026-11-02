import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import Role


@pytest.fixture
def owner_client(owner, login, org):
    return login(owner.user, org)


def test_only_one_owner_per_organization(org, owner, make_member):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_member(org, Role.OWNER)


def test_transfer_ownership(org, owner, owner_client, make_member):
    admin = make_member(org, Role.ADMIN)

    owner_client.post(reverse("organizations:transfer_ownership"), {"membership": admin.pk})

    admin.refresh_from_db()
    owner.refresh_from_db()
    assert admin.role == Role.OWNER
    assert owner.role == Role.ADMIN


def test_teacher_cannot_become_owner(org, owner, owner_client, make_member):
    teacher = make_member(org, Role.TEACHER)

    owner_client.post(reverse("organizations:transfer_ownership"), {"membership": teacher.pk})

    teacher.refresh_from_db()
    assert teacher.role == Role.TEACHER


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner_can_transfer_or_dissolve(org, owner, make_member, login, role):
    membership = make_member(org, role)
    client = login(membership.user, org)

    assert (
        client.post(
            reverse("organizations:transfer_ownership"), {"membership": membership.pk}
        ).status_code
        == 403
    )
    assert (
        client.post(reverse("organizations:dissolve"), {"confirm_name": org.name}).status_code
        == 403
    )
    assert (
        client.post(reverse("organizations:require_2fa"), {"require_2fa": "on"}).status_code == 403
    )
    assert Organization.objects.filter(pk=org.pk).exists()


def test_owner_cannot_leave_without_transfer(org, owner, owner_client):
    owner_client.post(reverse("organizations:leave"))
    assert Membership.objects.filter(pk=owner.pk).exists()


def test_member_can_leave(org, make_member, login):
    membership = make_member(org, Role.STUDENT)
    login(membership.user, org).post(reverse("organizations:leave"))
    assert not Membership.objects.filter(pk=membership.pk).exists()


def test_dissolve_needs_exact_name(org, owner_client):
    owner_client.post(reverse("organizations:dissolve"), {"confirm_name": "falsch"})
    assert Organization.objects.filter(pk=org.pk).exists()

    owner_client.post(reverse("organizations:dissolve"), {"confirm_name": org.name})
    assert not Organization.objects.filter(pk=org.pk).exists()


def test_owner_changes_role_and_removes_member(org, owner_client, make_member):
    member = make_member(org, Role.STUDENT)

    owner_client.post(reverse("organizations:member_role", args=[member.pk]), {"role": Role.ADMIN})
    member.refresh_from_db()
    assert member.role == Role.ADMIN

    owner_client.post(reverse("organizations:member_remove", args=[member.pk]))
    assert not Membership.objects.filter(pk=member.pk).exists()


def test_owner_role_cannot_be_changed_via_role_form(org, owner, owner_client):
    owner_client.post(reverse("organizations:member_role", args=[owner.pk]), {"role": Role.STUDENT})
    owner.refresh_from_db()
    assert owner.role == Role.OWNER


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_non_owners_cannot_change_roles(org, make_member, login, role):
    actor = make_member(org, role)
    target = make_member(org, Role.STUDENT)

    response = login(actor.user, org).post(
        reverse("organizations:member_role", args=[target.pk]), {"role": Role.ADMIN}
    )

    assert response.status_code == 403
    target.refresh_from_db()
    assert target.role == Role.STUDENT


def test_members_page_visible_to_all_members(member_client):
    response = member_client.get(reverse("organizations:members"))

    assert response.status_code == 200
    assert "Mitglied einladen" not in response.content.decode()


def test_settings_show_role_badge_and_groups(owner_client):
    content = owner_client.get(reverse("organizations:settings")).content.decode()

    for text in ["Owner", "AG anpassen", "Für mich", "Konto", "Abmelden"]:
        assert text in content


def test_settings_hide_owner_entries_for_students(member_client):
    content = member_client.get(reverse("organizations:settings")).content.decode()

    assert "Schüler/in" in content
    assert "Zwei-Faktor für alle Mitglieder" not in content
    assert "Stundenraster" not in content


def test_dissolve_with_productions(org, owner_client, make_production, make_job):
    """Früher scheiterte das Auflösen am geschützten Status der Produktionen."""
    from apps.organizations.models import Organization

    make_job(make_production(org))
    owner_client.post(reverse("organizations:dissolve"), {"confirm_name": org.name})
    assert not Organization.objects.filter(pk=org.pk).exists()


CUSTOMIZE = "organizations:customize"


def test_customize_page_collects_org_settings_for_owner(owner_client):
    content = owner_client.get(reverse(CUSTOMIZE)).content.decode()

    for text in [
        "Produktionen",
        "Material",
        "Technik-Anfragen",
        "Schule",
        "Verbindungen und Sicherheit",
        "Kategorien",
        "Status-Werte",
        "Fähigkeiten",
        "Material-Kategorien",
        "Technik anfragen",
        "Technik-Auswahl",
        "Stundenraster",
        "Schuljahreswechsel",
        "Google-Konto",
        "Zwei-Faktor für alle Mitglieder",
    ]:
        assert text in content


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMIN, ["Kategorien", "Material-Kategorien", "Technik anfragen", "Technik-Auswahl"]),
        (Role.TEACHER, ["Technik-Auswahl"]),
    ],
)
def test_customize_shows_only_allowed_entries(org, make_member, login, role, expected):
    response = login(make_member(org, role).user, org).get(reverse(CUSTOMIZE))

    labels = [e.label for _, entries in response.context["groups"] for e in entries]
    assert labels == expected


def test_students_have_no_customize_page(org, make_member, login):
    client = login(make_member(org, Role.STUDENT).user, org)

    assert client.get(reverse(CUSTOMIZE)).status_code == 403
    assert "AG anpassen" not in client.get(reverse("organizations:settings")).content.decode()


def test_settings_rows_are_whole_links(owner_client):
    for url in ["organizations:settings", CUSTOMIZE]:
        content = owner_client.get(reverse(url)).content.decode()
        assert '<a class="list__item list__link"' in content


def test_customize_subpages_link_back_to_customize(owner_client):
    content = owner_client.get(reverse("organizations:school_year")).content.decode()

    assert "← AG anpassen" in content
    assert "← Einstellungen" in owner_client.get(reverse("organizations:members")).content.decode()
