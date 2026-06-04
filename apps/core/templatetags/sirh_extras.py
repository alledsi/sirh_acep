"""Filtres et tags personnalisés pour les templates."""
from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Permet d'accéder à un élément d'un dict par clé : {{ my_dict|get_item:key }}."""
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def hm(value):
    """Formate un timedelta en 'XhYY' (cohérent avec les KPIs : troncature des
    secondes). Si la durée est < 1h, affiche 'X min'. None/0 → '—'.

    Usage : {{ today_entry.break_duration|hm }}
    """
    if value in (None, ''):
        return '—'
    if not isinstance(value, timedelta):
        return value
    total_minutes = int(value.total_seconds() // 60)
    if total_minutes <= 0:
        return '0 min'
    h, m = divmod(total_minutes, 60)
    if h == 0:
        return f'{m} min'
    return f'{h}h{m:02d}'
