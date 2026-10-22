"""Middlewares applicatifs ACEP."""
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class RequireEmailMiddleware:
    """Force tout utilisateur connecté sans email à saisir son email.

    Si `user.email` est vide, chaque requête est redirigée vers la page
    « Email obligatoire » (sauf pour les URL exemptées : login/logout,
    la page email elle-même, les fichiers statiques, l'admin Django).
    """

    EXEMPT_PATH_PREFIXES = (
        '/static/',
        '/media/',
        '/admin/',          # super-utilisateur peut gérer sans email
    )

    def __init__(self, get_response):
        self.get_response = get_response
        # Résolution différée des URL nommées (au premier appel)
        self._exempt_names = {'core:login', 'core:logout', 'employees:email_required'}

    def _resolved_exempt_urls(self):
        urls = []
        for name in self._exempt_names:
            try:
                urls.append(reverse(name))
            except NoReverseMatch:
                pass
        return urls

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not (user.email or '').strip():
            path = request.path_info or '/'
            exempt = (
                any(path.startswith(p) for p in self.EXEMPT_PATH_PREFIXES)
                or path in self._resolved_exempt_urls()
            )
            if not exempt:
                return redirect('employees:email_required')
        return self.get_response(request)
