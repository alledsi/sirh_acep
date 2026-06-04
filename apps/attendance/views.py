"""Vues du module Attendance."""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.employees.models import Employee

from .models import Anomaly, TimeEntry
from .services import (
    ACTION_ARRIVAL, ACTION_BREAK_END, ACTION_BREAK_START, ACTION_DEPARTURE,
    can_punch_today, cancel_departure, get_today_entry, record_punch,
)


def _get_employee_or_none(request):
    """Récupère l'Employee lié à l'utilisateur connecté ; renvoie None sinon."""
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


def _no_employee_response(request):
    """Affiche un message clair quand l'utilisateur n'a pas de fiche Employee.
    Évite la boucle de redirection vers core:home."""
    return render(request, 'attendance/no_employee.html')


# ============ Dashboard agent (page d'accueil pointage) ============

@login_required
def dashboard(request):
    """Tableau de bord de l'agent — fidèle à la démo (4 stats, pointage, chart, notifs)."""
    import json

    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)

    today_entry = get_today_entry(employee)
    can_punch, punch_message = can_punch_today(employee)

    # Stats semaine et mois
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday())
    week_entries = TimeEntry.objects.filter(
        employee=employee, work_date__gte=monday, work_date__lte=today,
    ).order_by('work_date')
    month_entries = TimeEntry.objects.filter(
        employee=employee, work_date__year=today.year, work_date__month=today.month,
    )

    def total_hours(qs):
        total = timedelta()
        days = 0
        for e in qs:
            d = e.worked_duration
            if d:
                total += d
                days += 1
        return total, days

    def fmt_hm(td: timedelta) -> str:
        """Formate une durée en 'Xh YY' (heures et minutes, sans secondes)."""
        total_minutes = int(td.total_seconds() // 60)
        h, m = divmod(total_minutes, 60)
        return f"{h}h{m:02d}"

    week_total_td, week_days = total_hours(week_entries)
    month_total_td, month_days = total_hours(month_entries)
    week_total = fmt_hm(week_total_td)
    month_total = fmt_hm(month_total_td)

    # Données du graphique hebdomadaire (5 jours Lun-Ven)
    # `minutes` est un entier = source de vérité (cohérent avec les KPIs).
    # `hours` est calculé côté front à partir des minutes pour la hauteur de barre.
    week_chart = []
    entries_by_date = {e.work_date: e for e in week_entries}
    for i in range(5):
        d = monday + timedelta(days=i)
        e = entries_by_date.get(d)
        minutes = int(e.worked_duration.total_seconds() // 60) if e and e.worked_duration else 0
        week_chart.append({
            'label': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven'][i],
            'minutes': minutes,
        })

    # Anomalies récentes (notifications)
    recent_anomalies = Anomaly.objects.filter(
        time_entry__employee=employee,
        time_entry__work_date__gte=today - timedelta(days=14),
    ).order_by('-time_entry__work_date')[:5]

    return render(request, 'attendance/dashboard.html', {
        'employee': employee,
        'today_entry': today_entry,
        'can_punch': can_punch,
        'punch_message': punch_message,
        'week_total': week_total,
        'week_days': week_days,
        'month_total': month_total,
        'month_days': month_days,
        'week_chart_data': json.dumps(week_chart),
        'recent_anomalies': recent_anomalies,
        'anomalies_today_count': today_entry.anomalies.count() if today_entry else 0,
    })


@login_required
def pointer(request):
    """Page dédiée au pointage — focus sur les 4 boutons (clock big)."""
    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)
    today_entry = get_today_entry(employee)
    can_punch, punch_message = can_punch_today(employee)
    return render(request, 'attendance/pointer.html', {
        'employee': employee,
        'today_entry': today_entry,
        'can_punch': can_punch,
        'punch_message': punch_message,
    })


# ============ Actions de pointage (POST uniquement) ============

@login_required
@require_POST
def action_arrival(request):
    return _do_punch(request, ACTION_ARRIVAL, "Arrivée pointée.")


@login_required
@require_POST
def action_break_start(request):
    return _do_punch(request, ACTION_BREAK_START, "Début de pause pointé.")


@login_required
@require_POST
def action_break_end(request):
    return _do_punch(request, ACTION_BREAK_END, "Fin de pause pointée.")


@login_required
@require_POST
def action_departure(request):
    return _do_punch(request, ACTION_DEPARTURE, "Départ pointé.")


def _do_punch(request, action: str, success_msg: str):
    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)

    can_punch, msg = can_punch_today(employee)
    if not can_punch:
        messages.error(request, msg)
        return redirect('attendance:dashboard')

    try:
        record_punch(action, employee, request)
        messages.success(request, success_msg)
    except ValidationError as e:
        messages.error(request, '; '.join(e.messages))
    next_url = request.POST.get('next') or 'attendance:dashboard'
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect(next_url)


@login_required
@require_POST
def action_cancel_departure(request):
    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)
    try:
        cancel_departure(employee)
        messages.warning(request, "Départ annulé.")
    except ValidationError as e:
        messages.error(request, '; '.join(e.messages))
    return redirect('attendance:dashboard')


# ============ Historique ============

@login_required
def historique(request):
    """Historique des pointages : semaine / mois / année."""
    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)

    periode = request.GET.get('periode', 'semaine')
    today = timezone.localdate()

    if periode == 'mois':
        start = today.replace(day=1)
        end = today
        label = today.strftime('%B %Y').capitalize()
    elif periode == 'annee':
        start = today.replace(month=1, day=1)
        end = today
        label = str(today.year)
    else:  # semaine
        periode = 'semaine'
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        start = monday
        end = sunday
        label = f"Du {monday:%d/%m} au {sunday:%d/%m/%Y}"

    entries = (
        TimeEntry.objects
        .filter(employee=employee, work_date__gte=start, work_date__lte=end)
        .select_related('arrival_bureau', 'departure_bureau')
        .prefetch_related('anomalies')
        .order_by('work_date')
    )

    total = timedelta()
    days_count = 0
    for e in entries:
        d = e.worked_duration
        if d:
            total += d
            days_count += 1

    return render(request, 'attendance/historique.html', {
        'employee': employee,
        'periode': periode,
        'label': label,
        'entries': entries,
        'total': total,
        'days_count': days_count,
    })


@login_required
def time_entry_detail(request, pk):
    employee = _get_employee_or_none(request)
    if not employee:
        return _no_employee_response(request)
    entry = get_object_or_404(
        TimeEntry.objects.prefetch_related('anomalies'),
        pk=pk,
    )
    # Un agent voit uniquement ses propres pointages ; RH/DG voient tout
    if entry.employee_id != employee.id and not request.user.has_global_access:
        raise Http404()
    return render(request, 'attendance/time_entry_detail.html', {
        'entry': entry,
        'employee': entry.employee,
    })
