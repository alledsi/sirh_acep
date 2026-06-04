"""Context processors : expose les rôles dans tous les templates."""


def user_roles(request):
    """Ajoute aux templates : user_is_agent, user_is_directeur, user_is_rh, user_is_dg."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'user_is_agent': False,
            'user_is_directeur': False,
            'user_is_rh': False,
            'user_is_dg': False,
            'user_has_global_access': False,
        }
    return {
        'user_is_agent': user.is_agent,
        'user_is_directeur': user.is_directeur,
        'user_is_rh': user.is_rh,
        'user_is_dg': user.is_dg,
        'user_has_global_access': user.has_global_access,
    }
