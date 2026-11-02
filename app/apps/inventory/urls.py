from django.urls import path

from . import unit_views, views

app_name = "inventory"

urlpatterns = [
    path("material/etiketten/", unit_views.labels, name="labels"),
    path("material/<int:pk>/ausleihen/", unit_views.checkout, name="checkout"),
    path("ausleihen/<int:pk>/zurueck/", unit_views.checkin, name="checkin"),
    path("geraet/<str:code>/", unit_views.device, name="device"),
    path("geraete/<int:pk>/aktion/", unit_views.unit_action, name="unit_action"),
    path("geraete/<int:pk>/defekt/", unit_views.unit_defect, name="unit_defect"),
    path("geraete/defekte/<int:pk>/status/", unit_views.resolve_defect, name="unit_defect_status"),
    path("produktionen/<int:pk>/reservieren/", unit_views.reserve, name="reserve_unit"),
    path("reservierungen/<int:pk>/aufheben/", unit_views.cancel, name="cancel_reservation"),
    path("produktionen/<int:pk>/abbau/", unit_views.teardown, name="teardown"),
    path("produktionen/<int:pk>/abbau-protokoll/", unit_views.protocol, name="teardown_protocol"),
    path("material/<int:pk>/geraete/", unit_views.units, name="units"),
    path("material/<int:pk>/geraete/neu/", unit_views.create_unit, name="unit_create"),
    path("geraete/<int:pk>/qr/", unit_views.qr, name="unit_qr"),
    path("produktionen/<int:pk>/scan/", unit_views.scan, name="scan"),
    path("material/", views.material_list, name="list"),
    path("material/neu/", views.material_create, name="create"),
    path("material/<int:pk>/", views.material_detail, name="detail"),
    path("material/<int:pk>/bearbeiten/", views.material_edit, name="edit"),
    path("material/<int:pk>/archivieren/", views.material_archive, name="archive"),
    path("material/<int:pk>/defekt/", views.defect_report, name="defect_report"),
    path("defekte/<int:pk>/status/", views.defect_status, name="defect_status"),
    path("material/saetze/", views.kit_list, name="kits"),
    path("material/saetze/neu/", views.kit_create, name="kit_create"),
    path("material/saetze/<int:pk>/bearbeiten/", views.kit_edit, name="kit_edit"),
    path("material/saetze/<int:pk>/kopieren/", views.kit_copy, name="kit_copy"),
    path("material/saetze/<int:pk>/loeschen/", views.kit_delete, name="kit_delete"),
    path("produktionen/<int:pk>/material/neu/", views.plan_material, name="plan"),
    path("produktionen/<int:pk>/material/satz/", views.plan_kit, name="plan_kit"),
    path("produktionen/<int:pk>/packliste/", views.packing_list, name="packing_list"),
    path("geplant/<int:pk>/bearbeiten/", views.planned_edit, name="planned_edit"),
    path("geplant/<int:pk>/entfernen/", views.planned_remove, name="planned_remove"),
    path("geplant/<int:pk>/abhaken/", views.packing_toggle, name="packing_toggle"),
    path("einstellungen/material-kategorien/", views.categories, name="categories"),
    path(
        "einstellungen/material-kategorien/<int:pk>/",
        views.category_edit,
        name="category_edit",
    ),
    path(
        "einstellungen/material-kategorien/<int:pk>/loeschen/",
        views.category_delete,
        name="category_delete",
    ),
    path(
        "einstellungen/material-kategorien/<int:pk>/verschieben/",
        views.category_move,
        name="category_move",
    ),
]
