#!/usr/bin/env bash
# Script d'installation SIRH ACEP sur Ubuntu 22.04+
# Exécuter en tant que root : sudo bash install_ubuntu.sh
# Adapter les variables ci-dessous avant exécution.

set -euo pipefail

# ============ Configuration (à adapter) ============
APP_DIR="/opt/sirh_acep"
APP_USER="sirh"
DB_NAME="sirh_acep"
DB_USER="sirh_user"
DB_PASSWORD="CHANGE_ME_AVANT_INSTALL"
SERVER_IP="192.168.0.209"        # IP fixe du serveur sur le LAN ACEP
APP_PORT="3636"                  # Port d'écoute Nginx (basculera vers 3535 après validation)

# ============ 1. Mise à jour & paquets système ============
echo ">>> Mise à jour du système"
apt update && apt upgrade -y

echo ">>> Détection de la version Python disponible"
# Ubuntu 22.04 → python3.10, 24.04 → python3.12. On utilise la version livrée par l'OS.
if command -v python3.12 >/dev/null; then
    PYTHON_BIN="python3.12"
    PYTHON_PKGS="python3.12 python3.12-venv"
elif command -v python3.11 >/dev/null; then
    PYTHON_BIN="python3.11"
    PYTHON_PKGS="python3.11 python3.11-venv"
elif command -v python3.10 >/dev/null; then
    PYTHON_BIN="python3.10"
    PYTHON_PKGS="python3.10 python3.10-venv"
else
    PYTHON_BIN="python3"
    PYTHON_PKGS="python3 python3-venv"
fi
echo "    Python détecté : ${PYTHON_BIN}"

echo ">>> Installation des paquets nécessaires"
apt install -y \
    ${PYTHON_PKGS} python3-pip \
    postgresql postgresql-contrib \
    nginx \
    git curl ufw \
    build-essential libpq-dev

# ============ 2. Utilisateur système ============
echo ">>> Création de l'utilisateur applicatif : ${APP_USER}"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --shell /bin/bash --home "${APP_DIR}" "${APP_USER}"
fi

# ============ 3. PostgreSQL ============
echo ">>> Configuration de PostgreSQL"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres createdb "${DB_NAME}"
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASSWORD}';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -c "ALTER USER ${DB_USER} CREATEDB;"  # nécessaire pour les tests

# Sur PostgreSQL 15+, les utilisateurs n'ont plus le droit de créer des tables
# dans le schéma `public` par défaut. On rend ${DB_USER} propriétaire du schéma
# et de la base pour que Django puisse appliquer ses migrations.
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "ALTER SCHEMA public OWNER TO ${DB_USER};"
sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};"

# ============ 4. Code applicatif ============
echo ">>> Préparation du dossier ${APP_DIR}"
mkdir -p "${APP_DIR}" /var/log/sirh_acep
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" /var/log/sirh_acep

echo ">>> Le code doit être déployé manuellement dans ${APP_DIR}"
echo "    (git clone ou rsync depuis votre poste de dev)"
echo "    Exemple : sudo -u ${APP_USER} git clone <REPO_URL> ${APP_DIR}"

# ============ 5. Virtualenv et dépendances ============
if [ -f "${APP_DIR}/manage.py" ]; then
    echo ">>> Création du virtualenv (${PYTHON_BIN}) et installation"
    sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
    sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
    sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

    # .env
    if [ ! -f "${APP_DIR}/.env" ]; then
        echo ">>> Création du .env depuis .env.example"
        sudo -u "${APP_USER}" cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
        SECRET_KEY=$(sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
        sudo -u "${APP_USER}" sed -i "s|SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "${APP_DIR}/.env"
        sudo -u "${APP_USER}" sed -i "s|DEBUG=.*|DEBUG=False|" "${APP_DIR}/.env"
        sudo -u "${APP_USER}" sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgres://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}|" "${APP_DIR}/.env"
        sudo -u "${APP_USER}" sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${SERVER_IP},localhost,127.0.0.1|" "${APP_DIR}/.env"
        echo "    .env créé avec une SECRET_KEY aléatoire"
    fi

    # Migrations + statics + superuser
    cd "${APP_DIR}"
    sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" manage.py migrate --settings=config.settings.prod
    sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" manage.py collectstatic --noinput --settings=config.settings.prod
    echo ">>> Pensez à créer un superuser : sudo -u ${APP_USER} ${APP_DIR}/.venv/bin/python manage.py createsuperuser --settings=config.settings.prod"
fi

# ============ 6. systemd ============
echo ">>> Installation des units systemd"
if [ -f "${APP_DIR}/deploy/gunicorn.service" ]; then
    cp "${APP_DIR}/deploy/gunicorn.service" /etc/systemd/system/sirh-acep.service
    cp "${APP_DIR}/deploy/sirh-acep.socket" /etc/systemd/system/sirh-acep.socket
    systemctl daemon-reload
    systemctl enable --now sirh-acep.socket
    systemctl enable sirh-acep.service
    systemctl start sirh-acep.service
fi

# ============ 7. Nginx ============
echo ">>> Configuration Nginx (port ${APP_PORT})"
if [ -f "${APP_DIR}/deploy/nginx.conf" ]; then
    cp "${APP_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/sirh-acep
    # Force le port d'écoute selon la variable APP_PORT (au cas où elle a été changée)
    sed -i "s|^    listen [0-9]* default_server;|    listen ${APP_PORT} default_server;|" /etc/nginx/sites-available/sirh-acep
    ln -sf /etc/nginx/sites-available/sirh-acep /etc/nginx/sites-enabled/sirh-acep
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx
fi

# ============ 8. Firewall ============
echo ">>> Configuration du firewall (UFW) — port ${APP_PORT}/tcp"
ufw allow OpenSSH
ufw allow "${APP_PORT}/tcp"
ufw --force enable

echo ""
echo "================================================"
echo "  Installation SIRH ACEP terminée"
echo "================================================"
echo "  Vérifier le service  : systemctl status sirh-acep"
echo "  Voir les logs        : journalctl -u sirh-acep -f"
echo "  URL                  : http://${SERVER_IP}:${APP_PORT}"
echo ""
echo "  N'oubliez pas :"
echo "  - Configurer HTTPS (certificat SSL)"
echo "  - Créer un superuser (commande ci-dessus)"
echo "  - Sauvegarder régulièrement la base : pg_dump ${DB_NAME}"
echo "================================================"
