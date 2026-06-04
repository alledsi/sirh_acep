"""Admin Django du module Attendance."""
from django.contrib import admin

from .models import Anomaly, TimeEntry


class AnomalyInline(admin.TabularInline):
    model = Anomaly
    extra = 0
    readonly_fields = ('anomaly_type', 'severity', 'description', 'is_acknowledged', 'acknowledged_by', 'acknowledged_at')
    can_delete = False
    fields = readonly_fields


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = (
        'work_date', 'employee', 'arrival_time', 'departure_time',
        'arrival_bureau', 'arrival_ip', 'bureau_coherent_display', 'anomalies_count',
    )
    list_filter = ('work_date', 'arrival_bureau__agence__mutuelle')
    search_fields = ('employee__user__matricule', 'employee__user__last_name', 'arrival_ip')
    date_hierarchy = 'work_date'
    autocomplete_fields = ('employee', 'arrival_bureau', 'break_start_bureau', 'break_end_bureau', 'departure_bureau')
    inlines = [AnomalyInline]
    readonly_fields = ('worked_duration_display', 'break_duration_display')

    fieldsets = (
        (None, {'fields': ('employee', 'work_date')}),
        ('Arrivée', {'fields': ('arrival_time', 'arrival_bureau', 'arrival_ip')}),
        ('Pause', {'fields': ('break_start', 'break_start_bureau', 'break_start_ip',
                              'break_end', 'break_end_bureau', 'break_end_ip')}),
        ('Départ', {'fields': ('departure_time', 'departure_bureau', 'departure_ip')}),
        ('Calculs', {'fields': ('worked_duration_display', 'break_duration_display')}),
    )

    @admin.display(description='Cohérence', boolean=True)
    def bureau_coherent_display(self, obj):
        return obj.bureau_coherent if obj.arrival_bureau else None

    @admin.display(description='Anomalies')
    def anomalies_count(self, obj):
        return obj.anomalies.count()

    @admin.display(description='Durée travaillée')
    def worked_duration_display(self, obj):
        return obj.worked_duration or '—'

    @admin.display(description='Durée pause')
    def break_duration_display(self, obj):
        return obj.break_duration or '—'


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ('time_entry', 'anomaly_type', 'severity', 'is_acknowledged', 'acknowledged_by')
    list_filter = ('anomaly_type', 'severity', 'is_acknowledged')
    search_fields = ('time_entry__employee__user__matricule', 'description')
    autocomplete_fields = ('time_entry',)
    readonly_fields = ('anomaly_type', 'severity', 'description')
