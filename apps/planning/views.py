"""Vues du module Planning (réservées RH/DG)."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from apps.core.mixins import GlobalAccessRequiredMixin

from .forms import DailyScheduleFormSet, HolidayForm, PlanningForm
from .models import Holiday
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
        from django.utils import timezone
        today = timezone.localdate()
        upcoming_holidays = Holiday.objects.filter(date__gte=today, is_active=True).order_by('date')[:5]
        return render(request, self.template_name, {
            'planning': planning,
            'form': form,
            'formset': formset,
            'total_employees': total_employees,
            'last_update_at': planning.updated_at,
            'upcoming_holidays': upcoming_holidays,
        })


# ============ Jours fériés ============

class HolidayListView(GlobalAccessRequiredMixin, ListView):
    model = Holiday
    template_name = 'planning/holiday_list.html'
    context_object_name = 'holidays'
    paginate_by = 50

    def get_queryset(self):
        return Holiday.objects.all().order_by('-date')


class HolidayCreateView(GlobalAccessRequiredMixin, CreateView):
    model = Holiday
    form_class = HolidayForm
    template_name = 'planning/holiday_form.html'
    success_url = reverse_lazy('planning:holiday_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Jour férié « {self.object.name} » créé.')
        return response


class HolidayUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = Holiday
    form_class = HolidayForm
    template_name = 'planning/holiday_form.html'
    success_url = reverse_lazy('planning:holiday_list')


class HolidayDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Holiday
    template_name = 'planning/holiday_confirm_delete.html'
    success_url = reverse_lazy('planning:holiday_list')
