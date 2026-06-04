"""Formulaires du module Organisation (CRUD via vues HTML personnalisées)."""
from django import forms
from django.forms import inlineformset_factory

from .models import Agence, Bureau, Direction, IPBureauMapping, Mutuelle


_TEXT = {'class': 'form-control'}
_SELECT = {'class': 'form-select'}
_CHECK = {'class': 'form-check-input'}
_TEXTAREA = {'class': 'form-control', 'rows': 3}


class MutuelleForm(forms.ModelForm):
    class Meta:
        model = Mutuelle
        fields = ['code', 'name', 'description', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : MUT-DKR'}),
            'name': forms.TextInput(attrs=_TEXT),
            'description': forms.Textarea(attrs=_TEXTAREA),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }


class AgenceForm(forms.ModelForm):
    class Meta:
        model = Agence
        fields = ['mutuelle', 'code', 'name', 'region', 'address', 'is_active']
        widgets = {
            'mutuelle': forms.Select(attrs=_SELECT),
            'code': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : AG-VDN'}),
            'name': forms.TextInput(attrs=_TEXT),
            'region': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : Dakar'}),
            'address': forms.Textarea(attrs={**_TEXTAREA, 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }


class BureauForm(forms.ModelForm):
    class Meta:
        model = Bureau
        fields = ['agence', 'code', 'name', 'address', 'is_active']
        widgets = {
            'agence': forms.Select(attrs=_SELECT),
            'code': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : BUR-VDN-01'}),
            'name': forms.TextInput(attrs=_TEXT),
            'address': forms.Textarea(attrs={**_TEXTAREA, 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }


class IPBureauMappingForm(forms.ModelForm):
    class Meta:
        model = IPBureauMapping
        fields = ['ip_pattern', 'description', 'is_active']
        widgets = {
            'ip_pattern': forms.TextInput(attrs={
                **_TEXT, 'placeholder': '192.168.7.0/24', 'style': 'font-family: monospace;',
            }),
            'description': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Optionnel'}),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }


# Permet de gérer les plages IP en inline dans le formulaire Bureau.
# extra=1 pour proposer une ligne vide par défaut, can_delete pour permettre suppression.
IPBureauMappingFormSet = inlineformset_factory(
    Bureau,
    IPBureauMapping,
    form=IPBureauMappingForm,
    extra=1,
    can_delete=True,
    min_num=0,
)


class DirectionForm(forms.ModelForm):
    class Meta:
        model = Direction
        fields = ['code', 'name', 'description', 'parent_direction', 'directeur', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : DIR-COM'}),
            'name': forms.TextInput(attrs=_TEXT),
            'description': forms.Textarea(attrs=_TEXTAREA),
            'parent_direction': forms.Select(attrs=_SELECT),
            'directeur': forms.Select(attrs=_SELECT),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On ne peut pas se choisir soi-même comme parent
        if self.instance and self.instance.pk:
            self.fields['parent_direction'].queryset = (
                Direction.objects.exclude(pk=self.instance.pk)
            )
        # Restreindre les directeurs aux employés avec le rôle DIRECTEUR
        from apps.employees.models import Employee
        self.fields['directeur'].queryset = Employee.objects.filter(
            is_active=True, user__roles__contains=['DIRECTEUR']
        ).select_related('user')
