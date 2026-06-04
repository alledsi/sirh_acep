"""Vues d'authentification + accueil + changement de mot de passe."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.shortcuts import render
from django.urls import reverse_lazy

from .forms import MatriculeLoginForm


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
