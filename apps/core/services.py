"""Services partagés.

`get_client_ip(request)` : extrait l'IP réelle du client en tenant compte d'un
éventuel reverse proxy nginx en amont (header X-Forwarded-For).

Cette fonction sera utilisée par le module Attendance (Sprint 3) pour résoudre
le bureau de connexion à partir de l'adresse IP source.
"""
from django.conf import settings


def get_client_ip(request) -> str | None:
    """Retourne l'IP source de la requête (str) ou None si introuvable."""
    if getattr(settings, 'USE_X_FORWARDED_FOR', True):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
