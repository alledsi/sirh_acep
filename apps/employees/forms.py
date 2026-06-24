"""Formulaires du module Employees.

Pour la création, le formulaire crée à la fois le User (matricule = identifiant
de connexion) et l'Employee dans une seule opération atomique.
"""
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.core.models import User
from apps.organization.models import Bureau, Direction

from .models import Employee, EmployeeDocument


_TEXT = {'class': 'form-control'}
_SELECT = {'class': 'form-select'}
_CHECK = {'class': 'form-check-input'}
_DATE = {'class': 'form-control', 'type': 'date'}


def _date_widget():
    """Widget date HTML5 — format ISO obligatoire pour <input type='date'>."""
    return forms.DateInput(attrs=_DATE, format='%Y-%m-%d')


# ============ Création d'un employé (User + Employee en une fois) ============

class EmployeeCreateForm(forms.Form):
    """Crée un User + un Employee. Utilisé uniquement par la RH/DG."""

    # --- Champs User ---
    matricule = forms.CharField(
        label='Matricule', max_length=20,
        widget=forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : 1042'}),
        help_text='Identifiant de connexion de l\'employé. Doit être unique.',
    )
    first_name = forms.CharField(label='Prénom', max_length=150, widget=forms.TextInput(attrs=_TEXT))
    last_name = forms.CharField(label='Nom', max_length=150, widget=forms.TextInput(attrs=_TEXT))
    email = forms.EmailField(label='Email', required=False, widget=forms.EmailInput(attrs=_TEXT))
    phone = forms.CharField(label='Téléphone', max_length=30, required=False, widget=forms.TextInput(attrs=_TEXT))
    roles = forms.MultipleChoiceField(
        label='Rôles',
        choices=User.ROLE_CHOICES,
        initial=[User.ROLE_AGENT],
        widget=forms.CheckboxSelectMultiple(attrs=_CHECK),
        help_text='Cumulables. AGENT est requis pour pouvoir pointer.',
    )
    password = forms.CharField(
        label='Mot de passe initial',
        widget=forms.PasswordInput(attrs={**_TEXT, 'placeholder': 'Min. 8 caractères'}),
        min_length=8,
    )
    must_change_password = forms.BooleanField(
        label='Forcer le changement à la 1ère connexion',
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs=_CHECK),
    )

    # --- Champs Employee (la photo s'ajoute via l'édition après création) ---
    birth_date = forms.DateField(
        label='Date de naissance', required=False,
        widget=_date_widget(), input_formats=['%Y-%m-%d'],
    )
    hire_date = forms.DateField(
        label="Date d'embauche",
        widget=_date_widget(), input_formats=['%Y-%m-%d'],
    )
    bureau = forms.ModelChoiceField(
        label="Bureau d'affectation",
        queryset=Bureau.objects.filter(is_active=True).select_related('agence__mutuelle'),
        widget=forms.Select(attrs=_SELECT),
    )
    direction = forms.ModelChoiceField(
        label='Direction',
        queryset=Direction.objects.filter(is_active=True),
        widget=forms.Select(attrs=_SELECT),
    )
    position = forms.CharField(
        label='Poste / Fonction', max_length=200,
        widget=forms.TextInput(attrs={
            **_TEXT,
            'placeholder': 'Ex : Caissier, Chargé clientèle, Directeur d\'agence...',
            'list': 'position-suggestions',
        }),
    )

    # ---------- Validation ----------
    def clean_matricule(self):
        matricule = self.cleaned_data['matricule'].strip()
        if User.objects.filter(matricule=matricule).exists():
            raise ValidationError(f"Le matricule '{matricule}' est déjà utilisé.")
        return matricule

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def save(self):
        """Crée le User puis l'Employee dans la même transaction (appelée par la vue)."""
        data = self.cleaned_data
        user = User.objects.create_user(
            matricule=data['matricule'],
            email=data.get('email') or None,
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        user.phone = data.get('phone') or ''
        user.roles = list(data['roles'])
        user.must_change_password = data.get('must_change_password', False)
        user.save()

        employee = Employee.objects.create(
            user=user,
            birth_date=data.get('birth_date'),
            hire_date=data['hire_date'],
            bureau=data['bureau'],
            direction=data['direction'],
            position=data['position'],
        )
        return employee


# ============ Édition d'un employé ============

class EmployeeUpdateForm(forms.Form):
    """Modifie le User + l'Employee existants (matricule en lecture seule)."""

    # --- Champs User (matricule read-only) ---
    matricule_display = forms.CharField(
        label='Matricule', required=False, disabled=True,
        widget=forms.TextInput(attrs={**_TEXT, 'readonly': 'readonly'}),
    )
    first_name = forms.CharField(label='Prénom', max_length=150, widget=forms.TextInput(attrs=_TEXT))
    last_name = forms.CharField(label='Nom', max_length=150, widget=forms.TextInput(attrs=_TEXT))
    email = forms.EmailField(label='Email', required=False, widget=forms.EmailInput(attrs=_TEXT))
    phone = forms.CharField(label='Téléphone', max_length=30, required=False, widget=forms.TextInput(attrs=_TEXT))
    roles = forms.MultipleChoiceField(
        label='Rôles',
        choices=User.ROLE_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs=_CHECK),
    )
    is_user_active = forms.BooleanField(
        label='Compte actif (autorise la connexion)',
        required=False,
        widget=forms.CheckboxInput(attrs=_CHECK),
    )

    # --- Champs Employee ---
    birth_date = forms.DateField(
        label='Date de naissance', required=False,
        widget=_date_widget(), input_formats=['%Y-%m-%d'],
    )
    hire_date = forms.DateField(
        label="Date d'embauche",
        widget=_date_widget(), input_formats=['%Y-%m-%d'],
    )
    bureau = forms.ModelChoiceField(
        label="Bureau d'affectation",
        queryset=Bureau.objects.filter(is_active=True).select_related('agence__mutuelle'),
        widget=forms.Select(attrs=_SELECT),
    )
    direction = forms.ModelChoiceField(
        label='Direction',
        queryset=Direction.objects.filter(is_active=True),
        widget=forms.Select(attrs=_SELECT),
    )
    position = forms.CharField(
        label='Poste / Fonction', max_length=200,
        widget=forms.TextInput(attrs={**_TEXT, 'list': 'position-suggestions'}),
    )
    is_active = forms.BooleanField(
        label="Employé actif (présent dans l'organisation)",
        required=False,
        widget=forms.CheckboxInput(attrs=_CHECK),
    )

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.employee = employee
        if employee:
            self.fields['matricule_display'].initial = employee.user.matricule
            self.fields['first_name'].initial = employee.user.first_name
            self.fields['last_name'].initial = employee.user.last_name
            self.fields['email'].initial = employee.user.email
            self.fields['phone'].initial = employee.user.phone
            self.fields['roles'].initial = employee.user.roles or []
            self.fields['is_user_active'].initial = employee.user.is_active
            self.fields['birth_date'].initial = employee.birth_date
            self.fields['hire_date'].initial = employee.hire_date
            self.fields['bureau'].initial = employee.bureau_id
            self.fields['direction'].initial = employee.direction_id
            self.fields['position'].initial = employee.position
            self.fields['is_active'].initial = employee.is_active

    def save(self):
        emp = self.employee
        data = self.cleaned_data
        user = emp.user
        user.first_name = data['first_name']
        user.last_name = data['last_name']
        user.email = data.get('email') or ''
        user.phone = data.get('phone') or ''
        user.roles = list(data['roles'])
        user.is_active = data.get('is_user_active', False)
        user.save()

        emp.birth_date = data.get('birth_date')
        emp.hire_date = data['hire_date']
        emp.bureau = data['bureau']
        emp.direction = data['direction']
        emp.position = data['position']
        emp.is_active = data.get('is_active', False)
        emp.save()
        return emp


# ============ Documents ============

class EmployeeDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['name', 'file', 'description']
        widgets = {
            'name': forms.TextInput(attrs=_TEXT),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={**_TEXT, 'rows': 2}),
        }
