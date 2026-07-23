"""Mixins de contrôle d'accès basés sur les rôles ACEP."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class GlobalAccessRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve la vue aux utilisateurs avec visibilité globale (RH ou DG).

    Utilisé pour les écrans d'administration : gestion des employés,
    de l'organisation, des plannings, etc.
    """

    raise_exception = False

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.has_global_access


class RHRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve la vue aux utilisateurs ayant le rôle RH."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_rh


class DirecteurRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve la vue aux utilisateurs ayant le rôle Directeur."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_directeur


class ChefAgenceRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réserve la vue aux Chefs d'agence (RH/DG y ont aussi accès)."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_chef_agence or user.has_global_access)
