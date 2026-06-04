"""Settings de production (Ubuntu + Gunicorn + Nginx).

Mode HTTPS : pilotable via la variable d'env `USE_HTTPS` du .env.
  - `USE_HTTPS=False` (défaut) → HTTP autorisé, pas de redirection forcée.
    À utiliser pour un déploiement LAN interne par IP sans certificat.
  - `USE_HTTPS=True` → cookies sécurisés, redirection HTTPS, HSTS 1 an.
    À activer après avoir mis en place un certificat (auto-signé ou interne).
"""
from .base import *  # noqa: F401, F403
from .base import env

DEBUG = False

# ---------- Sécurité HTTP ----------
USE_HTTPS = env.bool('USE_HTTPS', default=False)

# Cookies sécurisés et redirection HTTPS uniquement si on est en HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if USE_HTTPS else None

# HSTS : seulement quand HTTPS est en place et stable
SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
SECURE_HSTS_PRELOAD = USE_HTTPS

# Anti-clickjacking, MIME sniffing, etc.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# ---------- Logging ----------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/sirh_acep/django.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
