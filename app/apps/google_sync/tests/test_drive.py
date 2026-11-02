"""Dateien im Google Drive: hochladen, öffnen, löschen, Fehlermeldungen, Rechte."""

import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.google_sync import drive
from apps.google_sync.google_api import QUOTA, GoogleError
from apps.google_sync.models import Attachment
from apps.organizations.permissions import Role
from apps.productions.models import Production, ProductionLink

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
PDF = b"%PDF-1.4 test"


def _file(name="buehnenplan.pdf", content=PDF, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.fixture
def concert(org, make_production):
    return make_production(org, "Schulkonzert")


def test_upload_to_production_folder(org, connected, google, concert, planner_client):
    url = reverse("google_sync:production_upload", args=[concert.pk])
    response = planner_client.post(url, {"file": _file()})

    attachment = Attachment.objects.get()
    assert response.url.endswith("#dateien")
    assert (attachment.production, attachment.name, attachment.size) == (
        concert,
        "buehnenplan.pdf",
        len(PDF),
    )
    assert google.path_of(attachment.drive_file_id) == (
        f"Technik-AG Planer – Technik-AG Nord/Produktionen/Schulkonzert "
        f"({concert.start_date:%d.%m.%Y})"
    )
    detail = planner_client.get(reverse("productions:detail", args=[concert.pk])).content.decode()
    assert "buehnenplan.pdf" in detail


def test_open_file(org, connected, google, concert, student_client, other_org, make_member, login):
    attachment = drive.upload(org, _file(), production=concert)
    response = student_client.get(reverse("google_sync:open", args=[attachment.pk]))
    assert response.content == PDF
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("inline")

    stranger = login(make_member(other_org, Role.OWNER).user, other_org)
    assert stranger.get(reverse("google_sync:open", args=[attachment.pk])).status_code == 404


def test_html_is_never_shown_inline(org, connected, google, concert, student_client):
    attachment = drive.upload(
        org, _file("x.html", b"<script>alert(1)</script>", "text/html"), production=concert
    )
    response = student_client.get(reverse("google_sync:open", args=[attachment.pk]))
    assert response["Content-Type"] == "application/octet-stream"
    assert response["Content-Disposition"].startswith("attachment")


def test_too_large(org, connected, google, concert, planner_client, settings):
    settings.GOOGLE_UPLOAD_MAX_MB = 1
    url = reverse("google_sync:production_upload", args=[concert.pk])
    response = planner_client.post(url, {"file": _file(content=b"0" * (1024 * 1024 + 1))})
    assert "zu groß" in response.content.decode()
    assert not Attachment.objects.exists()


def test_not_connected(org, google, concert, planner_client):
    url = reverse("google_sync:production_upload", args=[concert.pk])
    assert "Kein Google-Konto verbunden" in planner_client.get(url).content.decode()
    response = planner_client.post(url, {"file": _file()}, follow=True)
    assert "Kein Google-Konto verbunden" in response.content.decode()
    assert not Attachment.objects.exists()


def test_quota_full(org, connected, google, concert, planner_client):
    drive.upload(org, _file(), production=concert)  # Ordner existieren schon
    google.fail_with = GoogleError(QUOTA, "quota")
    url = reverse("google_sync:production_upload", args=[concert.pk])
    response = planner_client.post(url, {"file": _file()}, follow=True)
    assert "Google-Drive-Speicher ist voll" in response.content.decode()
    assert Attachment.objects.count() == 1


def test_deleted_folder_is_recreated(org, connected, google, concert):
    drive.upload(org, _file(), production=concert)
    google.folders.clear()
    attachment = drive.upload(org, _file("zwei.pdf"), production=concert)
    assert google.path_of(attachment.drive_file_id).endswith(f"({concert.start_date:%d.%m.%Y})")


def test_delete_removes_drive_file(org, connected, google, concert, planner_client, student_client):
    attachment = drive.upload(org, _file(), production=concert)
    url = reverse("google_sync:delete", args=[attachment.pk])
    assert student_client.post(url).status_code == 403
    planner_client.post(url)
    assert not Attachment.objects.exists() and not google.files


def test_dissolving_org_keeps_drive_files(org, connected, google, concert):
    from apps.organizations import services

    drive.upload(org, _file(), production=concert)
    services.dissolve(org, org.name)  # auch mit Produktionen möglich
    assert len(google.files) == 1


def test_purge_deletes_drive_files(org, connected, google, concert):
    drive.upload(org, _file(), production=concert)
    concert.soft_delete()
    Production.all_objects.filter(pk=concert.pk).update(
        deleted_at=timezone.now() - timedelta(days=8)
    )
    from apps.productions.tasks import purge_deleted_productions

    pk = concert.pk
    connected.refresh_from_db()
    folder = connected.folder_ids[f"production:{pk}"]

    purge_deleted_productions()

    assert not google.files
    assert folder not in google.folders
    connected.refresh_from_db()
    assert f"production:{pk}" not in connected.folder_ids


def test_purge_keeps_going_when_folder_cannot_be_removed(org, connected, google, concert):
    drive.upload(org, _file(), production=concert)
    concert.soft_delete()
    Production.all_objects.filter(pk=concert.pk).update(
        deleted_at=timezone.now() - timedelta(days=8)
    )
    from apps.google_sync.google_api import GoogleError
    from apps.productions.tasks import purge_deleted_productions

    original = google.delete_file

    def delete_then_fail(file_id):
        original(file_id)
        google.fail_with = GoogleError("Nicht erreichbar")

    google.delete_file = delete_then_fail

    assert purge_deleted_productions() == 1
    assert not Production.all_objects.filter(pk=concert.pk).exists()


def test_material_upload_and_defect_photo(org, connected, google, owner, login, make_material):
    material = make_material(org, "Lichtpult")
    client = login(owner.user, org)
    client.post(reverse("google_sync:material_upload", args=[material.pk]), {"file": _file()})
    client.post(
        reverse("inventory:defect_report", args=[material.pk]),
        {"quantity": "1", "description": "Fader klemmt", "photo": _file("f.png", PNG, "image/png")},
    )
    files = Attachment.objects.order_by("pk")
    assert files[0].material == material
    assert files[1].defect.material == material
    assert google.path_of(files[1].drive_file_id).endswith("/Material")
    content = client.get(reverse("inventory:detail", args=[material.pk])).content.decode()
    assert "buehnenplan.pdf" in content and "Foto" in content


def test_defect_photo_must_be_image(org, connected, google, owner, login, make_material):
    material = make_material(org)
    login(owner.user, org).post(
        reverse("inventory:defect_report", args=[material.pk]),
        {"quantity": "1", "description": "kaputt", "photo": _file()},
    )
    assert not material.defects.exists()


@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT])
def test_upload_rights(org, connected, google, concert, make_member, login, role):
    client = login(make_member(org, role).user, org)
    expected = 403 if role == Role.STUDENT else 200
    url = reverse("google_sync:production_upload", args=[concert.pk])
    assert client.get(url).status_code == expected


def test_foreign_targets_return_404(
    org, other_org, owner, login, connected, google, make_production
):
    foreign = make_production(other_org)
    client = login(owner.user, org)
    assert (
        client.get(reverse("google_sync:production_upload", args=[foreign.pk])).status_code == 404
    )


# ---------- Links im Abschnitt „Dateien“ ----------


def test_production_links(org, concert, planner_client, student_client, other_org, make_production):
    url = reverse("productions:link_create", args=[concert.pk])
    planner_client.post(url, {"title": "Bühnenplan", "url": "example.org/plan"})
    link = ProductionLink.objects.get()
    assert link.url == "https://example.org/plan"
    assert (
        "Bühnenplan"
        in student_client.get(reverse("productions:detail", args=[concert.pk])).content.decode()
    )
    assert student_client.get(url).status_code == 403
    assert (
        student_client.post(reverse("productions:link_delete", args=[link.pk])).status_code == 403
    )

    foreign = make_production(other_org)
    assert (
        planner_client.get(reverse("productions:link_create", args=[foreign.pk])).status_code == 404
    )

    planner_client.post(reverse("productions:copy", args=[concert.pk]))
    assert ProductionLink.objects.count() == 2  # Kopie übernimmt die Links

    planner_client.post(reverse("productions:link_delete", args=[link.pk]))
    assert ProductionLink.objects.count() == 1


# ---------- PDF im öffentlichen Anfrage-Formular ----------


def _inquiry_data(**extra):
    return {
        "requester_name": "Frau Muster",
        "requester_email": "muster@schule.example",
        "date": (timezone.localdate() + timedelta(days=10)).isoformat(),
        **extra,
    }


@pytest.fixture
def inquiry_link(org):
    from apps.inquiries.services import link_for

    link = link_for(org)
    link.is_active = True
    link.save()
    return link


def test_inquiry_pdf_upload(org, connected, google, inquiry_link, planner_client):
    url = reverse("inquiries:public", args=[inquiry_link.token])
    assert "Ablauf als PDF" in Client().get(url).content.decode()
    Client().post(url, _inquiry_data(schedule_pdf=_file("ablauf.pdf")))
    attachment = Attachment.objects.get()
    assert attachment.inquiry.event_name == "" or attachment.inquiry is not None
    assert google.path_of(attachment.drive_file_id).endswith("/Anfragen")
    detail = planner_client.get(reverse("inquiries:detail", args=[attachment.inquiry_id]))
    assert "ablauf.pdf" in detail.content.decode()


def test_inquiry_rejects_non_pdf(org, connected, google, inquiry_link):
    from apps.inquiries.models import Inquiry

    url = reverse("inquiries:public", args=[inquiry_link.token])
    Client().post(url, _inquiry_data(schedule_pdf=_file("x.pdf", b"MZ evil", "application/pdf")))
    assert not Inquiry.objects.exists()


def test_inquiry_without_google_has_no_upload(org, google, inquiry_link):
    url = reverse("inquiries:public", args=[inquiry_link.token])
    assert "Ablauf als PDF" not in Client().get(url).content.decode()


def test_inquiry_pdf_only_for_inquiry_handlers(
    org, connected, google, inquiry_link, student_client, make_inquiry=None
):
    from apps.inquiries.models import Inquiry

    inquiry = Inquiry.objects.create(
        organization=org,
        requester_name="X",
        requester_email="x@example.org",
        date=timezone.localdate(),
    )
    attachment = drive.upload(org, _file(), inquiry=inquiry)
    assert student_client.get(reverse("google_sync:open", args=[attachment.pk])).status_code == 403


def test_beispieldaten_still_work(db, settings):
    settings.DEBUG = True
    call_command("beispieldaten", stdout=io.StringIO())
