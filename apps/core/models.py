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
    ROLE_CHEF_AGENCE = 'CHEF_AGENCE'
    ROLE_DIRECTEUR = 'DIRECTEUR'
    ROLE_RH = 'RH'
    ROLE_DG = 'DG'
    ROLE_CHOICES = [
        (ROLE_AGENT, 'Agent'),
        (ROLE_CHEF_AGENCE, "Chef d'agence"),
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
        help_text='Liste de rôles (cumulables) : AGENT, CHEF_AGENCE, DIRECTEUR, RH, DG',
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
    def is_chef_agence(self):
        return self.has_role(self.ROLE_CHEF_AGENCE)

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


class BroadcastMessage(models.Model):
    """Message diffusé à tous les utilisateurs connectés (RH → personnel).

    Un seul message peut être actif à la fois (contrainte applicative).
    Quand un message est activé, les précédents sont automatiquement désactivés.
    Chaque utilisateur voit le message une fois par session (dismissable).
    """
    LEVEL_INFO = 'INFO'
    LEVEL_IMPORTANT = 'IMPORTANT'
    LEVEL_URGENT = 'URGENT'
    LEVEL_CHOICES = [
        (LEVEL_INFO, 'Information'),
        (LEVEL_IMPORTANT, 'Important'),
        (LEVEL_URGENT, 'Urgent'),
    ]

    title = models.CharField('Titre', max_length=200)
    body = models.TextField('Message', help_text='Texte du message. Les sauts de ligne sont préservés.')
    level = models.CharField('Niveau', max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    is_active = models.BooleanField(
        'Diffusé',
        default=False,
        help_text="Si coché, ce message s'affiche à tous les utilisateurs à la connexion. Les autres messages sont automatiquement désactivés.",
    )
    created_by = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='broadcast_messages', verbose_name='Créé par',
    )
    created_at = models.DateTimeField('Créé le', auto_now_add=True)
    updated_at = models.DateTimeField('Modifié le', auto_now=True)
    activated_at = models.DateTimeField('Diffusé le', null=True, blank=True)

    class Meta:
        verbose_name = 'Message diffusé'
        verbose_name_plural = 'Messages diffusés'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Si on active ce message, désactiver tous les autres."""
        from django.utils import timezone as tz
        if self.is_active:
            # Désactiver les autres
            BroadcastMessage.objects.exclude(pk=self.pk).filter(is_active=True).update(
                is_active=False
            )
            if not self.activated_at:
                self.activated_at = tz.now()
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Retourne le message actuellement diffusé, ou None."""
        return cls.objects.filter(is_active=True).first()


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
