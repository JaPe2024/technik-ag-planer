"""Seiten rund um Material, Sätze, Planung und Packliste."""

from django.urls import reverse

from apps.board.models import Message
from apps.inventory import services
from apps.inventory.models import DefectReport, Kit, Material, MaterialCategory, PlannedMaterial


def _material_data(org, **overrides):
    data = {
        "name": "Lichtpult",
        "category": MaterialCategory.objects.for_org(org).first().pk,
        "quantity": "2",
        "notes": "Regal 1",
        "links-TOTAL_FORMS": "1",
        "links-INITIAL_FORMS": "0",
        "links-MIN_NUM_FORMS": "0",
        "links-MAX_NUM_FORMS": "1000",
        "links-0-title": "Handbuch",
        "links-0-url": "https://example.org/handbuch.pdf",
    }
    data.update(overrides)
    return data


def test_create_material_with_link(org, planner_client):
    response = planner_client.post(reverse("inventory:create"), _material_data(org))

    material = Material.objects.for_org(org).get()
    assert response.url == reverse("inventory:detail", args=[material.pk])
    assert material.quantity == 2
    assert material.links.get().organization == org
    content = planner_client.get(response.url).content.decode()
    assert "Handbuch" in content and "Regal 1" in content


def test_empty_quantity_means_unlimited(org, planner_client):
    planner_client.post(reverse("inventory:create"), _material_data(org, quantity=""))
    material = Material.objects.for_org(org).get()
    assert material.quantity is None
    assert "beliebig" in planner_client.get(reverse("inventory:list")).content.decode()


def test_form_rejects_category_of_other_org(org, other_org, planner_client):
    foreign = MaterialCategory.objects.for_org(other_org).first()
    planner_client.post(reverse("inventory:create"), _material_data(org, category=foreign.pk))
    assert not Material.objects.exists()


def test_list_search_category_and_filters(org, owner, member_client, make_material):
    lights = MaterialCategory.objects.for_org(org).get(name="Licht")
    desk = make_material(org, "Lichtpult", quantity=1, category=lights)
    audio = MaterialCategory.objects.for_org(org).get(name="Audio")
    mics = make_material(org, "Funkmikrofon", category=audio)
    old = make_material(org, "Altes Pult")
    services.archive(old)
    services.report_defect(mics, 1, "kaputt", owner.user)
    url = reverse("inventory:list")

    content = member_client.get(url).content.decode()
    assert "Lichtpult" in content and "Funkmikrofon" in content and "Altes Pult" not in content
    assert "Funkmikrofon" not in member_client.get(url, {"q": "licht"}).content.decode()
    assert "Funkmikrofon" not in member_client.get(url, {"kategorie": lights.pk}).content.decode()
    defect = member_client.get(url, {"filter": "defekt"}).content.decode()
    assert "Funkmikrofon" in defect and desk.name not in defect
    assert "Altes Pult" in member_client.get(url, {"filter": "archiviert"}).content.decode()


def test_archive_and_restore(org, planner_client, mics):
    planner_client.post(reverse("inventory:archive", args=[mics.pk]))
    mics.refresh_from_db()
    assert mics.is_archived

    planner_client.post(reverse("inventory:archive", args=[mics.pk]))
    mics.refresh_from_db()
    assert not mics.is_archived


def test_student_reports_defect_and_board_announces(org, student_client, mics):
    response = student_client.post(
        reverse("inventory:defect_report", args=[mics.pk]),
        {"quantity": "2", "description": "Kapsel knackt"},
    )
    assert response.status_code == 302
    defect = DefectReport.objects.get()
    assert defect.status == DefectReport.Status.DEFECT and defect.organization == org
    message = Message.objects.for_org(org).get(link_material=mics)
    assert message.text == "Material defekt: Funkmikrofon (× 2)"


def test_defect_quantity_limited_to_available(org, student_client, mics):
    response = student_client.post(
        reverse("inventory:defect_report", args=[mics.pk]),
        {"quantity": "7", "description": "alle"},
    )
    assert response.status_code == 200
    assert "nur noch 6" in response.content.decode()
    assert not DefectReport.objects.exists()


def test_repair_flow_and_board_message(org, owner, planner_client, mics):
    defect = services.report_defect(mics, 1, "kaputt", owner.user)
    url = reverse("inventory:defect_status", args=[defect.pk])

    planner_client.post(url, {"status": "in_repair"})
    defect.refresh_from_db()
    assert defect.status == DefectReport.Status.IN_REPAIR
    assert not Message.objects.filter(text__startswith="Wieder verfügbar").exists()

    planner_client.post(url, {"status": "repaired"})
    defect.refresh_from_db()
    assert defect.status == DefectReport.Status.REPAIRED
    assert (
        Message.objects.for_org(org).get(text="Wieder verfügbar: Funkmikrofon").link_material
        == mics
    )

    board = planner_client.get(reverse("board:index")).content.decode()
    assert reverse("inventory:detail", args=[mics.pk]) in board


def test_plan_material_with_conflict_warning(org, planner_client, mics, make_production):
    other = make_production(org, "Probe")
    services.plan(other, mics, 5)
    production = make_production(org)
    url = reverse("inventory:plan", args=[production.pk])

    response = planner_client.post(url, {"material": mics.pk, "quantity": "2"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Bestand reicht nicht" in content and "Trotzdem einplanen" in content
    assert not production.planned_material.exists()

    response = planner_client.post(
        url, {"material": mics.pk, "quantity": "2", "ignore_conflicts": "on"}
    )
    assert response.status_code == 302
    assert production.planned_material.get().quantity == 2

    detail = planner_client.get(reverse("productions:detail", args=[production.pk]))
    assert "überbucht" in detail.content.decode()
    material_page = planner_client.get(reverse("inventory:detail", args=[mics.pk]))
    assert "überbucht" in material_page.content.decode()


def test_archived_material_cannot_be_planned(org, planner_client, mics, make_production):
    services.archive(mics)
    production = make_production(org)
    planner_client.post(
        reverse("inventory:plan", args=[production.pk]), {"material": mics.pk, "quantity": "1"}
    )
    assert not production.planned_material.exists()


def test_plan_kit_then_adjust_and_remove(
    org, planner_client, mics, make_material, make_kit, make_production
):
    desk = make_material(org, "Mischpult", quantity=1)
    kit = make_kit(org, items=[(mics, 4), (desk, 1)])
    production = make_production(org)

    response = planner_client.post(
        reverse("inventory:plan_kit", args=[production.pk]), {"kit": kit.pk}
    )
    assert response.status_code == 302
    planned = {p.material.name: p for p in production.planned_material.all()}
    assert planned["Funkmikrofon"].quantity == 4

    planner_client.post(
        reverse("inventory:planned_edit", args=[planned["Funkmikrofon"].pk]), {"quantity": "2"}
    )
    planner_client.post(reverse("inventory:planned_remove", args=[planned["Mischpult"].pk]))

    assert [(p.material.name, p.quantity) for p in production.planned_material.all()] == [
        ("Funkmikrofon", 2)
    ]
    assert kit.items.get(material=mics).quantity == 4  # Satz bleibt unverändert


def test_planned_edit_warns_on_overbooking(org, planner_client, mics, make_production):
    production = make_production(org)
    planned = services.plan(production, mics, 2)
    url = reverse("inventory:planned_edit", args=[planned.pk])

    response = planner_client.post(url, {"quantity": "9"})
    assert "Trotzdem speichern" in response.content.decode()
    planned.refresh_from_db()
    assert planned.quantity == 2


def test_kit_create_edit_copy_delete(org, owner, login, mics, make_material):
    client = login(owner.user, org)
    data = {
        "name": "Bühnenlicht Aula",
        "description": "",
        "items-TOTAL_FORMS": "2",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-material": mics.pk,
        "items-0-quantity": "4",
        "items-1-material": "",
        "items-1-quantity": "1",
    }
    client.post(reverse("inventory:kit_create"), data)
    kit = Kit.objects.for_org(org).get()
    item = kit.items.get()
    assert (item.quantity, item.organization) == (4, org)

    # Dasselbe Material zweimal wird abgelehnt
    duplicate = {**data, "items-1-material": mics.pk}
    response = client.post(reverse("inventory:kit_create"), duplicate)
    assert "zweimal" in response.content.decode()

    client.post(reverse("inventory:kit_copy", args=[kit.pk]))
    assert Kit.objects.for_org(org).count() == 2

    client.post(reverse("inventory:kit_delete", args=[kit.pk]))
    assert not Kit.objects.filter(pk=kit.pk).exists()
    assert "Bühnenlicht Aula (Kopie)" in client.get(reverse("inventory:kits")).content.decode()


def test_packing_list_for_all_members(org, student_client, mics, make_production):
    production = make_production(org)
    planned = services.plan(production, mics, 3)
    url = reverse("inventory:packing_list", args=[production.pk])

    assert "Funkmikrofon × 3" in student_client.get(url).content.decode()

    toggle = reverse("inventory:packing_toggle", args=[planned.pk])
    student_client.post(toggle, {"spalte": "ausgabe"})
    planned.refresh_from_db()
    assert planned.issued_at is not None and planned.returned_at is None

    student_client.post(toggle, {"spalte": "rueckgabe"})
    student_client.post(toggle, {"spalte": "ausgabe"})
    planned.refresh_from_db()
    assert planned.issued_at is None and planned.returned_at is not None


def test_production_detail_shows_material_and_packing_list_link(
    org, member_client, mics, make_production
):
    production = make_production(org)
    content = member_client.get(
        reverse("productions:detail", args=[production.pk])
    ).content.decode()
    assert "Noch kein Material eingeplant." in content
    assert "+ Material" not in content  # Schüler/innen planen nicht

    services.plan(production, mics, 2)
    content = member_client.get(
        reverse("productions:detail", args=[production.pk])
    ).content.decode()
    assert "Funkmikrofon × 2" in content
    assert reverse("inventory:packing_list", args=[production.pk]) in content


def test_manage_material_categories(org, owner, login, make_material):
    client = login(owner.user, org)
    client.post(reverse("inventory:categories"), {"name": "Effekte", "color": "lilac"})
    effects = MaterialCategory.objects.for_org(org).get(name="Effekte")
    assert effects.position == 6

    client.post(reverse("inventory:category_move", args=[effects.pk]), {"richtung": "-1"})
    names = list(MaterialCategory.objects.for_org(org).values_list("name", flat=True))
    assert names.index("Effekte") == 5

    material = make_material(org, "Nebelmaschine", category=effects)
    client.post(reverse("inventory:category_delete", args=[effects.pk]))
    material.refresh_from_db()
    assert material.category is None

    assert "Material-Kategorien" in client.get(reverse("organizations:customize")).content.decode()


def test_deleting_production_removes_its_plannings_with_cascade(org, mics, make_production):
    production = make_production(org)
    services.plan(production, mics, 1)
    production.delete()
    assert not PlannedMaterial.objects.exists()
