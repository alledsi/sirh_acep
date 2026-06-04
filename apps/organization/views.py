"""Vues CRUD du module Organisation.

Accessibles uniquement aux RH/DG (via GlobalAccessRequiredMixin).

Pour Bureau, le formulaire intègre un formset inline pour gérer les plages IP
(un bureau peut avoir plusieurs IPs : 192.168.1.0/24 + 192.168.2.0/24…).
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from apps.core.mixins import GlobalAccessRequiredMixin

from .forms import (
    AgenceForm, BureauForm, DirectionForm, IPBureauMappingFormSet,
    MutuelleForm,
)
from .models import Agence, Bureau, Direction, Mutuelle


# ============ Mutuelles ============

class MutuelleListView(GlobalAccessRequiredMixin, ListView):
    model = Mutuelle
    template_name = 'organization/mutuelle_list.html'
    context_object_name = 'mutuelles'
    paginate_by = 30

    def get_queryset(self):
        return Mutuelle.objects.annotate(nb_agences=Count('agences'))


class MutuelleCreateView(GlobalAccessRequiredMixin, CreateView):
    model = Mutuelle
    form_class = MutuelleForm
    template_name = 'organization/mutuelle_form.html'
    success_url = reverse_lazy('organization:mutuelle_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Mutuelle « {self.object.name} » créée.')
        return response


class MutuelleUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = Mutuelle
    form_class = MutuelleForm
    template_name = 'organization/mutuelle_form.html'
    success_url = reverse_lazy('organization:mutuelle_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Mutuelle « {self.object.name} » mise à jour.')
        return response


class MutuelleDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Mutuelle
    template_name = 'organization/confirm_delete.html'
    success_url = reverse_lazy('organization:mutuelle_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.success_url
        context['entity_label'] = 'la mutuelle'
        return context


# ============ Agences ============

class AgenceListView(GlobalAccessRequiredMixin, ListView):
    model = Agence
    template_name = 'organization/agence_list.html'
    context_object_name = 'agences'
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Agence.objects.select_related('mutuelle')
            .annotate(nb_bureaux=Count('bureaux'))
        )
        mutuelle_id = self.request.GET.get('mutuelle')
        if mutuelle_id:
            qs = qs.filter(mutuelle_id=mutuelle_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mutuelles'] = Mutuelle.objects.filter(is_active=True)
        context['selected_mutuelle'] = self.request.GET.get('mutuelle', '')
        return context


class AgenceCreateView(GlobalAccessRequiredMixin, CreateView):
    model = Agence
    form_class = AgenceForm
    template_name = 'organization/agence_form.html'
    success_url = reverse_lazy('organization:agence_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Agence « {self.object.name} » créée.')
        return response


class AgenceUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = Agence
    form_class = AgenceForm
    template_name = 'organization/agence_form.html'
    success_url = reverse_lazy('organization:agence_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Agence « {self.object.name} » mise à jour.')
        return response


class AgenceDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Agence
    template_name = 'organization/confirm_delete.html'
    success_url = reverse_lazy('organization:agence_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.success_url
        context['entity_label'] = "l'agence"
        return context


# ============ Bureaux (avec formset inline pour les plages IP) ============

class BureauListView(GlobalAccessRequiredMixin, ListView):
    model = Bureau
    template_name = 'organization/bureau_list.html'
    context_object_name = 'bureaux'
    paginate_by = 30

    def get_queryset(self):
        qs = (
            Bureau.objects
            .select_related('agence__mutuelle')
            .prefetch_related('ip_mappings')
        )
        mutuelle_id = self.request.GET.get('mutuelle')
        agence_id = self.request.GET.get('agence')
        if mutuelle_id:
            qs = qs.filter(agence__mutuelle_id=mutuelle_id)
        if agence_id:
            qs = qs.filter(agence_id=agence_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mutuelles'] = Mutuelle.objects.filter(is_active=True)
        context['agences'] = Agence.objects.filter(is_active=True).select_related('mutuelle')
        context['selected_mutuelle'] = self.request.GET.get('mutuelle', '')
        context['selected_agence'] = self.request.GET.get('agence', '')
        return context


class BureauDetailView(GlobalAccessRequiredMixin, DetailView):
    model = Bureau
    template_name = 'organization/bureau_detail.html'
    context_object_name = 'bureau'

    def get_queryset(self):
        return Bureau.objects.select_related('agence__mutuelle').prefetch_related('ip_mappings')


class BureauCreateView(GlobalAccessRequiredMixin, CreateView):
    model = Bureau
    form_class = BureauForm
    template_name = 'organization/bureau_form.html'
    success_url = reverse_lazy('organization:bureau_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('ip_formset', IPBureauMappingFormSet(prefix='ips'))
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        ip_formset = IPBureauMappingFormSet(request.POST, prefix='ips')
        if form.is_valid() and ip_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                ip_formset.instance = self.object
                ip_formset.save()
            messages.success(request, f'Bureau « {self.object.name} » créé.')
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form, ip_formset=ip_formset))


class BureauUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = Bureau
    form_class = BureauForm
    template_name = 'organization/bureau_form.html'
    success_url = reverse_lazy('organization:bureau_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('ip_formset', IPBureauMappingFormSet(instance=self.object, prefix='ips'))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        ip_formset = IPBureauMappingFormSet(request.POST, instance=self.object, prefix='ips')
        if form.is_valid() and ip_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                ip_formset.save()
            messages.success(request, f'Bureau « {self.object.name} » mis à jour.')
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form, ip_formset=ip_formset))


class BureauDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Bureau
    template_name = 'organization/confirm_delete.html'
    success_url = reverse_lazy('organization:bureau_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.success_url
        context['entity_label'] = 'le bureau'
        return context


# ============ Directions ============

class DirectionListView(GlobalAccessRequiredMixin, ListView):
    model = Direction
    template_name = 'organization/direction_list.html'
    context_object_name = 'directions'
    paginate_by = 30

    def get_queryset(self):
        return Direction.objects.select_related('parent_direction')


class DirectionCreateView(GlobalAccessRequiredMixin, CreateView):
    model = Direction
    form_class = DirectionForm
    template_name = 'organization/direction_form.html'
    success_url = reverse_lazy('organization:direction_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Direction « {self.object.name} » créée.')
        return response


class DirectionUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = Direction
    form_class = DirectionForm
    template_name = 'organization/direction_form.html'
    success_url = reverse_lazy('organization:direction_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Direction « {self.object.name} » mise à jour.')
        return response


class DirectionDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = Direction
    template_name = 'organization/confirm_delete.html'
    success_url = reverse_lazy('organization:direction_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.success_url
        context['entity_label'] = 'la direction'
        return context


# Le modèle Position a été supprimé : le poste est désormais un simple
# champ texte (CharField) sur le modèle Employee. Voir apps/employees/models.py.
