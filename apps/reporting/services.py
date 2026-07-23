"""Services d'agrégation pour le module Reporting.

Fournit les fonctions de calcul utilisées par les dashboards Directeur et
les statistiques RH/DG.
"""
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.attendance.models import Anomaly, TimeEntry
from apps.employees.models import Employee
from apps.organization.models import Agence, Bureau, Direction, Mutuelle


# ----------------------------------------------------------------------------
# Périmètre du Directeur
# ----------------------------------------------------------------------------

def get_directeur_directions(user):
    """Retourne le queryset des Directions sous la responsabilité de cet utilisateur.

    Règles :
      1. Directions où il est explicitement désigné `Direction.directeur` (FK),
         plus leurs sous-directions récursivement.
      2. À défaut, si l'utilisateur a le rôle DIRECTEUR, on retombe sur sa propre
         direction d'affectation (Employee.direction) — c'est le comportement
         attendu : recevoir le rôle Directeur donne accès aux infos de sa direction.
    """
    try:
        employee = user.employee
    except Exception:
        return Direction.objects.none()

    direct_ids = set(employee.directions_dirigees.values_list('pk', flat=True))

    # Fallback : rôle DIRECTEUR mais pas explicitement nommé directeur d'une direction
    # → on prend sa direction d'affectation.
    if not direct_ids and getattr(user, 'is_directeur', False) and employee.direction_id:
        direct_ids = {employee.direction_id}

    if not direct_ids:
        return Direction.objects.none()

    # Sous-directions récursives (BFS)
    all_ids = set(direct_ids)
    to_explore = list(direct_ids)
    while to_explore:
        children = list(
            Direction.objects.filter(parent_direction_id__in=to_explore)
            .exclude(pk__in=all_ids)
            .values_list('pk', flat=True)
        )
        all_ids.update(children)
        to_explore = children

    return Direction.objects.filter(pk__in=all_ids)


def get_directeur_employees(user):
    """Retourne le queryset des Employees de la direction du Directeur."""
    directions = get_directeur_directions(user)
    return (
        Employee.objects.filter(direction__in=directions, is_active=True)
        .select_related('user', 'bureau__agence__mutuelle', 'direction')
    )


# ----------------------------------------------------------------------------
# Périmètre du Chef d'agence
# ----------------------------------------------------------------------------

def get_chef_agence_agences(user):
    """Retourne les agences dont l'utilisateur est chef.

    Le rattachement se fait via son propre bureau d'affectation : le chef
    d'agence appartient à un bureau, ce bureau appartient à une agence, et
    il voit tous les employés des bureaux de cette agence.
    """
    try:
        employee = user.employee
    except Exception:
        return Agence.objects.none()
    if not employee.bureau_id or not employee.bureau.agence_id:
        return Agence.objects.none()
    return Agence.objects.filter(pk=employee.bureau.agence_id)


def get_chef_agence_employees(user):
    """Retourne les Employees des bureaux de l'agence du Chef d'agence."""
    agences = get_chef_agence_agences(user)
    if not agences.exists():
        return Employee.objects.none()
    return (
        Employee.objects.filter(bureau__agence__in=agences, is_active=True)
        .select_related('user', 'bureau__agence__mutuelle', 'direction')
    )


# ----------------------------------------------------------------------------
# Stats temps réel pour un ensemble d'employés
# ----------------------------------------------------------------------------

def compute_today_status(employees_qs):
    """Pour un queryset d'employés, calcule présents / en pause / partis / absents."""
    today = timezone.localdate()
    employee_ids = list(employees_qs.values_list('pk', flat=True))
    today_entries = TimeEntry.objects.filter(
        employee_id__in=employee_ids,
        work_date=today,
    ).select_related('employee__user', 'arrival_bureau')

    present = 0
    on_break = 0
    departed = 0
    arrived_ids = set()
    for e in today_entries:
        arrived_ids.add(e.employee_id)
        if e.departure_time:
            departed += 1
        elif e.is_on_break:
            on_break += 1
        else:
            present += 1

    total = len(employee_ids)
    absent = total - len(arrived_ids)
    rate = round(100 * len(arrived_ids) / total, 1) if total else 0

    return {
        'total': total,
        'present': present,
        'on_break': on_break,
        'departed': departed,
        'absent': absent,
        'attendance_rate': rate,
        'today_entries': today_entries,
        'arrived_ids': arrived_ids,
    }


def _fmt_hm(td: timedelta) -> str:
    """Formate un timedelta en 'XhYY' (heures et minutes)."""
    total_minutes = int(td.total_seconds() // 60)
    h, m = divmod(total_minutes, 60)
    return f"{h}h{m:02d}"


def compute_period_stats(employees_qs, start_date, end_date):
    """Heures cumulées + nb jours travaillés + taux de présence sur la période."""
    total = timedelta()
    days_count = 0
    entries = TimeEntry.objects.filter(
        employee__in=employees_qs,
        work_date__gte=start_date,
        work_date__lte=end_date,
    )
    for e in entries:
        d = e.worked_duration
        if d:
            total += d
            days_count += 1
    return {
        'total_hours': _fmt_hm(total),
        'total_hours_td': total,
        'days_count': days_count,
        'entries_count': entries.count(),
    }


def compute_hours_per_employee(employees_qs, start_date, end_date, limit=20):
    """Heures cumulées par employé sur la période — pour l'histogramme directeur.

    Retourne `minutes` (entier) — la source de vérité, cohérent avec les KPIs
    qui font `int(secondes // 60)`. Le front recalcule les heures décimales à
    partir des minutes pour la hauteur de barre.
    """
    rows = []
    entries_qs = TimeEntry.objects.filter(
        work_date__gte=start_date, work_date__lte=end_date,
    )
    for emp in employees_qs:
        total = timedelta()
        for e in entries_qs.filter(employee=emp):
            d = e.worked_duration
            if d:
                total += d
        minutes = int(total.total_seconds() // 60)
        rows.append({
            'label': emp.user.get_full_name() or emp.user.matricule,
            'minutes': minutes,
        })
    rows.sort(key=lambda r: r['minutes'], reverse=True)
    return rows[:limit]


# ----------------------------------------------------------------------------
# Anomalies — listes et filtres
# ----------------------------------------------------------------------------

def get_anomalies_for_user(user, only_pending=True):
    """Renvoie les anomalies visibles par l'utilisateur :
      - RH/DG : toutes
      - Directeur : celles de sa direction
      - Chef d'agence : celles des bureaux de son agence
      - Sinon : aucune
    """
    qs = (
        Anomaly.objects
        .select_related('time_entry__employee__user', 'time_entry__employee__direction',
                        'time_entry__arrival_bureau', 'acknowledged_by')
    )
    if user.has_global_access:
        pass  # RH/DG voient tout
    elif user.is_directeur:
        directions = get_directeur_directions(user)
        qs = qs.filter(time_entry__employee__direction__in=directions)
    elif user.is_chef_agence:
        agences = get_chef_agence_agences(user)
        qs = qs.filter(time_entry__employee__bureau__agence__in=agences)
    else:
        return Anomaly.objects.none()

    if only_pending:
        qs = qs.filter(is_acknowledged=False)
    return qs.order_by('-time_entry__work_date', '-severity')


# ----------------------------------------------------------------------------
# Stats RH/DG globales
# ----------------------------------------------------------------------------

def get_global_overview():
    """KPIs globaux pour le dashboard RH/DG."""
    today = timezone.localdate()
    month_start = today.replace(day=1)

    employees_qs = Employee.objects.filter(is_active=True)
    today_status = compute_today_status(employees_qs)

    month_entries = TimeEntry.objects.filter(work_date__gte=month_start, work_date__lte=today)
    total_hours = timedelta()
    for e in month_entries:
        d = e.worked_duration
        if d:
            total_hours += d

    total_minutes = int(total_hours.total_seconds() // 60)
    h, m = divmod(total_minutes, 60)
    total_hours_str = f"{h}h{m:02d}"

    return {
        'total_employees': employees_qs.count(),
        'present_today': today_status['present'],
        'on_break_today': today_status['on_break'],
        'departed_today': today_status['departed'],
        'absent_today': today_status['absent'],
        'attendance_rate_today': today_status['attendance_rate'],
        'total_hours_month': total_hours_str,
        'anomalies_month': Anomaly.objects.filter(
            time_entry__work_date__gte=month_start,
            time_entry__work_date__lte=today,
        ).count(),
        'anomalies_pending': Anomaly.objects.filter(is_acknowledged=False).count(),
    }


def get_breakdown_by_mutuelle():
    """Effectif par mutuelle."""
    qs = (
        Mutuelle.objects.filter(is_active=True)
        .annotate(nb_employees=Count('agences__bureaux__employees',
                                     filter=Q(agences__bureaux__employees__is_active=True),
                                     distinct=True))
        .order_by('-nb_employees')
    )
    return [{'label': m.name, 'count': m.nb_employees} for m in qs]


def get_breakdown_by_agence():
    """Effectif par agence."""
    qs = (
        Agence.objects.filter(is_active=True)
        .annotate(nb_employees=Count('bureaux__employees',
                                     filter=Q(bureaux__employees__is_active=True),
                                     distinct=True))
        .order_by('-nb_employees')
    )
    return [{'label': a.name, 'count': a.nb_employees} for a in qs]


def get_breakdown_by_direction():
    """Effectif par direction."""
    qs = (
        Direction.objects.filter(is_active=True)
        .annotate(nb_employees=Count('employees',
                                     filter=Q(employees__is_active=True),
                                     distinct=True))
        .order_by('-nb_employees')
    )
    return [{'label': d.name, 'count': d.nb_employees} for d in qs]


def get_anomaly_breakdown():
    """Répartition des anomalies du mois en cours par type."""
    today = timezone.localdate()
    qs = (
        Anomaly.objects.filter(time_entry__work_date__year=today.year,
                                time_entry__work_date__month=today.month)
        .values('anomaly_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    type_labels = dict(Anomaly.ANOMALY_TYPES)
    return [{'label': type_labels.get(r['anomaly_type'], r['anomaly_type']),
             'count': r['count'], 'type': r['anomaly_type']} for r in qs]


def get_presence_30_days():
    """Taux de présence (% d'employés ayant pointé) sur les 30 derniers jours."""
    today = timezone.localdate()
    total_employees = Employee.objects.filter(is_active=True).count() or 1
    data = []
    for offset in range(29, -1, -1):
        d = today - timedelta(days=offset)
        if d.weekday() >= 5:  # Sam/Dim : on n'inclut pas pour simplifier
            continue
        nb_arrived = TimeEntry.objects.filter(
            work_date=d, arrival_time__isnull=False,
        ).values('employee_id').distinct().count()
        rate = round(100 * nb_arrived / total_employees, 1)
        data.append({'date': d.strftime('%d/%m'), 'rate': rate})
    return data
