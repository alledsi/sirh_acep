"""Context processors du module Employees.

`todays_birthdays` n'expose les anniversaires du jour que **juste après la
connexion** (flag de session posé par le signal `user_logged_in`).
Le flag est consommé au premier rendu, donc le modal s'affiche une seule
fois par session de connexion (et apparaît à nouveau au prochain login).
"""
from django.utils import timezone


def todays_birthdays(request):
    """Renvoie la liste des employés actifs dont c'est l'anniversaire aujourd'hui.

    Uniquement disponible au premier rendu de page suivant une connexion réussie
    (le signal `user_logged_in` pose `birthday_modal_pending=True` dans la session).
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'todays_birthdays': []}

    # On consomme le flag : pop = True puis le supprime de la session
    show_modal = request.session.pop('birthday_modal_pending', False)
    if not show_modal:
        return {'todays_birthdays': []}

    try:
        from .models import Employee
        today = timezone.localdate()
        birthdays = (
            Employee.objects
            .filter(is_active=True, birth_date__month=today.month, birth_date__day=today.day)
            .select_related('user', 'bureau__agence', 'direction')
        )
        return {'todays_birthdays': list(birthdays)}
    except Exception:
        return {'todays_birthdays': []}
