#!/bin/bash
# ============================================================================
# update.sh — Mise à jour SIRH ACEP depuis GitHub sans perte de données.
#
# Étapes :
#   1. Sauvegarde de la base PostgreSQL (snapshot horodaté dans /var/backups)
#   2. git pull (branche main par défaut)
#   3. pip install si requirements.txt a changé
#   4. manage.py migrate (les migrations Django sont incrémentales — préservent
#      les données existantes)
#   5. manage.py collectstatic (rafraîchit /opt/sirh_acep/staticfiles)
#   6. Redémarrage de Gunicorn (Nginx continue de tourner — coupure < 2 s)
#
# Sécurité : si une étape échoue, le script s'arrête (set -e) et un retour
# arrière est possible via la sauvegarde produite à l'étape 1.
#
# Usage :
#   sudo bash /opt/sirh_acep/deploy/update.sh
#
# Personnalisable : variables BRANCH et APP_DIR ci-dessous.
# ============================================================================
set -euo pipefail

APP_DIR="/opt/sirh_acep"
APP_USER="sirh"
SERVICE="sirh-acep"
DB_NAME="sirh_acep"
BRANCH="${1:-main}"
BACKUP_DIR="/var/backups/sirh_acep"
TS=$(date +%Y%m%d_%H%M%S)

log()  { echo -e "\033[1;32m[$(date +%H:%M:%S)] $*\033[0m"; }
warn() { echo -e "\033[1;33m[$(date +%H:%M:%S)] $*\033[0m"; }
err()  { echo -e "\033[1;31m[$(date +%H:%M:%S)] $*\033[0m" >&2; }

# --- Vérifications ---------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  err "Ce script doit être exécuté avec sudo."
  exit 1
fi
if [[ ! -d "$APP_DIR/.git" ]]; then
  err "$APP_DIR n'est pas un repo Git. Clonez d'abord le projet."
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# --- 1. Sauvegarde BDD ----------------------------------------------------
log "Sauvegarde PostgreSQL → $BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"
log "Sauvegarde OK ($(du -h "$BACKUP_DIR/${DB_NAME}_${TS}.sql.gz" | cut -f1))"

# Conservation : on garde les 30 dernières sauvegardes
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +30 -delete || true

# --- 2. Sauvegarde des médias (photos employés, etc.) ---------------------
if [[ -d "$APP_DIR/media" ]] && [[ -n "$(ls -A "$APP_DIR/media" 2>/dev/null)" ]]; then
  log "Sauvegarde des médias → $BACKUP_DIR/media_${TS}.tar.gz"
  tar -czf "$BACKUP_DIR/media_${TS}.tar.gz" -C "$APP_DIR" media
fi

# --- 3. git pull ----------------------------------------------------------
log "Pull de la branche $BRANCH"
cd "$APP_DIR"

# Capture le hash avant pull pour pouvoir rollback
OLD_COMMIT=$(sudo -u "$APP_USER" git rev-parse HEAD)
log "Commit actuel : $OLD_COMMIT"

# Si des fichiers locaux ont été modifiés en prod par erreur, on prévient
if ! sudo -u "$APP_USER" git diff-index --quiet HEAD --; then
  warn "Modifications locales détectées — elles seront stashées."
  sudo -u "$APP_USER" git stash push -m "auto-stash $TS" || true
fi

sudo -u "$APP_USER" git fetch origin
sudo -u "$APP_USER" git checkout "$BRANCH"
sudo -u "$APP_USER" git pull --ff-only origin "$BRANCH"

NEW_COMMIT=$(sudo -u "$APP_USER" git rev-parse HEAD)
if [[ "$OLD_COMMIT" == "$NEW_COMMIT" ]]; then
  log "Aucun nouveau commit. Rien à faire."
  exit 0
fi
log "Nouveau commit : $NEW_COMMIT"

# --- 4. Dépendances Python (si requirements.txt a changé) -----------------
if sudo -u "$APP_USER" git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -q "requirements.txt"; then
  log "requirements.txt modifié — pip install"
  sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
else
  log "Dépendances inchangées."
fi

# --- 5. Migrations Django (préservent les données) ------------------------
log "Application des migrations"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate \
  --noinput --settings=config.settings.prod

# --- 6. Fichiers statiques ------------------------------------------------
log "collectstatic"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic \
  --noinput --settings=config.settings.prod

# --- 7. Redémarrage Gunicorn ---------------------------------------------
log "Redémarrage de $SERVICE"
systemctl restart "$SERVICE"
sleep 2
if systemctl is-active --quiet "$SERVICE"; then
  log "✓ Déploiement réussi — $SERVICE actif."
  log "  Ancien commit : $OLD_COMMIT"
  log "  Nouveau commit : $NEW_COMMIT"
  log "  Sauvegarde     : $BACKUP_DIR/${DB_NAME}_${TS}.sql.gz"
else
  err "$SERVICE n'a pas démarré ! Voir : journalctl -u $SERVICE -n 50"
  err "Pour rollback :"
  err "  cd $APP_DIR && sudo -u $APP_USER git reset --hard $OLD_COMMIT"
  err "  gunzip -c $BACKUP_DIR/${DB_NAME}_${TS}.sql.gz | sudo -u postgres psql $DB_NAME"
  err "  sudo systemctl restart $SERVICE"
  exit 1
fi
