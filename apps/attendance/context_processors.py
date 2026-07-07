"""Context processors du module Attendance.

Expose l'heure de fin de journée pour le rappel de départ (notif navigateur).
"""
from django.utils import timezone


def pointage_reminder(request):
    """Retourne les infos nécessaires au rappel JS "N'oubliez pas de pointer".

    Créneaux ACEP :
      - Lundi-Jeudi : 17:05 et 17:25 (fin de journée 17:30)
      - Vendredi    : 12:55 uniquement (fin de journée 13:00)

    Le JS déclenche une notification navigateur à ces heures si l'utilisateur
    est actuellement présent (arrivée sans départ).

    Variables template :
      - `pointage_end_time_hhmm` : heure de fin (ex 17:30) pour affichage
      - `pointage_reminder_slots` : liste JSON de HH:MM (créneaux d'alerte)
      - `pointage_needs_reminder` : True si l'utilisateur est actuellement présent
    """
    import json

    ctx = {
        'pointage_end_time_hhmm': '',
        'pointage_reminder_slots': '[]',
        'pointage_needs_reminder': False,
    }
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return ctx

    try:
        from apps.employees.models import Employee
        from apps.attendance.services import get_today_entry
    except Exception:
        return ctx

    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        return ctx

    today = timezone.localdate()
    weekday = today.weekday()  # 0=Lundi, 4=Vendredi, 5=Sam, 6=Dim

    if weekday == 4:  # Vendredi
        slots = ['12:55']
        end_time = '13:00'
    elif weekday < 4:  # Lundi à Jeudi
        slots = ['17:05', '17:25']
        end_time = '17:30'
    else:  # Weekend
        return ctx

    ctx['pointage_end_time_hhmm'] = end_time
    ctx['pointage_reminder_slots'] = json.dumps(slots)

    # Rappel utile uniquement si l'agent est actuellement présent
    try:
        entry = get_today_entry(employee)
    except Exception:
        entry = None
    if entry and entry.arrival_time and not entry.departure_time:
        ctx['pointage_needs_reminder'] = True

    return ctx
