"""Modèles transverses : Custom User (matricule comme identifiant) + BaseModel."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Manager qui crée des utilisateurs identifiés par leur matricule."""

    use_in_migrations = True

    def _create_user(self, matricule, email, password, **extra_fields):
        if not matricule:
            raise ValueError('Le matricule est obligatoire.')
        email = self.normalize_email(email)
        user = self.model(matricule=matricule, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, matricule, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(matricule, email, password, **extra_fields)

    def create_superuser(self, matricule, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('roles', ['AGENT', 'RH', 'DG'])
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superuser doit avoir is_superuser=True.')
        return self._create_user(matricule, email, password, **extra_fields)


class User(AbstractUser):
    """Utilisateur étendu pour ACEP.

    Le matricule remplace le username comme identifiant de connexion.
    Les rôles sont stockés en liste JSON et sont cumulables.
    """

    ROLE_AGENT = 'AGENT'
    ROLE_DIRECTEUR = 'DIRECTEUR'
    ROLE_RH = 'RH'
    ROLE_DG = 'DG'
    ROLE_CHOICES = [
        (ROLE_AGENT, 'Agent'),
        (ROLE_DIRECTEUR, 'Directeur'),
        (ROLE_RH, 'Ressources Humaines'),
        (ROLE_DG, 'Directeur Général'),
    ]

    # Le username Django par défaut est supprimé au profit du matricule
    username = None

    matricule = models.CharField('Matricule', max_length=20, unique=True)
    phone = models.CharField('Téléphone', max_length=30, blank=True)
    must_change_password = models.BooleanField(
        'Mot de passe à changer à la prochaine connexion',
        default=False,
    )
    roles = models.JSONField(
        'Rôles',
        default=list,
        blank=True,
        help_text='Liste de rôles (cumulables) : AGENT, DIRECTEUR, RH, DG',
    )

    USERNAME_FIELD = 'matricule'
    # email n'est plus obligatoire (la majorité des employés ACEP n'en ont pas
    # encore en base). Restera demandé interactivement seulement par createsuperuser.
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['matricule']

    def __str__(self):
        full = self.get_full_name()
        return f'{self.matricule} — {full}' if full else self.matricule

    # ---------- Helpers rôles ----------
    def has_role(self, role):
        return role in (self.roles or [])

    @property
    def is_agent(self):
        return self.has_role(self.ROLE_AGENT)

    @property
    def is_directeur(self):
        return self.has_role(self.ROLE_DIRECTEUR)

    @property
    def is_rh(self):
        return self.has_role(self.ROLE_RH)

    @property
    def is_dg(self):
        return self.has_role(self.ROLE_DG)

    @property
    def has_global_access(self):
        """RH et DG ont une visibilité globale (tous les employés, tous les sites)."""
        return self.is_rh or self.is_dg


class BaseModel(models.Model):
    """Modèle abstrait avec horodatage et soft delete.

    Tous les modèles métier héritent de ce modèle. Permet de tracer la
    création et la dernière modification, et de désactiver une entrée
    sans la supprimer physiquement (préserve les références historiques).
    """
    created_at = models.DateTimeField('Créé le', auto_now_add=True)
    updated_at = models.DateTimeField('Modifié le', auto_now=True)
    is_deleted = models.BooleanField('Archivé', default=False)
    deleted_at = models.DateTimeField('Archivé le', null=True, blank=True)

    class Meta:
        abstract = True
