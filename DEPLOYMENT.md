# Déploiement SIRH ACEP sur Ubuntu Server

Guide complet pour déployer l'application sur un serveur interne ACEP (Ubuntu 22.04 LTS ou supérieur).

**Stack cible :** Nginx (reverse proxy) → Gunicorn (WSGI) → Django + PostgreSQL.

---

## Pré-requis

- Serveur Ubuntu 22.04 LTS ou supérieur
- Accès root ou sudo
- **Adresse IP fixe du serveur** sur le réseau interne ACEP : `192.168.0.209`
- **Port d'écoute** : `3636` (port de test ; sera basculé sur `3535` après validation de la direction)
- URL d'accès depuis n'importe quel poste du LAN ACEP : <http://192.168.0.209:3636>
- Connexion réseau interne ACEP (pas de VPN — voir contrainte fonctionnelle)

> 💡 Pas besoin de DNS interne — l'IP fixe du serveur suffit. Pour changer le port plus tard (de 3636 vers 3535), il faut modifier **trois choses** : `listen` dans `/etc/nginx/sites-available/sirh-acep`, autoriser le nouveau port dans `ufw`, et **reload Nginx**. Procédure détaillée dans la section *Changement de port* en bas du document.

---

## Option 1 — Installation automatique (recommandée)

Un script tout-en-un est fourni :

```bash
# 1. Déposer le code dans /opt/sirh_acep (git clone, rsync, ou copie manuelle)
sudo mkdir -p /opt/sirh_acep
sudo chown $USER /opt/sirh_acep
git clone <REPO_URL> /opt/sirh_acep
# OU : rsync -av sirh_acep/ user@serveur:/opt/sirh_acep/

# 2. Adapter les variables en haut du script (DB_PASSWORD notamment)
sudo nano /opt/sirh_acep/deploy/install_ubuntu.sh

# 3. Exécuter le script
sudo bash /opt/sirh_acep/deploy/install_ubuntu.sh

# 4. Créer un superuser
sudo -u sirh /opt/sirh_acep/.venv/bin/python /opt/sirh_acep/manage.py createsuperuser \
    --settings=config.settings.prod
```

Le script installe Python, PostgreSQL, Nginx, crée l'utilisateur système, la base, le virtualenv, applique les migrations, configure systemd et nginx, active le firewall.

---

## Option 2 — Installation manuelle (étape par étape)

### 1. Paquets système

```bash
sudo apt update && sudo apt upgrade -y
# Ubuntu 22.04 → python3.10, 24.04 → python3.12. Le script install_ubuntu.sh
# détecte automatiquement la version livrée par votre OS.
sudo apt install -y \
    python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    nginx \
    git curl ufw \
    build-essential libpq-dev
```

### 2. Utilisateur applicatif

```bash
sudo useradd --system --shell /bin/bash --home /opt/sirh_acep sirh
sudo mkdir -p /opt/sirh_acep /var/log/sirh_acep
sudo chown -R sirh:sirh /opt/sirh_acep /var/log/sirh_acep
```

### 3. Base de données PostgreSQL

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE sirh_acep;
CREATE USER sirh_user WITH ENCRYPTED PASSWORD 'MotDePasseSolide';
GRANT ALL PRIVILEGES ON DATABASE sirh_acep TO sirh_user;
ALTER USER sirh_user CREATEDB;
\q
EOF
```

### 4. Code et virtualenv

```bash
sudo -u sirh git clone <REPO_URL> /opt/sirh_acep
cd /opt/sirh_acep
# Utiliser la version Python livrée par l'OS (python3 = 3.12 sur 24.04, 3.10 sur 22.04)
sudo -u sirh python3 -m venv .venv
sudo -u sirh .venv/bin/pip install --upgrade pip
sudo -u sirh .venv/bin/pip install -r requirements.txt
```

### 5. Variables d'environnement

```bash
sudo -u sirh cp .env.example .env
sudo -u sirh nano .env
```

Compléter :

```
SECRET_KEY=...                                # généré aléatoirement
DEBUG=False
ALLOWED_HOSTS=192.168.0.209,127.0.0.1,localhost
DATABASE_URL=postgres://sirh_user:MotDePasseSolide@localhost:5432/sirh_acep
USE_X_FORWARDED_FOR=True
```

> Le port (3636) **ne se met PAS** dans `ALLOWED_HOSTS` — Django ne valide que l'hôte, pas le port.

Générer la `SECRET_KEY` :

```bash
sudo -u sirh .venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. Migrations + statiques + superuser

```bash
cd /opt/sirh_acep
sudo -u sirh .venv/bin/python manage.py migrate --settings=config.settings.prod
sudo -u sirh .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.prod
sudo -u sirh .venv/bin/python manage.py createsuperuser --settings=config.settings.prod
```

### 7. systemd (Gunicorn)

```bash
sudo cp /opt/sirh_acep/deploy/gunicorn.service /etc/systemd/system/sirh-acep.service
sudo cp /opt/sirh_acep/deploy/sirh-acep.socket /etc/systemd/system/sirh-acep.socket
sudo systemctl daemon-reload
sudo systemctl enable --now sirh-acep.socket
sudo systemctl enable --now sirh-acep.service
sudo systemctl status sirh-acep
```

### 8. Nginx

```bash
sudo cp /opt/sirh_acep/deploy/nginx.conf /etc/nginx/sites-available/sirh-acep
sudo ln -s /etc/nginx/sites-available/sirh-acep /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 9. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 3636/tcp     # port d'accès à l'application
sudo ufw enable
sudo ufw status verbose
```

> Pour basculer sur le port définitif `3535` plus tard, voir la section *Changement de port* en fin de document.

---

## HTTPS (optionnel)

⚠️ **Let's Encrypt ne fonctionne PAS avec une IP** — il requiert un nom de domaine public résolvable. Si vous accédez à l'application par `http://192.168.0.209:3636` sans DNS, deux options :

### Option A — Rester en HTTP (acceptable sur réseau interne)

Comme l'application n'est joignable que depuis le LAN ACEP (pas d'accès Internet, pas de VPN), HTTP est techniquement suffisant. Le risque sniffing existe mais reste maîtrisé sur un réseau switché interne.

### Option B — Certificat auto-signé (HTTPS interne)

Génère un certificat valide 10 ans pour votre IP :

```bash
sudo mkdir -p /etc/ssl/sirh
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/ssl/sirh/sirh.key \
    -out /etc/ssl/sirh/sirh.crt \
    -subj "/C=SN/ST=Dakar/L=Dakar/O=ACEP/CN=192.168.0.209" \
    -addext "subjectAltName=IP:192.168.0.209"
sudo chmod 600 /etc/ssl/sirh/sirh.key
```

Puis dans `/etc/nginx/sites-available/sirh-acep`, décommentez le bloc HTTPS et choisissez un port (par ex. `3637` pour HTTPS) :

```nginx
server {
    listen 3637 ssl http2;
    server_name _;

    ssl_certificate     /etc/ssl/sirh/sirh.crt;
    ssl_certificate_key /etc/ssl/sirh/sirh.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    # ... (recopier les blocs location / static / media du serveur HTTP)
}
```

Ouvrir le port et reload :

```bash
sudo ufw allow 3637/tcp
sudo nginx -t && sudo systemctl reload nginx
```

URL d'accès : `https://192.168.0.209:3637`. Les agents verront un avertissement "certificat non vérifié" à la première visite (normal pour un cert auto-signé) — ils peuvent l'accepter une fois.

### Option C — Certificat interne ACEP (si votre DSI fournit une PKI)

Si ACEP a une autorité de certification interne, demandez un certificat signé pour l'IP du serveur et placez `.crt`/`.key` dans `/etc/ssl/sirh/` puis configurez Nginx comme à l'option B. Aucun avertissement navigateur.

---

## Mappings IP → Bureaux

Une fois l'application en production, **la RH doit renseigner les plages IP** de chaque bureau via l'interface admin Django (page Bureaux, Sprint 1 à venir).

Exemple :

```
Bureau VDN      → 192.168.7.0/24
Bureau Yoff     → 192.168.9.0/24
Siège Dakar     → 192.168.1.0/24
```

À chaque pointage, l'IP source de la requête est résolue automatiquement en bureau, ce qui permet de détecter les incohérences (employé pointant depuis un autre bureau que son affectation).

---

## Sauvegardes

### Base PostgreSQL (quotidien)

```bash
# Script à placer dans /usr/local/bin/sirh_backup.sh
#!/bin/bash
DATE=$(date +%Y%m%d)
sudo -u postgres pg_dump sirh_acep | gzip > /var/backups/sirh_acep_${DATE}.sql.gz
find /var/backups -name 'sirh_acep_*.sql.gz' -mtime +30 -delete
```

Programmer dans cron :

```bash
sudo crontab -e
# Tous les jours à 2h du matin :
0 2 * * * /usr/local/bin/sirh_backup.sh
```

### Médias (photos employés)

```bash
sudo rsync -av /opt/sirh_acep/media/ /var/backups/sirh_media/
```

---

## Maintenance

### Mise à jour de l'application (GitHub → prod, sans perte de données)

**Principe** : Django garantit que les `migrations` sont **incrémentales et préservent les données** existantes (elles ajoutent/modifient des colonnes mais ne suppriment jamais les lignes sauf si la migration le demande explicitement). Un `git pull + migrate + restart` est donc sans risque pour les données déjà saisies (pointages, employés, anomalies, etc.).

**Script automatisé** (recommandé) — `deploy/update.sh` :

```bash
sudo bash /opt/sirh_acep/deploy/update.sh
```

Le script enchaîne :

1. **Snapshot PostgreSQL** horodaté dans `/var/backups/sirh_acep/` (pour rollback éventuel).
2. Sauvegarde du dossier `media/` (photos employés) si non vide.
3. `git fetch && git pull --ff-only` sur la branche `main`.
4. Si `requirements.txt` a changé → `pip install`.
5. `manage.py migrate` (incrémental — préserve toutes les données).
6. `manage.py collectstatic` (rafraîchit CSS/JS).
7. `systemctl restart sirh-acep` (coupure < 2 s, Nginx ne s'arrête pas).
8. Vérification que le service est bien actif ; sinon, message clair pour rollback.

Pour spécifier une autre branche : `sudo bash deploy/update.sh dev`.

**Manuel** (équivalent) :

```bash
cd /opt/sirh_acep
sudo -u postgres pg_dump sirh_acep | gzip > /var/backups/sirh_acep_$(date +%Y%m%d_%H%M%S).sql.gz
sudo -u sirh git pull --ff-only origin main
sudo -u sirh .venv/bin/pip install -r requirements.txt
sudo -u sirh .venv/bin/python manage.py migrate --settings=config.settings.prod
sudo -u sirh .venv/bin/python manage.py collectstatic --noinput --settings=config.settings.prod
sudo systemctl restart sirh-acep
```

### Workflow git recommandé

Côté **développement (votre poste Windows)** :

```bash
cd C:\Users\HP\Documents\sirh_acep
git add .
git commit -m "Description du changement"
git push origin main
```

Côté **serveur Ubuntu** :

```bash
sudo bash /opt/sirh_acep/deploy/update.sh
```

C'est tout — les données de prod (pointages, employés, anomalies) sont intactes.

### Cron / déploiement automatique (optionnel)

Pour pull automatiquement chaque nuit (si vous préférez tester en prod le matin) :

```bash
sudo crontab -e
# Chaque jour à 4h, pull et redémarre :
0 4 * * * /opt/sirh_acep/deploy/update.sh >> /var/log/sirh_acep/update.log 2>&1
```

⚠️ À éviter en production critique — préférez un déclenchement manuel après revue.

### Webhook GitHub (déploiement push-to-deploy)

Si le serveur est joignable depuis GitHub, un webhook peut déclencher `update.sh` à chaque push. Cela nécessite un endpoint léger (Flask/FastAPI ou un script via `webhook` package) — demandez si vous voulez la config.

### Rollback rapide

Si un déploiement casse quelque chose :

```bash
cd /opt/sirh_acep
# 1. Revenir au commit précédent
sudo -u sirh git reset --hard <ANCIEN_COMMIT>

# 2. Restaurer la base si nécessaire
gunzip -c /var/backups/sirh_acep/sirh_acep_AAAAMMJJ_HHMMSS.sql.gz \
  | sudo -u postgres psql sirh_acep

# 3. Redémarrer
sudo systemctl restart sirh-acep
```

### Données à ne JAMAIS pull (sécurité)

Le fichier `.env` (contient `SECRET_KEY`, password BDD) **n'est pas versionné**. Il reste sur le serveur dans `/opt/sirh_acep/.env` et n'est jamais écrasé par `git pull`. De même, le dossier `media/` et `staticfiles/` sont exclus via `.gitignore`.

### Logs

```bash
# Logs Django (Gunicorn)
sudo journalctl -u sirh-acep -f
sudo tail -f /var/log/sirh_acep/error.log

# Logs Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Diagnostic

```bash
# État des services
sudo systemctl status sirh-acep
sudo systemctl status nginx
sudo systemctl status postgresql

# Test de la configuration Django
sudo -u sirh /opt/sirh_acep/.venv/bin/python /opt/sirh_acep/manage.py check --deploy --settings=config.settings.prod
```

---

## Changement de port (ex : 3636 → 3535)

Une fois la validation de la direction obtenue, pour passer du port de test (`3636`) au port définitif (`3535`) :

```bash
# 1. Modifier la config Nginx
sudo sed -i 's/listen 3636/listen 3535/' /etc/nginx/sites-available/sirh-acep

# 2. Ouvrir le nouveau port et fermer l'ancien
sudo ufw allow 3535/tcp
sudo ufw delete allow 3636/tcp

# 3. Tester la config et reload
sudo nginx -t
sudo systemctl reload nginx

# 4. Vérifier
sudo ufw status verbose
curl -I http://192.168.0.209:3535
```

L'IP du serveur reste la même (`192.168.0.209`), aucune migration BDD n'est nécessaire, les pointages et données existantes sont intacts. Communiquez simplement aux agents la nouvelle URL : `http://192.168.0.209:3535`.

> Si vous utilisez HTTPS auto-signé, le certificat reste valable (il est lié à l'IP, pas au port).

---

## Désinstallation

```bash
sudo systemctl stop sirh-acep nginx
sudo systemctl disable sirh-acep
sudo rm /etc/systemd/system/sirh-acep.{service,socket}
sudo rm /etc/nginx/sites-enabled/sirh-acep /etc/nginx/sites-available/sirh-acep
sudo systemctl daemon-reload && sudo systemctl reload nginx
sudo -u postgres dropdb sirh_acep
sudo -u postgres dropuser sirh_user
sudo userdel -r sirh
sudo rm -rf /opt/sirh_acep /var/log/sirh_acep
```
