"""Modèles du module Organisation — Sprint 1.

Hiérarchie ACEP : Mutuelle → Agence → Bureau (+ axe transversal Direction).
Un Bureau peut être rattaché à plusieurs plages IP (relation 1-N IPBureauMapping).
"""
from ipaddress import ip_address, ip_network

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel


class Mutuelle(BaseModel):
    """Niveau le plus haut de la hiérarchie organisationnelle ACEP."""
    code = models.CharField('Code', max_length=20, unique=True, help_text='Ex : MUT-DKR')
    name = models.CharField('Nom', max_length=200)
    description = models.TextField('Description', blank=True)
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Mutuelle'
        verbose_name_plural = 'Mutuelles'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def get_absolute_url(self):
        return reverse('organization:mutuelle_list')

    @property
    def bureaux_count(self):
        return Bureau.objects.filter(agence__mutuelle=self).count()


class Agence(BaseModel):
    """Agence rattachée à une mutuelle."""
    mutuelle = models.ForeignKey(
        Mutuelle, on_delete=models.PROTECT, related_name='agences',
        verbose_name='Mutuelle',
    )
    code = models.CharField('Code', max_length=20, unique=True, help_text='Ex : AG-VDN')
    name = models.CharField('Nom', max_length=200)
    region = models.CharField('Région', max_length=100, blank=True)
    address = models.TextField('Adresse', blank=True)
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Agence'
        verbose_name_plural = 'Agences'
        ordering = ['mutuelle__code', 'code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def get_absolute_url(self):
        return reverse('organization:agence_list')


class Bureau(BaseModel):
    """Bureau (lieu physique) rattaché à une agence.

    Un bureau peut être associé à plusieurs plages IP via IPBureauMapping.
    Lors d'un pointage, l'IP source est résolue en bureau via ces plages.
    """
    agence = models.ForeignKey(
        Agence, on_delete=models.PROTECT, related_name='bureaux',
        verbose_name='Agence',
    )
    code = models.CharField('Code', max_length=20, unique=True, help_text='Ex : BUR-VDN-01')
    name = models.CharField('Nom', max_length=200)
    address = models.TextField('Adresse', blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Bureau'
        verbose_name_plural = 'Bureaux'
        ordering = ['agence__code', 'code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def get_absolute_url(self):
        return reverse('organization:bureau_detail', kwargs={'pk': self.pk})

    @property
    def mutuelle(self):
        return self.agence.mutuelle

    @property
    def ip_patterns(self):
        """Liste des plages IP actives (str)."""
        return list(self.ip_mappings.filter(is_active=True).values_list('ip_pattern', flat=True))


class Direction(BaseModel):
    """Direction (axe transversal pour l'organigramme).

    Regroupe des employés indépendamment de leur bureau d'affectation.
    Le Directeur est un Employee (rattachement défini en Sprint 2).
    """
    code = models.CharField('Code', max_length=20, unique=True, help_text='Ex : DIR-COM')
    name = models.CharField('Nom', max_length=200)
    description = models.TextField('Description', blank=True)
    parent_direction = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='sub_directions',
        verbose_name='Direction parente',
    )
    directeur = models.ForeignKey(
        'employees.Employee',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='directions_dirigees',
        verbose_name='Directeur en charge',
        help_text="L'employé qui dirige cette direction (doit avoir le rôle Directeur).",
    )
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Direction'
        verbose_name_plural = 'Directions'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'

    def get_absolute_url(self):
        return reverse('organization:direction_list')


def _validate_ip_pattern(value: str):
    """Vérifie que `value` est une plage CIDR (192.168.1.0/24) ou une IP unique."""
    if not value:
        raise ValidationError('La plage IP est obligatoire.')
    # On essaie d'abord en tant que réseau (accepte les CIDR), sinon IP simple.
    try:
        ip_network(value, strict=False)
        return
    except ValueError:
        pass
    try:
        ip_address(value)
    except ValueError:
        raise ValidationError(
            f"Format invalide : '{value}'. Utilisez un CIDR (192.168.1.0/24) ou une IP (192.168.1.42)."
        )


class IPBureauMapping(BaseModel):
    """Mapping IP → Bureau.

    Un bureau peut avoir plusieurs plages IP (différents étages, bâtiments, réseaux).
    Lors du pointage, l'IP source est comparée à ces plages pour déterminer le bureau.
    """
    bureau = models.ForeignKey(
        Bureau, on_delete=models.CASCADE, related_name='ip_mappings',
        verbose_name='Bureau',
    )
    ip_pattern = models.CharField(
        'Plage IP',
        max_length=50,
        validators=[_validate_ip_pattern],
        help_text='Format CIDR (192.168.7.0/24) ou IP unique (192.168.7.42)',
    )
    description = models.CharField(
        'Description', max_length=200, blank=True,
        help_text='Optionnel : étage, bâtiment, type de réseau…',
    )
    is_active = models.BooleanField('Active', default=True)

    class Meta:
        verbose_name = 'Plage IP de bureau'
        verbose_name_plural = 'Plages IP de bureau'
        ordering = ['bureau__code', 'ip_pattern']
        constraints = [
            models.UniqueConstraint(
                fields=['bureau', 'ip_pattern'],
                name='unique_bureau_ip_pattern',
            ),
        ]

    def __str__(self):
        return f'{self.ip_pattern} → {self.bureau.code}'

    def clean(self):
        super().clean()
        _validate_ip_pattern(self.ip_pattern)
