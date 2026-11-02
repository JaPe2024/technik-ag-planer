import io
import json
import zipfile

import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations import services
from apps.organizations.export import export_organization
from apps.organizations.models import Invitation, Organization
from apps.organizations.permissions import Role


@pytest.fixture
def operator(db):
    return User.objects.create_superuser("betreiber@example.org", "Betreiber-Passwort-1")


@pytest.fixture
def admin_client(operator, login):
    return login(operator)


def test_creating_org_sends_owner_invitation(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.post(
            reverse("admin:organizations_organization_add"),
            {
                "name": "Technik-AG West",
                "is_active": "on",
                "owner_email": "owner@example.org",
                "memberships-TOTAL_FORMS": "0",
                "memberships-INITIAL_FORMS": "0",
                "invitations-TOTAL_FORMS": "0",
                "invitations-INITIAL_FORMS": "0",
            },
        )

    assert response.status_code == 302, response.content.decode()[:2000]
    org = Organization.objects.get(name="Technik-AG West")
    invitation = Invitation.objects.for_org(org).get()
    assert invitation.role == Role.OWNER
    assert invitation.email == "owner@example.org"
    assert mail.outbox[0].to == ["owner@example.org"]


def test_operator_cannot_be_entered_as_owner(admin_client, operator):
    response = admin_client.post(
        reverse("admin:organizations_organization_add"),
        {
            "name": "Technik-AG West",
            "is_active": "on",
            "owner_email": operator.email.upper(),
            "memberships-TOTAL_FORMS": "0",
            "memberships-INITIAL_FORMS": "0",
            "invitations-TOTAL_FORMS": "0",
            "invitations-INITIAL_FORMS": "0",
        },
    )

    assert response.status_code == 200
    assert services.OPERATOR_NOT_ALLOWED in response.content.decode()
    assert not Organization.objects.filter(name="Technik-AG West").exists()
    assert not Invitation.objects.exists()


def test_members_cannot_access_admin(member_client, owner, login, org):
    for client in (member_client, login(owner.user, org)):
        response = client.get(reverse("admin:index"))
        assert response.status_code == 302
        assert "login" in response.url


def test_operator_reaches_admin(admin_client):
    assert admin_client.get(reverse("admin:index")).status_code == 200


def test_export_contains_only_this_organization(org, other_org, make_member):
    make_member(org, Role.OWNER, display_name="Nora Nord")
    make_member(other_org, Role.OWNER, display_name="Sam Süd")
    services.invite(org, "neu-nord@example.org", Role.STUDENT, send=False)
    services.invite(other_org, "neu-sued@example.org", Role.STUDENT, send=False)

    archive = zipfile.ZipFile(io.BytesIO(export_organization(org)))
    content = {name: json.loads(archive.read(name)) for name in archive.namelist()}
    dump = json.dumps(content, ensure_ascii=False)

    assert content["ag.json"]["name"] == org.name
    assert "Nora Nord" in dump
    assert "neu-nord@example.org" in dump
    assert "Sam Süd" not in dump
    assert "neu-sued@example.org" not in dump
    assert "token_hash" not in dump
    assert "password" not in dump


def test_admin_export_action(admin_client, org):
    response = admin_client.post(
        reverse("admin:organizations_organization_changelist"),
        {"action": "export_data", "_selected_action": [org.pk]},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"


def test_operator_changes_owner_to_existing_member(admin_client, org, owner, make_member):
    admin = make_member(org, Role.ADMIN)
    admin_client.post(
        reverse("admin:organizations_organization_change", args=[org.pk]),
        {
            "name": org.name,
            "is_active": "on",
            "owner_email": admin.user.email,
            "memberships-TOTAL_FORMS": "2",
            "memberships-INITIAL_FORMS": "2",
            "memberships-0-id": owner.pk,
            "memberships-0-organization": org.pk,
            "memberships-0-role": Role.OWNER,
            "memberships-1-id": admin.pk,
            "memberships-1-organization": org.pk,
            "memberships-1-role": Role.ADMIN,
            "invitations-TOTAL_FORMS": "0",
            "invitations-INITIAL_FORMS": "0",
        },
    )

    owner.refresh_from_db()
    admin.refresh_from_db()
    assert admin.role == Role.OWNER
    assert owner.role == Role.ADMIN
