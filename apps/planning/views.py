"""Vues du module Planning (réservées RH/DG)."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.generic import View

from apps.core.mixins import GlobalAccessRequiredMixin

from .forms import DailyScheduleFormSet, PlanningForm
from .services import get_active_planning


class PlanningEditView(GlobalAccessRequiredMixin, View):
    """Édition du Planning unique d'ACEP."""
    template_name = 'planning/planning_edit.html'

    def get(self, request):
        planning = get_active_planning()
        form = PlanningForm(instance=planning)
        formset = DailyScheduleFormSet(instance=planning, prefix='days')
        return self._render(request, planning, form, formset)

    def post(self, request):
        planning = get_active_planning()
        form = PlanningForm(request.POST, instance=planning)
        formset = DailyScheduleFormSet(request.POST, instance=planning, prefix='days')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'Planning mis à jour.')
            return redirect('planning:edit')
        return self._render(request, planning, form, formset)

    def _render(self, request, planning, form, formset):
        from apps.employees.models import Employee as Emp
        total_employees = Emp.objects.filter(is_active=True).count()
        return render(request, self.template_name, {
            'planning': planning,
            'form': form,
            'formset': formset,
            'total_employees': total_employees,
            'last_update_at': planning.updated_at,
        })
