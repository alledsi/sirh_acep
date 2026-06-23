"""Modèles du module Attendance (Pointage) — Sprint 3.

Un `TimeEntry` représente une journée de pointage pour un employé donné.
À chaque action de pointage (arrivée, début pause, fin pause, départ), on
enregistre l'heure, l'IP source et le bureau résolu via cette IP.

Le bureau de connexion peut différer du bureau d'affectation : c'est
légitime (mission, remplacement), mais une anomalie INCOHERENCE_BUREAU
est créée pour validation par la Direction.
"""
from datetime import datetime, timedelta

from django.db import models

from apps.core.models import BaseModel


class TimeEntry(BaseModel):
    """Une journée de pointage. Un seul TimeEntry par employé par jour.

    Champs distincts pour arrival / break_start / break_end / departure :
    chaque action capte son heure, son bureau de connexion (résolu par IP)
    et l'IP exacte utilisée.
    """
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
        related_name='time_entries',
        verbose_name='Employé',
    )
    work_date = models.DateField('Date', db_index=True)

    # ----- Arrivée -----
    arrival_time = models.DateTimeField('Heure d\'arrivée', null=True, blank=True)
    arrival_bureau = models.ForeignKey(
        'organization.Bureau', null=True, blank=True,
        related_name='arrivals',
        on_delete=models.SET_NULL,
        verbose_name='Bureau de connexion à l\'arrivée',
    )
    arrival_ip = models.GenericIPAddressField('IP à l\'arrivée', null=True, blank=True)

    # ----- Début pause -----
    break_start = models.DateTimeField('Début pause', null=True, blank=True)
    break_start_bureau = models.ForeignKey(
        'organization.Bureau', null=True, blank=True,
        related_name='break_starts',
        on_delete=models.SET_NULL,
        verbose_name='Bureau au début de pause',
    )
    break_start_ip = models.GenericIPAddressField('IP au début de pause', null=True, blank=True)

    # ----- Fin pause -----
    break_end = models.DateTimeField('Fin pause', null=True, blank=True)
    break_end_bureau = models.ForeignKey(
        'organization.Bureau', null=True, blank=True,
        related_name='break_ends',
        on_delete=models.SET_NULL,
        verbose_name='Bureau à la fin de pause',
    )
    break_end_ip = models.GenericIPAddressField('IP à la fin de pause', null=True, blank=True)

    # ----- Départ -----
    departure_time = models.DateTimeField('Heure de départ', null=True, blank=True)
    departure_bureau = models.ForeignKey(
        'organization.Bureau', null=True, blank=True,
        related_name='departures',
        on_delete=models.SET_NULL,
        verbose_name='Bureau au départ',
    )
    departure_ip = models.GenericIPAddressField('IP au départ', null=True, blank=True)

    # ----- Régularisation manuelle (RH/DG) -----
    is_regularized = models.BooleanField(
        'Pointage régularisé manuellement', default=False,
        help_text='Coché si la RH a modifié manuellement ce pointage (incident technique, oubli, etc.)',
    )
    regularization_reason = models.TextField(
        'Motif de la régularisation', blank=True,
        help_text='Motif détaillé : incident technique, oubli de pointage, etc.',
    )
    regularized_by = models.ForeignKey(
        'core.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='regularizations',
        verbose_name='Régularisé par',
    )
    regularized_at = models.DateTimeField('Régularisé le', null=True, blank=True)

    class Meta:
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        ordering = ['-work_date', 'employee__user__matricule']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'work_date'], name='unique_employee_workdate'),
        ]
        indexes = [
            models.Index(fields=['work_date', 'employee']),
            models.Index(fields=['employee', '-work_date']),
        ]

    def __str__(self):
        return f"{self.employee.user.matricule} — {self.work_date:%d/%m/%Y}"

    # ---------- Propriétés calculées ----------
    @property
    def worked_duration(self) -> timedelta | None:
        """Durée travaillée nette (sans la pause)."""
        if not (self.arrival_time and self.departure_time):
            return None
        total = self.departure_time - self.arrival_time
        if self.break_start and self.break_end:
            total -= (self.break_end - self.break_start)
        return total

    @property
    def break_duration(self) -> timedelta | None:
        if not (self.break_start and self.break_end):
            return None
        return self.break_end - self.break_start

    @property
    def bureau_coherent(self) -> bool | None:
        """True si le bureau de connexion à l'arrivée == bureau d'affectation."""
        if not self.arrival_bureau:
            return None
        return self.arrival_bureau_id == self.employee.bureau_id

    @property
    def is_in_progress(self) -> bool:
        """L'employé est arrivé mais pas encore parti."""
        return self.arrival_time is not None and self.departure_time is None

    @property
    def is_on_break(self) -> bool:
        return self.break_start is not None and self.break_end is None


class Anomaly(BaseModel):
    """Anomalie détectée automatiquement sur un pointage."""

    TYPE_LATE = 'LATE'
    TYPE_NO_DEPARTURE = 'NO_DEPARTURE'
    TYPE_LONG_BREAK = 'LONG_BREAK'
    TYPE_UNKNOWN_IP = 'UNKNOWN_IP'
    TYPE_INCOHERENCE_BUREAU = 'INCOHERENCE_BUREAU'
    ANOMALY_TYPES = [
        (TYPE_LATE, 'Retard'),
        (TYPE_NO_DEPARTURE, 'Départ non pointé'),
        (TYPE_LONG_BREAK, 'Pause anormalement longue'),
        (TYPE_UNKNOWN_IP, 'IP non rattachée à un bureau'),
        (TYPE_INCOHERENCE_BUREAU, "Incohérence : bureau de connexion ≠ bureau d'affectation"),
    ]

    SEVERITY_INFO = 1
    SEVERITY_WARNING = 2
    SEVERITY_CRITICAL = 3
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Info'),
        (SEVERITY_WARNING, 'Avertissement'),
        (SEVERITY_CRITICAL, 'Critique'),
    ]

    time_entry = models.ForeignKey(
        TimeEntry, on_delete=models.CASCADE, related_name='anomalies',
        verbose_name='Pointage',
    )
    anomaly_type = models.CharField('Type', max_length=30, choices=ANOMALY_TYPES)
    severity = models.PositiveSmallIntegerField('Sévérité', choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    description = models.TextField('Description')
    is_acknowledged = models.BooleanField('Validée', default=False)
    acknowledged_by = models.ForeignKey(
        'core.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='anomalies_acknowledged',
        verbose_name='Validée par',
    )
    acknowledged_at = models.DateTimeField('Validée le', null=True, blank=True)
    acknowledgement_note = models.TextField('Note de validation', blank=True)

    class Meta:
        verbose_name = 'Anomalie'
        verbose_name_plural = 'Anomalies'
        ordering = ['-time_entry__work_date', '-severity']
        constraints = [
            models.UniqueConstraint(
                fields=['time_entry', 'anomaly_type'],
                name='unique_anomaly_per_entry_type',
            ),
        ]

    def __str__(self):
        return f"{self.get_anomaly_type_display()} — {self.time_entry}"


class AbsenceJustification(BaseModel):
    """Justification d'absence ou de retard soumise par un agent.

    L'agent fournit un motif + une pièce jointe (certificat médical, etc.).
    La RH/le directeur valide ou rejette la justification.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'En attente'),
        (STATUS_APPROVED, 'Approuvée'),
        (STATUS_REJECTED, 'Rejetée'),
    ]

    TYPE_ABSENCE = 'ABSENCE'
    TYPE_LATE = 'LATE'
    TYPE_EARLY = 'EARLY_DEPARTURE'
    TYPE_OTHER = 'OTHER'
    TYPE_CHOICES = [
        (TYPE_ABSENCE, 'Absence'),
        (TYPE_LATE, 'Retard'),
        (TYPE_EARLY, 'Départ anticipé'),
        (TYPE_OTHER, 'Autre'),
    ]

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='justifications',
        verbose_name='Employé',
    )
    absence_date = models.DateField('Date concernée', db_index=True)
    justification_type = models.CharField(
        'Type', max_length=20, choices=TYPE_CHOICES, default=TYPE_ABSENCE,
    )
    reason = models.TextField('Motif détaillé', help_text='Expliquer la raison.')
    attachment = models.FileField(
        'Pièce jointe',
        upload_to='justifications/%Y/%m/',
        blank=True, null=True,
        help_text='Certificat médical, courrier, etc. (PDF, image)',
    )
    status = models.CharField(
        'Statut', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    reviewed_by = models.ForeignKey(
        'core.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='justifications_reviewed',
        verbose_name='Validée par',
    )
    reviewed_at = models.DateTimeField('Validée le', null=True, blank=True)
    review_note = models.TextField('Note du valideur', blank=True)

    class Meta:
        verbose_name = 'Justification d\'absence'
        verbose_name_plural = 'Justifications d\'absence'
        ordering = ['-absence_date', '-created_at']

    def __str__(self):
        return f"{self.employee} — {self.absence_date:%d/%m/%Y} ({self.get_status_display()})"
