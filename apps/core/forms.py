"""Formulaires : login avec matricule + création User côté admin."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class MatriculeLoginForm(AuthenticationForm):
    """Formulaire de login utilisant le matricule comme identifiant."""

    username = forms.CharField(
        label='Matricule',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ex : 1042',
            'autofocus': True,
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        }),
    )

    error_messages = {
        'invalid_login': 'Matricule ou mot de passe incorrect.',
        'inactive': 'Ce compte est désactivé. Contactez la RH.',
    }


class UserCreationAdminForm(UserCreationForm):
    """Formulaire de création d'un User dans l'admin Django (matricule = username)."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('matricule', 'email', 'first_name', 'last_name', 'roles')
