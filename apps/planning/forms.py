"""Formulaires du module Planning."""
from django import forms
from django.forms import inlineformset_factory

from .models import DailySchedule, Holiday, Planning


_TEXT = {'class': 'form-control'}
_SELECT = {'class': 'form-select'}
_TIME = {'class': 'form-control', 'type': 'time'}
_DATE = {'class': 'form-control', 'type': 'date'}
_CHECK = {'class': 'form-check-input'}


class PlanningForm(forms.ModelForm):
    """Édition du Planning unique : tolérance et durée max de pause."""
    max_break_duration_hhmm = forms.CharField(
        label='Durée maximale de pause (HH:MM)',
        max_length=5,
        widget=forms.TextInput(attrs={**_TEXT, 'placeholder': '01:30'}),
        help_text='Format heures:minutes (ex : 01:30 pour 1h30).',
    )

    class Meta:
        model = Planning
        fields = ['tolerance_minutes', 'max_break_duration_hhmm']
        widgets = {
            'tolerance_minutes': forms.NumberInput(attrs={**_TEXT, 'min': 0, 'max': 60}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            dur = self.instance.max_break_duration
            total_min = int(dur.total_seconds() // 60)
            self.fields['max_break_duration_hhmm'].initial = f'{total_min // 60:02d}:{total_min % 60:02d}'

    def clean_max_break_duration_hhmm(self):
        from datetime import timedelta
        value = self.cleaned_data['max_break_duration_hhmm'].strip()
        try:
            h, m = value.split(':')
            return timedelta(hours=int(h), minutes=int(m))
        except (ValueError, AttributeError):
            raise forms.ValidationError("Format invalide. Attendu : HH:MM (ex : 01:30).")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.max_break_duration = self.cleaned_data['max_break_duration_hhmm']
        if commit:
            instance.save()
        return instance


class DailyScheduleForm(forms.ModelForm):
    class Meta:
        model = DailySchedule
        fields = ['day_of_week', 'mode', 'start_time', 'end_time', 'break_start', 'break_end']
        widgets = {
            'day_of_week': forms.HiddenInput(),
            'mode': forms.Select(attrs={**_SELECT, 'class': 'form-select form-select-sm'}),
            'start_time': forms.TimeInput(attrs={**_TIME, 'class': 'form-control form-control-sm'}),
            'end_time': forms.TimeInput(attrs={**_TIME, 'class': 'form-control form-control-sm'}),
            'break_start': forms.TimeInput(attrs={**_TIME, 'class': 'form-control form-control-sm'}),
            'break_end': forms.TimeInput(attrs={**_TIME, 'class': 'form-control form-control-sm'}),
        }


DailyScheduleFormSet = inlineformset_factory(
    Planning, DailySchedule,
    form=DailyScheduleForm,
    extra=0, can_delete=False,
)


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ['name', 'date', 'description', 'is_paid', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={**_TEXT, 'placeholder': 'Ex : Fête du Travail'}),
            'date': forms.DateInput(attrs=_DATE, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={**_TEXT, 'rows': 2}),
            'is_paid': forms.CheckboxInput(attrs=_CHECK),
            'is_active': forms.CheckboxInput(attrs=_CHECK),
        }
