"""Commande à exécuter quotidiennement (cron / Task Scheduler / Celery beat).

Détecte les pointages de la veille pour lesquels aucun départ n'a été pointé
et crée l'anomalie NO_DEPARTURE correspondante.

Usage :
    python manage.py detect_missing_departures
"""
from django.core.management.base import BaseCommand

from apps.attendance.services import detect_missing_departures_for_yesterday


class Command(BaseCommand):
    help = "Détecte les pointages de la veille sans départ et crée les anomalies."

    def handle(self, *args, **options):
        count = detect_missing_departures_for_yesterday()
        self.stdout.write(self.style.SUCCESS(
            f"{count} anomalie(s) NO_DEPARTURE créée(s) pour la veille."
        ))
