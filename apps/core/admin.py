"""Admin Django pour le module Core (utilisateurs)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .forms import UserCreationAdminForm
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = UserCreationAdminForm
    list_display = ('matricule', 'first_name', 'last_name', 'email', 'roles_display', 'is_active')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('matricule', 'first_name', 'last_name', 'email')
    ordering = ('matricule',)

    fieldsets = (
        (None, {'fields': ('matricule', 'password')}),
        (_('Informations personnelles'), {
            'fields': ('first_name', 'last_name', 'email', 'phone'),
        }),
        (_('Rôles ACEP'), {
            'fields': ('roles', 'must_change_password'),
            'description': 'Sélectionnez un ou plusieurs rôles (cumulables) : AGENT, DIRECTEUR, RH, DG.',
        }),
        (_('Permissions Django'), {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Dates importantes'), {
            'classes': ('collapse',),
            'fields': ('last_login', 'date_joined'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'matricule', 'email', 'first_name', 'last_name',
                'password1', 'password2', 'roles',
            ),
        }),
    )

    @admin.display(description='Rôles')
    def roles_display(self, obj):
        return ', '.join(obj.roles) if obj.roles else '—'
