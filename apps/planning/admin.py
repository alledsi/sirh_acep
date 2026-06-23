"""Admin Django du module Planning."""
from django.contrib import admin

from .models import DailySchedule, Holiday, Planning


class DailyScheduleInline(admin.TabularInline):
    model = DailySchedule
    extra = 0
    fields = ('day_of_week', 'mode', 'start_time', 'end_time', 'break_start', 'break_end')
    ordering = ('day_of_week',)


@admin.register(Planning)
class PlanningAdmin(admin.ModelAdmin):
    list_display = ('name', 'tolerance_minutes', 'max_break_duration', 'is_active')
    list_filter = ('is_active',)
    inlines = [DailyScheduleInline]


@admin.register(DailySchedule)
class DailyScheduleAdmin(admin.ModelAdmin):
    list_display = ('planning', 'day_of_week', 'mode', 'start_time', 'end_time', 'break_start', 'break_end')
    list_filter = ('planning', 'mode')


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'is_paid', 'is_active')
    list_filter = ('is_active', 'is_paid')
    search_fields = ('name',)
    date_hierarchy = 'date'
    ordering = ('-date',)
