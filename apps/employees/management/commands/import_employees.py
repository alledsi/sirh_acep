"""Commande d'import des employés depuis un fichier Excel.

Usage :
    python manage.py import_employees                            # utilise le fichier par défaut
    python manage.py import_employees chemin/vers/fichier.xlsx   # fichier custom
    python manage.py import_employees --dry-run                  # simulation sans écriture
    python manage.py import_employees --check-bureaux            # lister/comparer les bureaux (rien n'est importé)

Fichier par défaut : apps/employees/data/employees_initial.xlsx

Comportement :
  - Matricule paddé à 4 chiffres (ex : 141 → 0141, 25 → 0025).
  - Direction : comparée aux directions existantes en base (insensible
    casse / accents / espaces multiples). Si pas trouvée, créée.
  - Bureau : comparé aux bureaux existants. SI PAS TROUVÉ → l'employé est
    rejeté (les bureaux doivent déjà exister en base, jamais créés ici).
  - User : matricule unique, rôle AGENT, mot de passe Acep@2026,
    must_change_password=True. Si le matricule existe déjà, ligne ignorée.
  - Email : optionnel (laissé vide).
"""
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import User
from apps.employees.models import Employee
from apps.organization.models import Agence, Bureau, Direction, Mutuelle


DEFAULT_PASSWORD = 'Acep@2026'
DEFAULT_FILE = Path(__file__).resolve().parent.parent.parent / 'data' / 'employees_initial.xlsx'


def _normalize(text: str) -> str:
    """Normalise un libellé pour comparaison : minuscule, sans accents,
    espaces multiples → un seul, trim."""
    if not text:
        return ''
    s = str(text).strip().lower()
    # Supprime les accents
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    # Espaces multiples
    s = re.sub(r'\s+', ' ', s)
    return s


def _pad_matricule(value) -> str:
    """Convertit en chaîne et padde à 4 chiffres avec des zéros à gauche."""
    if value is None:
        return ''
    s = str(value).strip()
    # Conserve les éventuels zéros déjà présents
    if s.isdigit():
        return s.zfill(4)
    return s


def _parse_date(value):
    """Retourne un date à partir d'un datetime/date/str."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _make_code(label: str, prefix: str, max_len: int = 20) -> str:
    """Génère un code court depuis un libellé.

    Ex : 'DIRECTION CONTRÔLE DE GESTION' + prefix='DIR-' → 'DIR-CG' (initiales)
    Si trop court, tronque le libellé brut.
    """
    norm = _normalize(label).upper()
    norm = re.sub(r'[^A-Z0-9 ]', '', norm)
    # Mots à ignorer pour les initiales
    stop = {'DE', 'DES', 'DU', 'LA', 'LE', 'LES', 'ET', 'A', "L'", 'EN'}
    words = [w for w in norm.split() if w and w not in stop]
    initials = ''.join(w[0] for w in words)
    code = (prefix + initials)[:max_len]
    return code or (prefix + 'XXX')


class Command(BaseCommand):
    help = "Importe les employés depuis un fichier Excel (matricule, prenom, nom, poste, direction, bureau, date_naissance, date_embauche)."

    def add_arguments(self, parser):
        parser.add_argument(
            'file', nargs='?', default=str(DEFAULT_FILE),
            help='Chemin du fichier Excel (par défaut : apps/employees/data/employees_initial.xlsx)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simulation : ne crée rien en base, montre seulement ce qui serait fait.',
        )
        parser.add_argument(
            '--check-bureaux', action='store_true',
            help='Liste les bureaux du fichier et indique ceux qui ne matchent pas la base. N\'importe rien.',
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("openpyxl n'est pas installé. Lancer : pip install -r requirements.txt")

        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        dry = options['dry_run']
        check_only = options['check_bureaux']
        self.stdout.write(self.style.NOTICE(f'Lecture de {path}'))
        if check_only:
            self.stdout.write(self.style.WARNING('Mode --check-bureaux : analyse des bureaux uniquement, pas d\'import.'))
        elif dry:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN : aucune écriture en base.'))

        wb = openpyxl.load_workbook(str(path), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise CommandError('Fichier vide.')

        # En-tête tolérante
        headers = [(_normalize(h) if h else '') for h in rows[0]]
        aliases = {
            'matricule': ['matricule', 'mat', 'id'],
            'prenom': ['prenom', 'first_name', 'firstname'],
            'nom': ['nom', 'last_name', 'lastname', 'name'],
            'poste': ['poste', 'fonction', 'position', 'job', 'job_title'],
            'direction': ['direction', 'service', 'dir'],
            'bureau': ['bureau', 'site', 'bureau_affecte', 'bureau_affecté'],
            'date_naissance': ['date_naissance', 'naissance', 'birth_date', 'date naissance', 'datenaissance'],
            'date_embauche': ['date_embauche', 'embauche', 'hire_date', 'date embauche', 'dateembauche'],
        }
        idx = {}
        for key, opts in aliases.items():
            for o in opts:
                if o in headers:
                    idx[key] = headers.index(o)
                    break

        missing = [k for k in ('matricule', 'prenom', 'nom') if k not in idx]
        if missing:
            raise CommandError(f"Colonnes obligatoires manquantes : {', '.join(missing)}")

        # Précharge les directions et bureaux existants pour comparaison rapide
        existing_directions = {_normalize(d.name): d for d in Direction.objects.all()}
        existing_bureaux = {_normalize(b.name): b for b in Bureau.objects.all()}
        # Index par code aussi (au cas où le code matche)
        existing_bureaux_by_code = {_normalize(b.code): b for b in Bureau.objects.all()}

        # ===== Mode --check-bureaux : compare le fichier à la base, propose les ressemblances =====
        if check_only:
            unique_bureaux_in_file = sorted({
                str(row[idx['bureau']]).strip()
                for row in rows[1:]
                if row and 'bureau' in idx and row[idx['bureau']]
            })

            # Référence : la liste de la base (avec sa clé normalisée + l'objet)
            db_bureaux = list(Bureau.objects.all().order_by('name'))
            db_norms = [(_normalize(b.name), b) for b in db_bureaux]

            def _best_matches(label, top=3, threshold=0.55):
                """Retourne les 'top' bureaux de la base les + ressemblants à 'label'.

                Compare la chaîne normalisée. Score >= threshold seulement.
                """
                key = _normalize(label)
                scored = []
                for db_key, db_bureau in db_norms:
                    score = SequenceMatcher(None, key, db_key).ratio()
                    if score >= threshold:
                        scored.append((score, db_bureau))
                scored.sort(key=lambda x: x[0], reverse=True)
                return scored[:top]

            exact, fuzzy, none_found = [], [], []
            for b_label in unique_bureaux_in_file:
                key = _normalize(b_label)
                if key in existing_bureaux:
                    exact.append((b_label, existing_bureaux[key]))
                elif key in existing_bureaux_by_code:
                    exact.append((b_label, existing_bureaux_by_code[key]))
                else:
                    suggestions = _best_matches(b_label)
                    if suggestions:
                        fuzzy.append((b_label, suggestions))
                    else:
                        none_found.append(b_label)

            # Synthèse
            total = len(unique_bureaux_in_file)
            self.stdout.write(self.style.SUCCESS(
                f'\n=== Comparaison fichier ({total} bureaux uniques) vs base ({len(db_bureaux)} bureaux) ==='
            ))
            self.stdout.write(f'✓ Match exact                    : {len(exact)}')
            self.stdout.write(f'≈ Ressemblances trouvées         : {len(fuzzy)}')
            self.stdout.write(f'✗ Aucune correspondance          : {len(none_found)}')

            if fuzzy:
                self.stdout.write(self.style.WARNING(
                    f'\n≈ RESSEMBLANCES PROPOSÉES ({len(fuzzy)}) — vérifier puis corriger fichier OU base :'
                ))
                for label, suggestions in fuzzy:
                    self.stdout.write(f'\n  Fichier : « {label} »')
                    for score, b in suggestions:
                        pct = int(round(score * 100))
                        marker = '★' if score >= 0.9 else (' ' if score < 0.75 else '·')
                        self.stdout.write(f'    {marker} {pct}%  →  {b.code:14}  {b.name}')

            if none_found:
                self.stdout.write(self.style.ERROR(
                    f'\n✗ BUREAUX SANS AUCUNE RESSEMBLANCE en base ({len(none_found)}) :'
                ))
                for label in none_found:
                    self.stdout.write(f'  • {label}')

            if not fuzzy and not none_found:
                self.stdout.write(self.style.SUCCESS(
                    '\n🎉 Tous les bureaux du fichier ont une correspondance exacte en base.'
                    '\n   Vous pouvez lancer l\'import sans souci.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    '\nProchaine étape :'
                    '\n  1. Pour chaque "≈" : si le match proposé (★ = 90 %+) est bien le bon bureau,'
                    '\n     corriger le libellé dans le fichier Excel pour qu\'il colle exactement à la base.'
                    '\n  2. Pour chaque "✗" : créer le bureau manquant en base (UI Organisation > Bureaux).'
                    '\n  3. Relancer  : python manage.py import_employees --dry-run'
                    '\n     puis     : python manage.py import_employees'
                ))
            return

        created_users = 0
        skipped_existing = 0
        created_directions = 0
        errors = []
        unmatched_bureaux = set()

        for row_num, row in enumerate(rows[1:], start=2):
            if not row or row[idx['matricule']] is None:
                continue

            matricule = _pad_matricule(row[idx['matricule']])
            if not matricule:
                continue

            if User.objects.filter(matricule=matricule).exists():
                skipped_existing += 1
                continue

            prenom = str(row[idx['prenom']] or '').strip()
            nom = str(row[idx['nom']] or '').strip()
            poste = (str(row[idx['poste']]).strip() if 'poste' in idx and row[idx['poste']] else '') or 'À renseigner'

            # Direction : match avec l'existant ou création
            direction = None
            if 'direction' in idx and row[idx['direction']]:
                d_label = str(row[idx['direction']]).strip()
                d_key = _normalize(d_label)
                if d_key in existing_directions:
                    direction = existing_directions[d_key]
                else:
                    if dry:
                        self.stdout.write(self.style.WARNING(f'  [DRY] Créerait Direction : {d_label}'))
                    else:
                        d_code = _make_code(d_label, 'DIR-')
                        # Si collision sur le code, ajoute un suffixe numérique
                        base_code = d_code
                        i = 2
                        while Direction.objects.filter(code=d_code).exists():
                            d_code = f'{base_code}{i}'
                            i += 1
                        direction = Direction.objects.create(code=d_code, name=d_label)
                        existing_directions[d_key] = direction
                        created_directions += 1

            if not direction:
                errors.append(f'Ligne {row_num} ({matricule}) : direction manquante.')
                continue

            # Bureau : recherche stricte en base (jamais créé ici)
            bureau = None
            if 'bureau' in idx and row[idx['bureau']]:
                b_label = str(row[idx['bureau']]).strip()
                b_key = _normalize(b_label)
                if b_key in existing_bureaux:
                    bureau = existing_bureaux[b_key]
                elif b_key in existing_bureaux_by_code:
                    bureau = existing_bureaux_by_code[b_key]
                else:
                    unmatched_bureaux.add(b_label)
                    errors.append(f'Ligne {row_num} ({matricule}) : bureau "{b_label}" non trouvé en base.')
                    continue
            else:
                errors.append(f'Ligne {row_num} ({matricule}) : bureau vide.')
                continue

            birth_date = _parse_date(row[idx['date_naissance']]) if 'date_naissance' in idx else None
            hire_date = _parse_date(row[idx['date_embauche']]) if 'date_embauche' in idx else None
            if not hire_date:
                hire_date = date.today()

            if dry:
                created_users += 1
                continue

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        matricule=matricule,
                        email=None,  # email optionnel
                        password=DEFAULT_PASSWORD,
                        first_name=prenom,
                        last_name=nom,
                    )
                    user.roles = ['AGENT']
                    user.must_change_password = True
                    user.save()

                    Employee.objects.create(
                        user=user,
                        birth_date=birth_date,
                        hire_date=hire_date,
                        bureau=bureau,
                        direction=direction,
                        position=poste,
                    )
                created_users += 1
            except Exception as e:
                errors.append(f'Ligne {row_num} ({matricule}) : {e}')

        # Rapport
        self.stdout.write(self.style.SUCCESS(f'\n=== Rapport d\'import ==='))
        self.stdout.write(f'Employés créés         : {created_users}')
        self.stdout.write(f'Matricules déjà connus : {skipped_existing}')
        self.stdout.write(f'Directions créées      : {created_directions}')
        if unmatched_bureaux:
            self.stdout.write(self.style.ERROR(
                f'\n✗ Bureaux du fichier non trouvés en base ({len(unmatched_bureaux)}) :'
            ))
            for b in sorted(unmatched_bureaux):
                self.stdout.write(f'  • {b}')
            self.stdout.write(self.style.WARNING(
                'Lancer d\'abord :   python manage.py import_employees --check-bureaux'
                '\nPuis corriger les noms côté fichier ou côté base avant de relancer.'
            ))
        if errors:
            self.stdout.write(self.style.WARNING(f'\nErreurs détaillées ({len(errors)}) :'))
            for e in errors[:20]:
                self.stdout.write(f'  - {e}')
            if len(errors) > 20:
                self.stdout.write(f'  ... et {len(errors) - 20} autres.')
        if dry:
            self.stdout.write(self.style.WARNING('\nDRY-RUN : aucune donnée écrite. Relancer sans --dry-run pour appliquer.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nMot de passe initial pour tous : {DEFAULT_PASSWORD}'
                ' (à changer à la 1ère connexion)'
            ))
