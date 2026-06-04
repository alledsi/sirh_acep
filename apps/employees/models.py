"""Modèles du module Employees — Sprint 2.

Un Employee est rattaché 1-1 à un User (via le matricule), affecté à un Bureau
et à une Direction. Le poste est un simple champ texte saisi à la création.
"""
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel


class Employee(BaseModel):
    """Fiche employé ACEP.

    - `user` : OneToOne vers le compte de connexion (matricule, rôles, mot de passe)
    - `bureau` : lieu d'affectation physique (FK Organisation)
    - `direction` : axe transversal pour l'organigramme
    - `position` : intitulé du poste, texte libre (Caissier, Chargé clientèle, …)
    - `manager` : supérieur hiérarchique direct (FK self, optionnel)
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='employee',
        verbose_name='Compte utilisateur',
    )
    photo = models.ImageField(
        'Photo', upload_to='employees/photos/', null=True, blank=True,
    )
    birth_date = models.DateField('Date de naissance', null=True, blank=True)
    hire_date = models.DateField('Date d\'embauche')

    bureau = models.ForeignKey(
        'organization.Bureau',
        on_delete=models.PROTECT,
        related_name='employees',
        verbose_name="Bureau d'affectation",
    )
    direction = models.ForeignKey(
        'organization.Direction',
        on_delete=models.PROTECT,
        related_name='employees',
        verbose_name='Direction',
    )
    position = models.CharField(
        'Poste / Fonction',
        max_length=200,
        help_text='Intitulé libre : Caissier, Chargé clientèle, Directeur d\'agence, etc.',
    )

    manager = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reports',
        verbose_name='Manager hiérarchique',
    )

    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Employé'
        verbose_name_plural = 'Employés'
        ordering = ['user__matricule']
        indexes = [
            models.Index(fields=['bureau']),
            models.Index(fields=['direction']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.matricule} — {self.user.get_full_name() or self.user.email}"

    def get_absolute_url(self):
        return reverse('employees:employee_detail', kwargs={'pk': self.pk})

    # ---------- Propriétés calculées ----------
    @property
    def matricule(self):
        return self.user.matricule

    @property
    def full_name(self):
        return self.user.get_full_name()

    @property
    def initials(self):
        first = (self.user.first_name or '')[:1].upper()
        last = (self.user.last_name or '')[:1].upper()
        return f"{first}{last}" or self.user.matricule[:2].upper()

    @property
    def agence(self):
        return self.bureau.agence

    @property
    def mutuelle(self):
        return self.bureau.agence.mutuelle

    @property
    def current_contract(self):
        """Retourne le contrat actif le plus récent."""
        return self.contracts.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.functions.Now())
        ).order_by('-start_date').first()


class Contract(BaseModel):
    """Contrat de travail d'un employé. Un employé peut avoir plusieurs contrats
    successifs (CDD enchaînés, transformation CDD→CDI, etc.)."""

    CONTRACT_CDI = 'CDI'
    CONTRACT_CDD = 'CDD'
    CONTRACT_STAGE = 'STAGE'
    CONTRACT_CONSULTANT = 'CONSULTANT'
    CONTRACT_TYPES = [
        (CONTRACT_CDI, 'CDI'),
        (CONTRACT_CDD, 'CDD'),
        (CONTRACT_STAGE, 'Stage'),
        (CONTRACT_CONSULTANT, 'Consultant'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='contracts',
        verbose_name='Employé',
    )
    contract_type = models.CharField('Type', max_length=20, choices=CONTRACT_TYPES, default=CONTRACT_CDI)
    start_date = models.DateField('Date de début')
    end_date = models.DateField('Date de fin', null=True, blank=True, help_text='Vide pour CDI')
    weekly_hours = models.DecimalField('Heures hebdomadaires', max_digits=5, decimal_places=2, default=40)
    salary_gross = models.DecimalField(
        'Salaire brut mensuel (FCFA)',
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    notes = models.TextField('Notes', blank=True)

    class Meta:
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.get_contract_type_display()} — {self.employee.user.matricule} ({self.start_date:%d/%m/%Y})'


class EmployeeDocument(BaseModel):
    """Document attaché à un employé (contrat scanné, pièce d'identité, etc.)."""
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='documents',
        verbose_name='Employé',
    )
    name = models.CharField('Intitulé', max_length=200)
    file = models.FileField('Fichier', upload_to='employees/documents/')
    description = models.TextField('Description', blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='documents_uploaded',
        verbose_name='Déposé par',
    )

    class Meta:
        verbose_name = 'Document employé'
        verbose_name_plural = 'Documents employés'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.employee.user.matricule})'
