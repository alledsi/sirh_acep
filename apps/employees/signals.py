"""Signaux du module Employees.

À chaque connexion réussie, on pose un flag de session pour déclencher
l'affichage du modal d'anniversaire (s'il y a des anniversaires aujourd'hui)
au premier rendu de page après login.
"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def trigger_birthday_modal(sender, request, user, **kwargs):
    """Active l'affichage du modal d'anniversaire à la prochaine page rendue."""
    if request is not None:
        request.session['birthday_modal_pending'] = True
