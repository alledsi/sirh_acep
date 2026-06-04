"""Vues CRUD du module Employees (réservées RH/DG) + vue Mon profil."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q as models_q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View,
)

from apps.core.mixins import GlobalAccessRequiredMixin
from apps.organization.models import Agence, Bureau, Direction, Mutuelle

from .forms import (
    EmployeeCreateForm, EmployeeDocumentForm, EmployeeUpdateForm,
)
from .models import Employee, EmployeeDocument


# ============ Liste + détail ============

class EmployeeListView(GlobalAccessRequiredMixin, ListView):
    model = Employee
    template_name = 'employees/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Employee.objects
            .select_related('user', 'bureau__agence__mutuelle', 'direction', 'manager__user')
        )
        q = self.request.GET.get('q', '').strip()
        mutuelle = self.request.GET.get('mutuelle')
        agence = self.request.GET.get('agence')
        bureau = self.request.GET.get('bureau')
        direction = self.request.GET.get('direction')
        role = self.request.GET.get('role')
        statut = self.request.GET.get('statut', 'all')

        if q:
            qs = qs.filter(
                models_q(user__matricule__icontains=q) |
                models_q(user__first_name__icontains=q) |
                models_q(user__last_name__icontains=q) |
                models_q(user__email__icontains=q) |
                models_q(position__icontains=q)
            )
        if mutuelle:
            qs = qs.filter(bureau__agence__mutuelle_id=mutuelle)
        if agence:
            qs = qs.filter(bureau__agence_id=agence)
        if bureau:
            qs = qs.filter(bureau_id=bureau)
        if direction:
            qs = qs.filter(direction_id=direction)
        if role:
            qs = qs.filter(user__roles__contains=[role])
        if statut == 'active':
            qs = qs.filter(is_active=True)
        elif statut == 'inactive':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['mutuelles'] = Mutuelle.objects.filter(is_active=True)
        ctx['agences'] = Agence.objects.filter(is_active=True).select_related('mutuelle')
        ctx['bureaux'] = Bureau.objects.filter(is_active=True).select_related('agence')
        ctx['directions'] = Direction.objects.filter(is_active=True)
        ctx['filters'] = {
            'q': self.request.GET.get('q', ''),
            'mutuelle': self.request.GET.get('mutuelle', ''),
            'agence': self.request.GET.get('agence', ''),
            'bureau': self.request.GET.get('bureau', ''),
            'direction': self.request.GET.get('direction', ''),
            'role': self.request.GET.get('role', ''),
            'statut': self.request.GET.get('statut', 'all'),
        }
        from apps.core.models import User
        ctx['role_choices'] = User.ROLE_CHOICES
        return ctx


class EmployeeDetailView(GlobalAccessRequiredMixin, DetailView):
    model = Employee
    template_name = 'employees/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return Employee.objects.select_related(
            'user', 'bureau__agence__mutuelle', 'direction', 'manager__user'
        ).prefetch_related('contracts', 'documents', 'reports__user')


# ============ Création ============

class EmployeeCreateView(GlobalAccessRequiredMixin, FormView):
    template_name = 'employees/employee_form.html'
    form_class = EmployeeCreateForm
    success_url = reverse_lazy('employees:employee_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['mode'] = 'create'
        ctx['position_suggestions'] = (
            Employee.objects.exclude(position='').values_list('position', flat=True).distinct().order_by('position')
        )
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            employee = form.save()
        messages.success(
            self.request,
            f"Employé créé : {employee.user.matricule} — {employee.user.get_full_name()}."
        )
        return redirect('employees:employee_detail', pk=employee.pk)


# ============ Édition ============

class EmployeeUpdateView(GlobalAccessRequiredMixin, FormView):
    template_name = 'employees/employee_form.html'
    form_class = EmployeeUpdateForm

    def get_employee(self):
        return get_object_or_404(Employee, pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee'] = self.get_employee()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['mode'] = 'update'
        ctx['employee'] = self.get_employee()
        ctx['object'] = ctx['employee']
        ctx['position_suggestions'] = (
            Employee.objects.exclude(position='').values_list('position', flat=True).distinct().order_by('position')
        )
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            employee = form.save()
        messages.success(self.request, f"Employé {employee.user.matricule} mis à jour.")
        return redirect('employees:employee_detail', pk=employee.pk)


# ============ Suppression ============

class EmployeeDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Employee
    template_name = 'employees/employee_confirm_delete.html'
    success_url = reverse_lazy('employees:employee_list')

    def form_valid(self, form):
        emp = self.get_object()
        # Soft delete plutôt que suppression physique
        emp.is_active = False
        emp.is_deleted = True
        emp.user.is_active = False
        emp.user.save()
        emp.save()
        messages.warning(self.request, f"Employé {emp.user.matricule} désactivé.")
        return redirect(self.success_url)


# ============ Mon profil (vue agent personnelle) ============

class MyProfileView(LoginRequiredMixin, View):
    """Vue de profil pour l'utilisateur connecté lui-même.

    Affiche : identité, affectation, planning, statistiques annuelles,
    et section de sécurité (changement de mot de passe).
    """
    template_name = 'employees/my_profile.html'

    def get(self, request):
        try:
            employee = request.user.employee
        except Employee.DoesNotExist:
            messages.warning(request, "Votre compte n'est pas rattaché à une fiche employé.")
            return redirect('core:home')

        from datetime import date, timedelta
        from apps.attendance.models import TimeEntry
        from apps.planning.services import get_active_planning
        import json

        planning = get_active_planning()
        daily_schedules = list(planning.schedules.order_by('day_of_week'))

        # Statistiques annuelles (heures par mois)
        # minutes = source de vérité (entier, cohérent avec les KPIs).
        today = date.today()
        year_chart = []
        for month in range(1, today.month + 1):
            entries = TimeEntry.objects.filter(
                employee=employee, work_date__year=today.year, work_date__month=month,
            )
            hours = timedelta()
            for e in entries:
                d = e.worked_duration
                if d:
                    hours += d
            year_chart.append({
                'label': ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
                          'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'][month - 1],
                'minutes': int(hours.total_seconds() // 60),
            })

        return render(request, self.template_name, {
            'employee': employee,
            'planning': planning,
            'daily_schedules': daily_schedules,
            'year_chart_data': json.dumps(year_chart),
        })


