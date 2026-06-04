"""Admin Django du module Employees."""
from django.contrib import admin

from .models import Employee, EmployeeDocument


class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0
    fields = ('name', 'file', 'description', 'uploaded_by')
    readonly_fields = ('uploaded_by',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'matricule_display', 'full_name_display', 'position',
        'bureau', 'direction', 'is_active',
    )
    list_filter = ('is_active', 'direction', 'bureau__agence__mutuelle', 'bureau__agence')
    search_fields = ('user__matricule', 'user__first_name', 'user__last_name', 'user__email', 'position')
    autocomplete_fields = ('user', 'bureau', 'direction', 'manager')
    inlines = [EmployeeDocumentInline]

    fieldsets = (
        ('Compte', {'fields': ('user', 'is_active')}),
        ('Affectation', {'fields': ('bureau', 'direction', 'position', 'manager')}),
        ('Infos personnelles', {'fields': ('photo', 'birth_date', 'hire_date')}),
    )

    @admin.display(description='Matricule', ordering='user__matricule')
    def matricule_display(self, obj):
        return obj.user.matricule

    @admin.display(description='Nom complet')
    def full_name_display(self, obj):
        return obj.user.get_full_name() or '—'


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee', 'uploaded_by', 'created_at')
    search_fields = ('name', 'employee__user__matricule')
    autocomplete_fields = ('employee',)
    readonly_fields = ('uploaded_by',)

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
