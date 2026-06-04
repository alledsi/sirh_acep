"""Services métier du module Attendance.

`record_punch(action, employee, request)` est le point d'entrée pour toutes les
actions de pointage. Il :
  1. récupère l'IP source via apps.core.services.get_client_ip(request)
  2. résout le bureau via apps.organization.services.resolve_bureau_from_ip(ip)
  3. crée/met à jour le TimeEntry du jour
  4. déclenche detect_anomalies() pour mettre à jour la liste des anomalies

Les seuils (retard, pause longue) sont définis dans constants.py — ils seront
remplacés par une consultation du Planning au Sprint 4.
"""
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services import get_client_ip
from apps.organization.services import resolve_bureau_from_ip

from .constants import (
    DEFAULT_ARRIVAL_REFERENCE,
    DEFAULT_ARRIVAL_TOLERANCE,
    DEFAULT_MAX_BREAK_DURATION,
)
from .models import Anomaly, TimeEntry


def _get_planning_settings_for_date(target_date):
    """Récupère (start_time, tolerance, max_break_duration) à partir du planning.

    Si le module Planning n'a pas encore été initialisé, on retombe sur les
    constantes par défaut.
    """
    try:
        from apps.planning.services import get_active_planning, get_daily_schedule
        planning = get_active_planning()
        daily = get_daily_schedule(target_date)
    except Exception:
        return DEFAULT_ARRIVAL_REFERENCE, DEFAULT_ARRIVAL_TOLERANCE, DEFAULT_MAX_BREAK_DURATION

    start = daily.start_time if (daily and daily.start_time) else DEFAULT_ARRIVAL_REFERENCE
    tolerance = timedelta(minutes=planning.tolerance_minutes) if planning else DEFAULT_ARRIVAL_TOLERANCE
    max_break = planning.max_break_duration if planning else DEFAULT_MAX_BREAK_DURATION
    return start, tolerance, max_break


ACTION_ARRIVAL = 'arrival'
ACTION_BREAK_START = 'break_start'
ACTION_BREAK_END = 'break_end'
ACTION_DEPARTURE = 'departure'


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def get_or_create_today_entry(employee) -> TimeEntry:
    """Récupère le TimeEntry du jour pour l'employé, en le créant si besoin."""
    today = timezone.localdate()
    entry, _ = TimeEntry.objects.get_or_create(employee=employee, work_date=today)
    return entry


def get_today_entry(employee) -> TimeEntry | None:
    """Récupère le TimeEntry du jour s'il existe, sans le créer."""
    return TimeEntry.objects.filter(
        employee=employee,
        work_date=timezone.localdate(),
    ).first()


# ----------------------------------------------------------------------------
# Action de pointage
# ----------------------------------------------------------------------------

@transaction.atomic
def record_punch(action: str, employee, request) -> TimeEntry:
    """Enregistre une action de pointage. Renvoie le TimeEntry mis à jour.

    Lève ValidationError si l'action n'est pas autorisée dans l'état actuel
    (ex : pointer arrivée alors qu'on est déjà arrivé).
    """
    if action not in (ACTION_ARRIVAL, ACTION_BREAK_START, ACTION_BREAK_END, ACTION_DEPARTURE):
        raise ValidationError(f"Action inconnue : {action}")

    entry = get_or_create_today_entry(employee)
    now = timezone.now()
    ip = get_client_ip(request)
    bureau = resolve_bureau_from_ip(ip) if ip else None

    if action == ACTION_ARRIVAL:
        if entry.arrival_time:
            raise ValidationError("Vous avez déjà pointé votre arrivée aujourd'hui.")
        entry.arrival_time = now
        entry.arrival_bureau = bureau
        entry.arrival_ip = ip

    elif action == ACTION_BREAK_START:
        if not entry.arrival_time:
            raise ValidationError("Pointez d'abord votre arrivée.")
        if entry.departure_time:
            raise ValidationError("Vous êtes déjà parti.")
        if entry.break_start:
            raise ValidationError("Vous avez déjà commencé une pause.")
        entry.break_start = now
        entry.break_start_bureau = bureau
        entry.break_start_ip = ip

    elif action == ACTION_BREAK_END:
        if not entry.break_start:
            raise ValidationError("Vous n'êtes pas en pause.")
        if entry.break_end:
            raise ValidationError("La pause est déjà terminée.")
        entry.break_end = now
        entry.break_end_bureau = bureau
        entry.break_end_ip = ip

    elif action == ACTION_DEPARTURE:
        if not entry.arrival_time:
            raise ValidationError("Pointez d'abord votre arrivée.")
        if entry.departure_time:
            raise ValidationError("Vous êtes déjà parti.")
        if entry.break_start and not entry.break_end:
            raise ValidationError("Terminez votre pause avant de pointer le départ.")
        entry.departure_time = now
        entry.departure_bureau = bureau
        entry.departure_ip = ip

    entry.save()
    detect_anomalies(entry)
    return entry


@transaction.atomic
def cancel_departure(employee) -> TimeEntry | None:
    """Annule le départ pointé aujourd'hui (en cas d'erreur)."""
    entry = get_today_entry(employee)
    if not entry or not entry.departure_time:
        raise ValidationError("Aucun départ à annuler aujourd'hui.")
    entry.departure_time = None
    entry.departure_bureau = None
    entry.departure_ip = None
    entry.save()
    detect_anomalies(entry)
    return entry


# ----------------------------------------------------------------------------
# Détection d'anomalies
# ----------------------------------------------------------------------------

def detect_anomalies(time_entry: TimeEntry) -> list[Anomaly]:
    """Re-évalue toutes les anomalies pour ce TimeEntry.

    Stratégie : on supprime les anomalies existantes puis on les recrée selon
    l'état actuel. Les notes de validation sont conservées si l'anomalie
    persiste (matching par type).
    """
    # Conserve les notes de validation existantes pour les réappliquer
    existing_acks = {
        a.anomaly_type: (a.is_acknowledged, a.acknowledged_by, a.acknowledged_at, a.acknowledgement_note)
        for a in time_entry.anomalies.all()
    }

    time_entry.anomalies.all().delete()
    created: list[Anomaly] = []

    # --- LATE : arrivée + tolérance dépassée (selon Planning)
    arrival_ref, tolerance, max_break = _get_planning_settings_for_date(time_entry.work_date)
    if time_entry.arrival_time:
        ref_dt = datetime.combine(
            time_entry.work_date,
            arrival_ref,
            tzinfo=time_entry.arrival_time.tzinfo,
        )
        delay = time_entry.arrival_time - ref_dt
        if delay > tolerance:
            minutes = int(delay.total_seconds() // 60)
            created.append(Anomaly(
                time_entry=time_entry,
                anomaly_type=Anomaly.TYPE_LATE,
                severity=Anomaly.SEVERITY_WARNING,
                description=f"Arrivée à {time_entry.arrival_time:%H:%M} — retard de {minutes} min (référence {arrival_ref:%H:%M}).",
            ))

    # --- UNKNOWN_IP : pointage depuis une IP non rattachée
    for ip_field, bureau_field, label in [
        ('arrival_ip', 'arrival_bureau', 'arrivée'),
        ('break_start_ip', 'break_start_bureau', 'début pause'),
        ('break_end_ip', 'break_end_bureau', 'fin pause'),
        ('departure_ip', 'departure_bureau', 'départ'),
    ]:
        if getattr(time_entry, ip_field) and not getattr(time_entry, bureau_field):
            created.append(Anomaly(
                time_entry=time_entry,
                anomaly_type=Anomaly.TYPE_UNKNOWN_IP,
                severity=Anomaly.SEVERITY_CRITICAL,
                description=(
                    f"IP {getattr(time_entry, ip_field)} non rattachée à un bureau "
                    f"(au moment du pointage {label})."
                ),
            ))
            break

    # --- INCOHERENCE_BUREAU : bureau de connexion ≠ bureau d'affectation
    if time_entry.arrival_bureau and time_entry.arrival_bureau_id != time_entry.employee.bureau_id:
        created.append(Anomaly(
            time_entry=time_entry,
            anomaly_type=Anomaly.TYPE_INCOHERENCE_BUREAU,
            severity=Anomaly.SEVERITY_INFO,
            description=(
                f"Connecté depuis {time_entry.arrival_bureau.name} "
                f"(affectation : {time_entry.employee.bureau.name})."
            ),
        ))

    # --- LONG_BREAK : pause > durée maximale (selon Planning)
    if time_entry.break_duration and time_entry.break_duration > max_break:
        duration_min = int(time_entry.break_duration.total_seconds() // 60)
        max_min = int(max_break.total_seconds() // 60)
        created.append(Anomaly(
            time_entry=time_entry,
            anomaly_type=Anomaly.TYPE_LONG_BREAK,
            severity=Anomaly.SEVERITY_INFO,
            description=f"Pause de {duration_min} min (limite {max_min} min).",
        ))

    # --- NO_DEPARTURE : journée passée sans départ pointé
    if time_entry.arrival_time and not time_entry.departure_time:
        if time_entry.work_date < timezone.localdate():
            created.append(Anomaly(
                time_entry=time_entry,
                anomaly_type=Anomaly.TYPE_NO_DEPARTURE,
                severity=Anomaly.SEVERITY_CRITICAL,
                description=(
                    f"Pas de pointage de départ enregistré pour le "
                    f"{time_entry.work_date:%d/%m/%Y}."
                ),
            ))

    # Persiste et réapplique les acquittements existants
    for ano in created:
        ano.save()
        ack = existing_acks.get(ano.anomaly_type)
        if ack and ack[0]:
            ano.is_acknowledged, ano.acknowledged_by, ano.acknowledged_at, ano.acknowledgement_note = ack
            ano.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at', 'acknowledgement_note'])

    return created


def detect_missing_departures_for_yesterday() -> int:
    """Scanne les pointages de la veille sans départ et crée les anomalies.

    À appeler une fois par jour (cron / Task Scheduler / Celery beat).
    Renvoie le nombre d'anomalies créées.
    """
    yesterday = timezone.localdate() - timedelta(days=1)
    entries = TimeEntry.objects.filter(
        work_date=yesterday,
        arrival_time__isnull=False,
        departure_time__isnull=True,
    )
    count = 0
    for entry in entries:
        anos = detect_anomalies(entry)
        count += sum(1 for a in anos if a.anomaly_type == Anomaly.TYPE_NO_DEPARTURE)
    return count


# ----------------------------------------------------------------------------
# Restriction samedi/dimanche (Sprint 4 affinera avec le planning)
# ----------------------------------------------------------------------------

def can_punch_today(employee) -> tuple[bool, str]:
    """Indique si l'employé peut pointer aujourd'hui — selon le Planning.

    - Jours en mode NOT_WORKED (ex : dimanche) → interdit
    - Jours en mode MANDATORY → autorisé
    - Jours en mode OPTIONAL (samedi) → autorisé pour tout le monde
      (pointage libre : qui travaille pointe, qui ne travaille pas s'abstient)
    """
    today = timezone.localdate()
    try:
        from apps.planning.services import can_punch_on
        return can_punch_on(employee, today)
    except Exception:
        # Fallback si le module Planning n'est pas encore migré
        if today.weekday() == 6:
            return False, "Le dimanche est un jour de repos."
        return True, ""
