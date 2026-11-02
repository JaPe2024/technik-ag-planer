from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Production


@shared_task
def purge_deleted_productions():
    """Entfernt Produktionen endgültig, die seit mehr als 7 Tagen gelöscht sind."""
    cutoff = timezone.now() - timedelta(days=settings.PRODUCTION_TRASH_DAYS)
    count = 0
    from apps.google_sync import drive

    for production in Production.all_objects.filter(deleted_at__lt=cutoff):
        drive.delete_all(production.attachments.all())  # Abschnitt 2: auch im Drive löschen
        drive.trash_production_folder(production)
        production.delete()
        count += 1
    return count
