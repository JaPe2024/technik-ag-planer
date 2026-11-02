from django.urls import path

from . import views

app_name = "inquiries"

urlpatterns = [
    path("anfrage/<str:token>/", views.public_form, name="public"),
    path("anfrage/<str:token>/danke/", views.public_thanks, name="public_thanks"),
    path("anfragen/<int:pk>/", views.inquiry_detail, name="detail"),
    path("anfragen/<int:pk>/erledigt/", views.inquiry_done, name="done"),
    path("anfragen/<int:pk>/nachfrage/", views.inquiry_followup, name="followup"),
    path("anfragen/erledigt/", views.done_list, name="done_list"),
    path("einstellungen/technik-anfragen/", views.link_settings, name="settings"),
    path("einstellungen/technik-auswahl/", views.tech_options, name="tech_options"),
    path(
        "einstellungen/technik-auswahl/<int:pk>/", views.tech_option_edit, name="tech_option_edit"
    ),
    path(
        "einstellungen/technik-auswahl/<int:pk>/loeschen/",
        views.tech_option_delete,
        name="tech_option_delete",
    ),
    path(
        "einstellungen/technik-auswahl/<int:pk>/verschieben/",
        views.tech_option_move,
        name="tech_option_move",
    ),
]
