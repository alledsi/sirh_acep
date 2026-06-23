"""Modèles du module Planning — Sprint 4.

Architecture :
- `Planning` : un seul enregistrement actif pour toute ACEP. Définit les
  paramètres globaux (tolérance retard, durée max de pause).
- `DailySchedule` : un par jour de la semaine, rattaché au Planning, qui
  définit les horaires et le mode (NOT_WORKED / MANDATORY / OPTIONAL).
  Le samedi est en mode OPTIONAL (pointage libre).
"""
from datetime import date, time, timedelta

from django.db import models, transaction

from apps.core.models import BaseModel


class Planning(BaseModel):
    """Planning unique d'ACEP — un seul actif à la fois."""

    name = models.CharField('Nom', max_length=200, default='Planning ACEP')
    tolerance_minutes = models.PositiveSmallIntegerField(
        'Tolérance retard (minutes)', default=5,
        help_text='Au-delà de cette tolérance, l\'arrivée est marquée comme un retard.',
    )
    max_break_duration = models.DurationField(
        'Durée maximale de pause',
        default=timedelta(hours=1, minutes=30),
        help_text='Une pause plus longue déclenche une anomalie.',
    )
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Planning'
        verbose_name_plural = 'Plannings'

    def __str__(self):
        return self.name


class DailySchedule(BaseModel):
    """Horaires pour un jour de la semaine."""

    MODE_NOT_WORKED = 'NOT_WORKED'
    MODE_MANDATORY = 'MANDATORY'
    MODE_OPTIONAL = 'OPTIONAL'
    MODE_CHOICES = [
        (MODE_NOT_WORKED, 'Non travaillé'),
        (MODE_MANDATORY, 'Obligatoire'),
        (MODE_OPTIONAL, 'Optionnel (pointage libre)'),
    ]

    DAY_CHOICES = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
        (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
    ]

    planning = models.ForeignKey(
        Planning, on_delete=models.CASCADE, related_name='schedules',
    )
    day_of_week = models.PositiveSmallIntegerField('Jour', choices=DAY_CHOICES)
    mode = models.CharField('Mode', max_length=20, choices=MODE_CHOICES, default=MODE_NOT_WORKED)
    start_time = models.TimeField('Heure d\'arrivée', null=True, blank=True)
    end_time = models.TimeField('Heure de départ', null=True, blank=True)
    break_start = models.TimeField('Début pause', null=True, blank=True)
    break_end = models.TimeField('Fin pause', null=True, blank=True)

    class Meta:
        verbose_name = 'Horaire journalier'
        verbose_name_plural = 'Horaires journaliers'
        ordering = ['planning', 'day_of_week']
        constraints = [
            models.UniqueConstraint(fields=['planning', 'day_of_week'], name='unique_planning_day'),
        ]

    def __str__(self):
        return f'{self.get_day_of_week_display()} — {self.get_mode_display()}'

    @property
    def is_worked(self):
        return self.mode != self.MODE_NOT_WORKED

    @property
    def is_mandatory(self):
        return self.mode == self.MODE_MANDATORY

    @property
    def is_optional(self):
        return self.mode == self.MODE_OPTIONAL


class Holiday(BaseModel):
    """Jour férié — ne génère pas d'anomalie d'absence ce jour-là.

    Si un employé pointe quand même (heures supplémentaires), c'est autorisé.
    Si l'employé ne pointe pas, aucune anomalie n'est créée.
    """
    name = models.CharField('Nom', max_length=200, help_text='Ex : Fête de l\'Indépendance')
    date = models.DateField('Date', unique=True, db_index=True)
    description = models.TextField('Description', blank=True)
    is_paid = models.BooleanField('Férié payé', default=True, help_text='Si coché, pas de retenue.')
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Jour férié'
        verbose_name_plural = 'Jours fériés'
        ordering = ['-date']

    def __str__(self):
        return f'{self.date:%d/%m/%Y} — {self.name}'

    @classmethod
    def is_holiday(cls, target_date: date) -> bool:
        """True si la date est un jour férié actif."""
        return cls.objects.filter(date=target_date, is_active=True).exists()
