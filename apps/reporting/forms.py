"""Formulaires du module Reporting."""
from django import forms


class AnomalyValidateForm(forms.Form):
    """Validation d'une anomalie par un Directeur ou la RH/DG."""
    note = forms.CharField(
        label='Justification / commentaire',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'Ex : agent en mission terrain, retard exceptionnel justifié…',
        }),
        required=True,
    )
