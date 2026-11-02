from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .help import topics_for
from .models import LegalPage

SETTINGS = {"active_section": "settings"}

# „Über die App“: alle Funktionen auf einen Blick (Abschnitt 10)
FEATURES = [
    ("Dashboard", "Nächste Produktion, meine Jobs, offene Crew-Anfragen"),
    (
        "Kalender",
        "Monat, Woche, Agenda; Termine und Serien; Stundenraster; „Nicht verfügbar“; "
        "Übernahme in den privaten Kalender",
    ),
    (
        "Produktionen",
        "Jobs, Crew mit Konfliktwarnung, To-dos, Aufsicht, Dateien, Kopieren, Papierkorb",
    ),
    ("Technik-Anfragen", "Öffentlicher Link für Lehrkräfte, geteilte Ansicht Anfrage | Produktion"),
    (
        "Material",
        "Bestand, Defekte mit Foto, Materialsätze, Planung mit Konfliktwarnung, Packliste",
    ),
    ("Board", "Chat der AG mit Systemmeldungen, Chats je Produktion, Moderation"),
    ("PDFs", "Call Sheets, Freistellungsliste, Packliste, Einsatzübersicht – mit Vorschau"),
    ("Team", "Rollen, Einladungen, Fähigkeiten, Einsatzübersicht mit Stunden, Schuljahreswechsel"),
    ("Google", "Dateien im Drive der AG, alle Einträge im Google-Kalender der AG"),
    ("App und Push", "Installierbar auf dem Home-Bildschirm, Push-Mitteilungen und Erinnerungen"),
    ("Sicherheit", "Nur auf Einladung, Zwei-Faktor-Anmeldung, strikte Trennung der AGs"),
]


@login_not_required
@never_cache
def healthz(request):
    """Health-Check für Docker und Caddy: prüft die Datenbankverbindung."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "fehler", "datenbank": False}, status=503)
    return JsonResponse({"status": "ok", "datenbank": True})


def landing(request):
    """Öffentliche Startseite (Abschnitt 12) – über `landing_for_anonymous` an „/“."""
    return render(request, "core/landing.html", {"features": FEATURES})


@login_not_required
def legal(request, kind):
    if kind not in LegalPage.Kind.values:
        raise Http404
    page = LegalPage.objects.filter(kind=kind).first()
    return render(
        request,
        "core/legal.html",
        {"title": LegalPage.Kind(kind).label, "page": page},
    )


def help_page(request):
    membership = getattr(request, "membership", None)
    return render(
        request,
        "core/help.html",
        {**SETTINGS, "topics": topics_for(membership.role if membership else None)},
    )


def about(request):
    return render(
        request,
        "core/about.html",
        {
            **SETTINGS,
            "features": FEATURES,
            "version": settings.APP_VERSION,
            "source_url": settings.SOURCE_URL,
            "legal_pages": LegalPage.Kind.choices,
        },
    )
