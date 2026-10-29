"""Context processors : expose les rôles et le message diffusé dans tous les templates."""


def broadcast_message(request):
    """Expose le message diffusé courant si non vu dans cette session."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'broadcast_message': None}
    try:
        from .models import BroadcastMessage
        msg = BroadcastMessage.get_active()
    except Exception:
        return {'broadcast_message': None}
    if not msg:
        return {'broadcast_message': None}
    # Vérifier si déjà vu dans cette session
    seen_ids = request.session.get('seen_broadcast_ids', [])
    if msg.pk in seen_ids:
        return {'broadcast_message': None}
    return {'broadcast_message': msg}


def user_roles(request):
    """Ajoute aux templates : user_is_agent, user_is_chef_agence, user_is_directeur, user_is_rh, user_is_dg."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'user_is_agent': False,
            'user_is_chef_agence': False,
            'user_is_directeur': False,
            'user_is_rh': False,
            'user_is_dg': False,
            'user_has_global_access': False,
        }
    return {
        'user_is_agent': user.is_agent,
        'user_is_chef_agence': user.is_chef_agence,
        'user_is_directeur': user.is_directeur,
        'user_is_rh': user.is_rh,
        'user_is_dg': user.is_dg,
        'user_has_global_access': user.has_global_access,
    }
