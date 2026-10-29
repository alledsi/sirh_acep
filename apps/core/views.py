"""Vues d'authentification + accueil + changement de mot de passe + messages diffusés."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import MatriculeLoginForm
from .mixins import GlobalAccessRequiredMixin
from .models import BroadcastMessage


class LoginPageView(LoginView):
    template_name = 'core/login.html'
    authentication_form = MatriculeLoginForm
    redirect_authenticated_user = True


class LogoutPageView(LogoutView):
    next_page = reverse_lazy('core:login')


class PasswordChangePageView(PasswordChangeView):
    """Changement de mot de passe accessible depuis le profil."""
    template_name = 'core/password_change.html'
    success_url = reverse_lazy('core:password_change_done')


@login_required
def password_change_done(request):
    messages.success(request, 'Votre mot de passe a été mis à jour avec succès.')
    return render(request, 'core/password_change_done.html')


# ============ Messages diffusés (RH/DG) ============

class BroadcastListView(GlobalAccessRequiredMixin, ListView):
    model = BroadcastMessage
    template_name = 'core/broadcast_list.html'
    context_object_name = 'messages_list'
    paginate_by = 30


class BroadcastCreateView(GlobalAccessRequiredMixin, CreateView):
    model = BroadcastMessage
    fields = ['title', 'body', 'level', 'is_active']
    template_name = 'core/broadcast_form.html'
    success_url = reverse_lazy('core:broadcast_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        if form.instance.is_active:
            messages.success(self.request, f"Message « {form.instance.title} » créé et diffusé.")
        else:
            messages.success(self.request, f"Message « {form.instance.title} » créé (non diffusé).")
        return response


class BroadcastUpdateView(GlobalAccessRequiredMixin, UpdateView):
    model = BroadcastMessage
    fields = ['title', 'body', 'level', 'is_active']
    template_name = 'core/broadcast_form.html'
    success_url = reverse_lazy('core:broadcast_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Message « {form.instance.title} » mis à jour.")
        return response


class BroadcastDeleteView(GlobalAccessRequiredMixin, DeleteView):
    model = BroadcastMessage
    template_name = 'core/broadcast_confirm_delete.html'
    success_url = reverse_lazy('core:broadcast_list')

    def form_valid(self, form):
        title = self.object.title
        response = super().form_valid(form)
        messages.warning(self.request, f"Message « {title} » supprimé.")
        return response


class BroadcastToggleView(GlobalAccessRequiredMixin, View):
    """Active / désactive un message. Un seul actif à la fois (géré par le modèle)."""

    def post(self, request, pk):
        msg = get_object_or_404(BroadcastMessage, pk=pk)
        msg.is_active = not msg.is_active
        msg.save()
        if msg.is_active:
            messages.success(request, f"Message « {msg.title} » diffusé à tous les utilisateurs.")
        else:
            messages.info(request, f"Diffusion du message « {msg.title} » arrêtée.")
        return redirect('core:broadcast_list')


@login_required
@require_POST
def broadcast_ack(request):
    """Marque le message courant comme vu dans la session (modal fermé)."""
    msg_id = request.POST.get('message_id')
    if msg_id and msg_id.isdigit():
        seen = request.session.get('seen_broadcast_ids', [])
        if int(msg_id) not in seen:
            seen.append(int(msg_id))
            request.session['seen_broadcast_ids'] = seen
    return HttpResponse(status=204)


@login_required
def home(request):
    """Page d'accueil après connexion.

    - Si l'utilisateur a le rôle AGENT **et** une fiche Employee : on
      l'envoie sur son tableau de bord de pointage.
    - Sinon (RH/DG seul, ou superuser fraîchement créé sans fiche employé) :
      on affiche le récapitulatif global de l'organisation.
    """
    from django.shortcuts import redirect

    from apps.employees.models import Employee
    has_employee = Employee.objects.filter(user=request.user).exists()
    if request.user.is_agent and has_employee:
        return redirect('attendance:dashboard')

    context = {'has_employee': has_employee}
    if request.user.has_global_access:
        from apps.organization.models import Agence, Bureau, Direction, Mutuelle
        context.update({
            'stats': {
                'employees': Employee.objects.filter(is_active=True).count(),
                'mutuelles': Mutuelle.objects.filter(is_active=True).count(),
                'agences': Agence.objects.filter(is_active=True).count(),
                'bureaux': Bureau.objects.filter(is_active=True).count(),
                'directions': Direction.objects.filter(is_active=True).count(),
            },
        })
    return render(request, 'core/home.html', context)
