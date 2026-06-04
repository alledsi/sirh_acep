"""Vues du module Reporting — Sprint 5."""
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import View

from apps.attendance.models import Anomaly
from apps.core.mixins import GlobalAccessRequiredMixin
from apps.employees.models import Employee

from .forms import AnomalyValidateForm
from .services import (
    compute_hours_per_employee, compute_period_stats, compute_today_status,
    get_anomalies_for_user, get_anomaly_breakdown, get_breakdown_by_agence,
    get_breakdown_by_direction, get_directeur_directions, get_directeur_employees,
    get_global_overview, get_presence_30_days,
)


class DirecteurRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Accès réservé aux Directeurs (ou RH/DG, qui peuvent aussi voir)."""

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_directeur or u.has_global_access)


# ============ Directeur — Tableau de bord ============

class DirecteurDashboardView(DirecteurRequiredMixin, View):
    template_name = 'reporting/directeur_dashboard.html'

    def get(self, request):
        directions = get_directeur_directions(request.user)
        if not directions.exists():
            messages.warning(
                request,
                "Aucune direction ne vous est rattachée. Vérifiez votre fiche employé "
                "(champ Direction) ou demandez à la RH de vous désigner directeur d'une direction."
            )
            return redirect('core:home')

        employees = get_directeur_employees(request.user)
        today_status = compute_today_status(employees)

        # Anomalies en attente
        anomalies_pending = get_anomalies_for_user(request.user, only_pending=True)[:10]
        anomalies_pending_count = get_anomalies_for_user(request.user, only_pending=True).count()

        # Stats des 30 derniers jours
        today = timezone.localdate()
        d30 = today - timedelta(days=30)
        period_stats = compute_period_stats(employees, d30, today)

        # Histogramme : heures par employé sur le mois en cours
        import json
        month_start = today.replace(day=1)
        hours_per_employee = compute_hours_per_employee(employees, month_start, today)

        return render(request, self.template_name, {
            'directions': directions,
            'employees': employees,
            'today_status': today_status,
            'today_entries_by_employee': {e.employee_id: e for e in today_status['today_entries']},
            'anomalies_pending': anomalies_pending,
            'anomalies_pending_count': anomalies_pending_count,
            'period_stats': period_stats,
            'hours_per_employee_data': json.dumps(hours_per_employee),
            'hours_per_employee_count': len(hours_per_employee),
        })


class DirecteurEquipeView(DirecteurRequiredMixin, View):
    template_name = 'reporting/directeur_equipe.html'

    def get(self, request):
        employees = get_directeur_employees(request.user)
        today = timezone.localdate()
        month_start = today.replace(day=1)

        # Stats par employé (mois en cours)
        from apps.attendance.models import TimeEntry
        employee_stats = []
        for emp in employees:
            entries = TimeEntry.objects.filter(
                employee=emp, work_date__gte=month_start, work_date__lte=today,
            )
            hours = timedelta()
            days = 0
            retards = 0
            anomalies = 0
            for e in entries:
                d = e.worked_duration
                if d:
                    hours += d
                    days += 1
                for a in e.anomalies.all():
                    anomalies += 1
                    if a.anomaly_type == Anomaly.TYPE_LATE:
                        retards += 1
            total_min = int(hours.total_seconds() // 60)
            h, m = divmod(total_min, 60)
            employee_stats.append({
                'employee': emp,
                'hours': f"{h}h{m:02d}",
                'days': days,
                'retards': retards,
                'anomalies': anomalies,
            })

        return render(request, self.template_name, {
            'employee_stats': employee_stats,
            'directions': get_directeur_directions(request.user),
        })


class DirecteurAnomaliesView(DirecteurRequiredMixin, View):
    template_name = 'reporting/anomaly_list.html'

    def get(self, request):
        only_pending = request.GET.get('statut', 'pending') == 'pending'
        anomalies = get_anomalies_for_user(request.user, only_pending=only_pending)
        return render(request, self.template_name, {
            'anomalies': anomalies,
            'only_pending': only_pending,
            'scope_label': 'ma direction' if request.user.is_directeur and not request.user.has_global_access else 'toutes les directions',
        })


class AnomalyValidateView(DirecteurRequiredMixin, View):
    template_name = 'reporting/anomaly_validate.html'

    def _get_anomaly(self, request, pk):
        anomaly = get_object_or_404(Anomaly, pk=pk)
        # Vérifier que l'utilisateur a le droit
        allowed_ids = list(get_anomalies_for_user(request.user, only_pending=False).values_list('pk', flat=True))
        if anomaly.pk not in allowed_ids:
            raise Http404("Anomalie non visible pour vous.")
        return anomaly

    def get(self, request, pk):
        anomaly = self._get_anomaly(request, pk)
        form = AnomalyValidateForm()
        return render(request, self.template_name, {'anomaly': anomaly, 'form': form})

    def post(self, request, pk):
        anomaly = self._get_anomaly(request, pk)
        form = AnomalyValidateForm(request.POST)
        if form.is_valid():
            anomaly.is_acknowledged = True
            anomaly.acknowledged_by = request.user
            anomaly.acknowledged_at = timezone.now()
            anomaly.acknowledgement_note = form.cleaned_data['note']
            anomaly.save()
            messages.success(request, "Anomalie validée.")
            # Redirige vers la liste d'anomalies appropriée
            if request.user.is_directeur and not request.user.has_global_access:
                return redirect('reporting:directeur_anomalies')
            return redirect('reporting:anomaly_list')
        return render(request, self.template_name, {'anomaly': anomaly, 'form': form})


# ============ RH/DG — Statistiques globales ============

class RHStatsView(GlobalAccessRequiredMixin, View):
    template_name = 'reporting/rh_stats.html'

    def get(self, request):
        overview = get_global_overview()
        return render(request, self.template_name, {
            'overview': overview,
            'breakdown_agence': json.dumps(get_breakdown_by_agence()),
            'breakdown_direction': json.dumps(get_breakdown_by_direction()),
            'anomaly_breakdown': json.dumps(get_anomaly_breakdown()),
            'presence_30': json.dumps(get_presence_30_days()),
        })


class AnomalyListView(GlobalAccessRequiredMixin, View):
    """Liste des anomalies pour la RH/DG (toutes les anomalies)."""
    template_name = 'reporting/anomaly_list.html'

    def get(self, request):
        only_pending = request.GET.get('statut', 'pending') == 'pending'
        anomalies = get_anomalies_for_user(request.user, only_pending=only_pending)
        return render(request, self.template_name, {
            'anomalies': anomalies,
            'only_pending': only_pending,
            'scope_label': 'toutes les directions',
        })
