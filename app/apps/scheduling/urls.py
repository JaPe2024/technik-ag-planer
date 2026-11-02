from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("kalender/", views.calendar_view, name="calendar"),
    path("termine/neu/", views.event_create, name="event_create"),
    path("termine/<int:pk>/", views.event_detail, name="event_detail"),
    path("termine/<int:pk>/bearbeiten/", views.event_edit, name="event_edit"),
    path("termine/<int:pk>/absagen/", views.event_cancel, name="event_cancel"),
    path("termine/<int:pk>/loeschen/", views.event_delete, name="event_delete"),
    path("termine/<int:pk>/leute/", views.event_attendees, name="event_attendees"),
    path("teilnahmen/<int:pk>/entfernen/", views.attendee_remove, name="attendee_remove"),
    path("teilnahmen/<int:pk>/antworten/", views.attendee_respond, name="attendee_respond"),
    path("einstellungen/nicht-verfuegbar/", views.unavailability_list, name="unavailability_list"),
    path(
        "einstellungen/nicht-verfuegbar/neu/",
        views.unavailability_create,
        name="unavailability_create",
    ),
    path(
        "einstellungen/nicht-verfuegbar/<int:pk>/",
        views.unavailability_edit,
        name="unavailability_edit",
    ),
    path(
        "einstellungen/nicht-verfuegbar/<int:pk>/loeschen/",
        views.unavailability_delete,
        name="unavailability_delete",
    ),
    path("einstellungen/stundenraster/", views.periods, name="periods"),
    path("ics/produktion/<int:pk>/", views.ics_production, name="ics_production"),
    path("ics/job/<int:pk>/", views.ics_job, name="ics_job"),
    path("ics/termin/<int:pk>/", views.ics_event, name="ics_event"),
    path("ics/nicht-verfuegbar/<int:pk>/", views.ics_unavailability, name="ics_unavailability"),
    path(
        "privater-kalender/produktion/<int:pk>/",
        views.private_calendar_production,
        name="private_calendar_production",
    ),
    path(
        "privater-kalender/job/<int:pk>/", views.private_calendar_job, name="private_calendar_job"
    ),
    path(
        "privater-kalender/termin/<int:pk>/",
        views.private_calendar_event,
        name="private_calendar_event",
    ),
    path(
        "privater-kalender/nicht-verfuegbar/<int:pk>/",
        views.private_calendar_unavailability,
        name="private_calendar_unavailability",
    ),
]
