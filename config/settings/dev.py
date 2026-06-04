"""Settings de développement (DEBUG=True, SQLite par défaut)."""
from .base import *  # noqa: F401, F403

# DEBUG est lu depuis .env ; on s'assure qu'il reste True en dev
DEBUG = True

# Autoriser tous les hôtes en dev
ALLOWED_HOSTS = ['*']

INTERNAL_IPS = ['127.0.0.1']

# Désactiver les cookies sécurisés en dev (HTTP)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Affichage des erreurs détaillées
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Pour tester la résolution IP en dev, on peut forcer une IP de test
# DEV_FORCE_IP = '192.168.7.42'   # à utiliser dans un middleware de test si besoin
