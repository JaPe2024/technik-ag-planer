from django.urls import path

from . import views

app_name = "organizations"

urlpatterns = [
    path("keine-ag/", views.no_organization, name="no_organization"),
    path("ag/wechseln/", views.switch_organization, name="switch"),
    path("einladung/<str:token>/", views.accept_invitation, name="accept_invitation"),
    path("einstellungen/", views.settings_index, name="settings"),
    path("einstellungen/anpassen/", views.customize, name="customize"),
    path("einstellungen/mitglieder/", views.members, name="members"),
    path("einstellungen/mitglieder/einladen/", views.invite, name="invite"),
    path("einstellungen/mitglieder/<int:pk>/rolle/", views.member_role, name="member_role"),
    path("einstellungen/mitglieder/<int:pk>/entfernen/", views.member_remove, name="member_remove"),
    path(
        "einstellungen/einladungen/<int:pk>/erneut-senden/",
        views.invitation_resend,
        name="invitation_resend",
    ),
    path(
        "einstellungen/einladungen/<int:pk>/zurueckziehen/",
        views.invitation_revoke,
        name="invitation_revoke",
    ),
    path("einstellungen/organisation/", views.manage, name="manage"),
    path(
        "einstellungen/organisation/ownership/",
        views.transfer_ownership,
        name="transfer_ownership",
    ),
    path("einstellungen/organisation/verlassen/", views.leave, name="leave"),
    path("einstellungen/organisation/aufloesen/", views.dissolve, name="dissolve"),
    path("einstellungen/zwei-faktor-pflicht/", views.require_2fa, name="require_2fa"),
    path("einstellungen/schuljahreswechsel/", views.school_year, name="school_year"),
]
