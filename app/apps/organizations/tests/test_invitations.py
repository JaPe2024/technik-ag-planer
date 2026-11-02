from datetime import timedelta

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations import services
from apps.organizations.models import Invitation, Membership
from apps.organizations.permissions import Role

NEW_PASSWORD = "Ganz-neues-Passwort-42"


def _token_from_mail(message):
    url = next(line for line in message.body.splitlines() if "/einladung/" in line)
    return url.rstrip("/").rsplit("/", 1)[1]


@pytest.fixture
def owner_client(owner, login, org):
    return login(owner.user, org)


def test_owner_invites_and_mail_contains_link(
    owner_client, org, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = owner_client.post(
            reverse("organizations:invite"), {"email": "Emma@Example.org", "role": Role.STUDENT}
        )

    assert response.status_code == 302
    invitation = Invitation.objects.for_org(org).get()
    assert invitation.email == "emma@example.org"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["emma@example.org"]
    assert "/einladung/" in mail.outbox[0].body
    # Token liegt nur als Hash in der Datenbank
    assert _token_from_mail(mail.outbox[0]) not in invitation.token_hash


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER, Role.STUDENT])
def test_only_owner_may_invite(org, make_member, login, role):
    membership = make_member(org, role)
    response = login(membership.user, org).post(
        reverse("organizations:invite"), {"email": "x@example.org", "role": Role.STUDENT}
    )

    assert response.status_code == 403
    assert not Invitation.objects.exists()


def test_owner_cannot_invite_another_owner(owner_client):
    owner_client.post(reverse("organizations:invite"), {"email": "x@example.org", "role": "owner"})
    assert not Invitation.objects.exists()


def test_accept_creates_account_with_grade(org, client):
    invitation, token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    url = reverse("organizations:accept_invitation", args=[token])

    response = client.post(
        url,
        {
            "display_name": "Emma",
            "grade": "Q1",
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
        },
    )

    assert response.status_code == 302
    user = User.objects.get(email="emma@example.org")
    assert user.display_name == "Emma"
    assert user.grade == "Q1"
    assert user.check_password(NEW_PASSWORD)
    assert Membership.objects.get(user=user, organization=org).role == Role.STUDENT
    invitation.refresh_from_db()
    assert invitation.accepted_at is not None
    # direkt angemeldet
    assert client.get(reverse("productions:dashboard")).status_code == 200


def test_grade_is_required_for_students(org, client):
    _, token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    response = client.post(
        reverse("organizations:accept_invitation", args=[token]),
        {"display_name": "Emma", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
    )

    assert response.status_code == 200
    assert "grade" in response.context["form"].errors
    assert not User.objects.filter(email="emma@example.org").exists()


def test_teachers_are_not_asked_for_grade(org, client):
    _, token = services.invite(org, "lehrer@example.org", Role.TEACHER, send=False)
    url = reverse("organizations:accept_invitation", args=[token])

    assert "grade" not in client.get(url).context["form"].fields
    client.post(
        url, {"display_name": "Herr Muster", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )
    assert User.objects.get(email="lehrer@example.org").grade == ""


def test_link_works_only_once(org, client):
    _, token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    url = reverse("organizations:accept_invitation", args=[token])
    data = {
        "display_name": "Emma",
        "grade": "7",
        "password1": NEW_PASSWORD,
        "password2": NEW_PASSWORD,
    }
    client.post(url, data)
    client.logout()

    response = client.get(url)

    assert response.status_code == 410
    assert "bereits angenommen" in response.content.decode()


def test_expired_link(org, client):
    invitation, token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    invitation.expires_at = timezone.now() - timedelta(minutes=1)
    invitation.save()

    response = client.get(reverse("organizations:accept_invitation", args=[token]))

    assert response.status_code == 410
    assert "abgelaufen" in response.content.decode()


@pytest.fixture
def operator(db):
    return User.objects.create_superuser("betreiber@example.org", "Betreiber-Passwort-1")


def test_owner_cannot_invite_operator(owner_client, org, operator):
    response = owner_client.post(
        reverse("organizations:invite"),
        {"email": "BETREIBER@example.org", "role": Role.STUDENT},
        follow=True,
    )

    assert not Invitation.objects.for_org(org).exists()
    assert services.OPERATOR_NOT_ALLOWED in response.content.decode()


@pytest.mark.parametrize(
    "flags", [{"is_staff": True}, {"is_superuser": True}], ids=["staff", "superuser"]
)
def test_invite_service_rejects_every_operator_kind(org, flags):
    User.objects.create_user("b@example.org", "Betreiber-Passwort-1", **flags)

    with pytest.raises(ValidationError):
        services.invite(org, "b@example.org", Role.STUDENT, send=False)


def _invitation_before_promotion(org, operator):
    """Einladung von vor der Betreiber-Ernennung: Konto war da noch normal."""
    User.objects.filter(pk=operator.pk).update(is_staff=False, is_superuser=False)
    invitation, token = services.invite(org, operator.email, Role.STUDENT, send=False)
    User.objects.filter(pk=operator.pk).update(is_staff=True, is_superuser=True)
    operator.refresh_from_db()
    return invitation, token


def test_operator_cannot_accept_old_invitation(org, operator, login):
    invitation, token = _invitation_before_promotion(org, operator)
    client = login(operator)
    url = reverse("organizations:accept_invitation", args=[token])

    assert client.get(url).status_code == 410
    response = client.post(url)

    assert response.status_code == 410
    assert services.OPERATOR_NOT_ALLOWED in response.content.decode()
    assert not Membership.objects.filter(user=operator).exists()
    invitation.refresh_from_db()
    assert invitation.accepted_at is None


def test_accept_service_rejects_operator(org, operator):
    invitation, _ = _invitation_before_promotion(org, operator)

    with pytest.raises(ValidationError):
        services.accept(invitation, operator)

    assert not Membership.objects.filter(user=operator).exists()


def test_resend_rejects_operator(org, operator):
    invitation, _ = _invitation_before_promotion(org, operator)

    with pytest.raises(ValidationError):
        services.resend(invitation)


def test_operator_member_cannot_become_owner(org, owner, operator):
    membership = Membership.objects.create(organization=org, user=operator, role=Role.ADMIN)

    with pytest.raises(ValidationError):
        services.make_owner(membership)

    owner.refresh_from_db()
    assert owner.role == Role.OWNER


def test_existing_normal_account_still_joins_with_one_click(org, other_org, make_member, login):
    member = make_member(other_org, Role.STUDENT)
    _, token = services.invite(org, member.user.email, Role.STUDENT, send=False)

    response = login(member.user).post(reverse("organizations:accept_invitation", args=[token]))

    assert response.status_code == 302
    assert Membership.objects.for_org(org).filter(user=member.user).exists()


def test_invitation_is_valid_for_seven_days(org):
    invitation, _ = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    assert timedelta(days=6, hours=23) < invitation.expires_at - timezone.now() <= timedelta(days=7)


def test_revoked_link(org, owner_client, client):
    invitation, token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    owner_client.post(reverse("organizations:invitation_revoke", args=[invitation.pk]))

    response = client.get(reverse("organizations:accept_invitation", args=[token]))

    assert response.status_code == 410
    assert "zurückgezogen" in response.content.decode()


def test_resend_invalidates_old_link(org, owner_client, client, django_capture_on_commit_callbacks):
    invitation, old_token = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    with django_capture_on_commit_callbacks(execute=True):
        owner_client.post(reverse("organizations:invitation_resend", args=[invitation.pk]))

    new_token = _token_from_mail(mail.outbox[-1])
    assert new_token != old_token
    assert (
        client.get(reverse("organizations:accept_invitation", args=[old_token])).status_code == 410
    )
    assert (
        client.get(reverse("organizations:accept_invitation", args=[new_token])).status_code == 200
    )


def test_new_invitation_replaces_open_one(org):
    first, _ = services.invite(org, "emma@example.org", Role.STUDENT, send=False)
    services.invite(org, "emma@example.org", Role.ADMIN, send=False)

    first.refresh_from_db()
    assert first.revoked_at is not None
    assert Invitation.objects.for_org(org).open().get().role == Role.ADMIN


def test_cannot_invite_existing_member(org, owner):
    with pytest.raises(Exception, match="bereits Mitglied"):
        services.invite(org, owner.user.email.upper(), Role.STUDENT, send=False)


def test_existing_account_joins_after_login(org, other_org, make_member, login):
    existing = make_member(other_org, Role.STUDENT)
    _, token = services.invite(org, existing.user.email, Role.ADMIN, send=False)
    url = reverse("organizations:accept_invitation", args=[token])
    client = login(existing.user)

    response = client.post(url)

    assert response.status_code == 302
    assert Membership.objects.get(user=existing.user, organization=org).role == Role.ADMIN
    assert client.session["active_organization_id"] == org.pk


def test_existing_account_is_asked_to_log_in(org, other_org, make_member, client):
    existing = make_member(other_org, Role.STUDENT)
    _, token = services.invite(org, existing.user.email, Role.STUDENT, send=False)

    response = client.get(reverse("organizations:accept_invitation", args=[token]))

    assert response.status_code == 200
    assert "gibt es schon ein Konto" in response.content.decode()


def test_wrong_logged_in_account_cannot_accept(org, make_member, make_user, login):
    other = make_user()
    existing = make_user()
    _, token = services.invite(org, existing.email, Role.STUDENT, send=False)

    login(other).post(reverse("organizations:accept_invitation", args=[token]))

    assert not Membership.objects.filter(organization=org).exists()


def test_owner_invitation_makes_owner_and_demotes_previous(org, owner, client):
    _, token = services.invite(org, "neuer-owner@example.org", Role.OWNER, send=False)
    client.post(
        reverse("organizations:accept_invitation", args=[token]),
        {
            "display_name": "Neu",
            "grade": "Q1",
            "password1": NEW_PASSWORD,
            "password2": NEW_PASSWORD,
        },
    )

    owner.refresh_from_db()
    assert owner.role == Role.ADMIN
    assert org.owner_membership.user.email == "neuer-owner@example.org"
