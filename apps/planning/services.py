"""Services du module Planning.

`get_active_planning()` est le point d'entrée principal : il garantit qu'un
Planning existe (création lazy au premier appel avec des défauts ACEP).

Les services d'attendance (`detect_anomalies`, `can_punch_today`) consultent
ces fonctions pour appliquer la politique en vigueur.
"""
from datetime import date, time, timedelta

from django.db import transaction

from .models import DailySchedule, Planning


_DEFAULT_DAILY_SETUP = [
    # (day, mode, start, end, break_start, break_end)
    (0, DailySchedule.MODE_MANDATORY, time(8, 0), time(17, 0), time(12, 30), time(13, 30)),  # Lundi
    (1, DailySchedule.MODE_MANDATORY, time(8, 0), time(17, 0), time(12, 30), time(13, 30)),  # Mardi
    (2, DailySchedule.MODE_MANDATORY, time(8, 0), time(17, 0), time(12, 30), time(13, 30)),  # Mercredi
    (3, DailySchedule.MODE_MANDATORY, time(8, 0), time(17, 0), time(12, 30), time(13, 30)),  # Jeudi
    (4, DailySchedule.MODE_MANDATORY, time(8, 0), time(17, 0), time(12, 30), time(13, 30)),  # Vendredi
    (5, DailySchedule.MODE_OPTIONAL, time(8, 0), time(13, 0), None, None),                    # Samedi (pointage libre)
    (6, DailySchedule.MODE_NOT_WORKED, None, None, None, None),                                # Dimanche
]


@transaction.atomic
def get_active_planning() -> Planning:
    """Récupère le Planning unique d'ACEP, en le créant s'il n'existe pas."""
    planning = Planning.objects.filter(is_active=True).first()
    if planning:
        return planning

    planning = Planning.objects.create(name='Planning ACEP')
    for day, mode, st, et, bs, be in _DEFAULT_DAILY_SETUP:
        DailySchedule.objects.create(
            planning=planning,
            day_of_week=day,
            mode=mode,
            start_time=st, end_time=et,
            break_start=bs, break_end=be,
        )
    return planning


def get_daily_schedule(target_date: date) -> DailySchedule | None:
    """Récupère l'horaire pour le jour de la semaine de target_date."""
    planning = get_active_planning()
    return planning.schedules.filter(day_of_week=target_date.weekday()).first()


def can_punch_on(employee, target_date: date) -> tuple[bool, str]:
    """Indique si l'employé peut pointer à la date donnée selon le planning.

    - Jour NOT_WORKED → pointage interdit (ex : dimanche)
    - Jour MANDATORY ou OPTIONAL → pointage autorisé pour tout le monde
      (MODE_OPTIONAL = jour ouvré libre, typiquement le samedi : l'employé
      qui vient pointe, celui qui ne vient pas n'est pas pénalisé)
    """
    daily = get_daily_schedule(target_date)
    if not daily or daily.mode == DailySchedule.MODE_NOT_WORKED:
        return False, f"{daily.get_day_of_week_display() if daily else target_date.strftime('%A')} n'est pas un jour travaillé."
    return True, ""
