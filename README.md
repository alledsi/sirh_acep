# SIRH ACEP — Pointage

Application de pointage du personnel ACEP, dérivée du module Pointage existant et conçue comme la fondation d'un SIRH complet (Système d'Information Ressources Humaines).

**Statut : Sprint 0 — Squelette du projet (authentification + structure multi-apps)**

---

## Fonctionnalités du Sprint 0

- Architecture Django multi-apps prête pour les sprints suivants
- Custom User avec **matricule** comme identifiant de connexion
- Rôles cumulables : Agent, Directeur, RH, Directeur Général
- Page de login fidèle à la maquette (logo ACEP, vert #02564A, fond)
- Page d'accueil après connexion + changement de mot de passe
- Admin Django configuré pour la gestion des utilisateurs
- Settings séparés dev (SQLite) / prod (PostgreSQL + sécurité durcie)
- Fichiers de déploiement Ubuntu (Gunicorn + Nginx + systemd)

## Prochains sprints (modèles à implémenter)

1. **Sprint 1 — Organisation** : Mutuelle, Agence, Bureau, Direction, IPBureauMapping
2. **Sprint 2 — Employés** : Employee, Contract, EmployeeDocument
3. **Sprint 3 — Pointage** : TimeEntry, Anomaly + résolution IP → Bureau
4. **Sprint 4 — Planning** : Planning unique, gestion du samedi semaine par semaine
5. **Sprint 5 — Reporting** : Dashboards Directeur, statistiques RH/DG

---

## Installation locale (Windows / macOS / Linux)

### Prérequis

- Python 3.11 ou supérieur
- Git (optionnel)

### Étapes

```bash
# 1. Aller dans le dossier du projet
cd sirh_acep

# 2. Créer un environnement virtuel
python -m venv .venv

# 3. Activer l'environnement
#    Linux/macOS :
source .venv/bin/activate
#    Windows :
.venv\Scripts\activate

# 4. Installer les dépendances
pip install -r requirements.txt

# 5. Copier le fichier d'environnement et le compléter
cp .env.example .env       # Linux/macOS
copy .env.example .env     # Windows
# Éditer .env : générer une SECRET_KEY unique

# 6. Créer la base SQLite et appliquer les migrations
python manage.py migrate

# 7. Créer un superutilisateur (matricule + email + mot de passe)
python manage.py createsuperuser

# 8. Lancer le serveur de développement
python manage.py runserver
```

Ouvrir [http://localhost:8000](http://localhost:8000) → redirection automatique vers la page de connexion.
L'admin Django est accessible sur [http://localhost:8000/admin/](http://localhost:8000/admin/).

### Génération d'une SECRET_KEY

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Structure du projet

```
sirh_acep/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── DEPLOYMENT.md                # Guide de déploiement Ubuntu détaillé
│
├── config/                      # Projet Django
│   ├── settings/
│   │   ├── base.py              # Settings communs
│   │   ├── dev.py               # DEBUG=True, SQLite
│   │   └── prod.py              # DEBUG=False, PostgreSQL, sécurité
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── core/                    # User custom, BaseModel, auth, services
│   ├── organization/            # Sprint 1 — Mutuelles, Agences, Bureaux, Directions
│   ├── employees/               # Sprint 2 — Fiches employés, contrats
│   ├── attendance/              # Sprint 3 — Pointage, anomalies
│   ├── planning/                # Sprint 4 — Horaires, samedi par semaine
│   └── reporting/               # Sprint 5 — Dashboards, statistiques
│
├── templates/
│   ├── base.html                # Layout principal (sidebar + topbar)
│   └── core/
│       ├── login.html           # Page de connexion (logo ACEP)
│       ├── home.html            # Page d'accueil après login
│       ├── password_change.html
│       └── password_change_done.html
│
├── static/
│   ├── css/app.css              # Styles ACEP (vert #02564A)
│   └── img/
│       ├── login.png            # Logo ACEP Sunu Moomel
│       └── fond_acep.png        # Motif de fond (page login uniquement)
│
└── deploy/                      # Fichiers de déploiement Ubuntu
    ├── gunicorn.service         # Unit systemd
    ├── sirh-acep.socket
    ├── nginx.conf
    └── install_ubuntu.sh        # Script d'install automatique
```

---

## Déploiement sur Ubuntu

Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour la procédure complète (PostgreSQL + Gunicorn + Nginx + systemd + HTTPS).

Un script d'installation automatique est fourni : `deploy/install_ubuntu.sh`.

---

## Notes importantes

### Authentification

- Le **matricule** est l'identifiant de connexion (pas l'email, pas un username).
- Le custom User vit dans `apps.core.models.User`.
- Les rôles sont stockés dans `user.roles` (JSON list) — exemple : `['AGENT', 'RH']`.
- Méthodes pratiques : `user.is_agent`, `user.is_directeur`, `user.is_rh`, `user.is_dg`, `user.has_global_access`.

### Résolution IP → Bureau

Le module Attendance (Sprint 3) utilisera `apps.core.services.get_client_ip(request)` pour récupérer l'IP réelle du client, en tenant compte du header `X-Forwarded-For` quand Django est derrière Nginx.

L'application est conçue pour fonctionner **uniquement sur le réseau interne ACEP** (pas de VPN supporté). Une IP non rattachée à un bureau déclenchera une anomalie `UNKNOWN_IP`.

### Sécurité

- Mots de passe : minimum 10 caractères, hash PBKDF2 (default Django, peut être passé à Argon2 en prod).
- En prod : `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS activés.
- Toutes les variables sensibles passent par `.env` (ignoré par Git).

---

## Commandes utiles

```bash
# Lancer les tests (à venir)
python manage.py test

# Créer une migration
python manage.py makemigrations <app>

# Appliquer les migrations
python manage.py migrate

# Shell Django
python manage.py shell

# Collecter les statiques (pour la prod)
python manage.py collectstatic --settings=config.settings.prod

# Vérifier la configuration pour la prod
python manage.py check --deploy --settings=config.settings.prod
```
