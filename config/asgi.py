"""ASGI config pour SIRH ACEP (utilisé si on ajoute Django Channels plus tard)."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = get_asgi_application()
