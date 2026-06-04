"""Admin Django du module Organisation.

Permet à la RH/DG de gérer les mutuelles, agences, bureaux, directions et postes
directement depuis l'admin Django, en complément des vues HTML personnalisées.
"""
from django.contrib import admin

from .models import Agence, Bureau, Direction, IPBureauMapping, Mutuelle


class IPBureauMappingInline(admin.TabularInline):
    """Inline pour gérer les plages IP directement depuis la fiche Bureau."""
    model = IPBureauMapping
    extra = 1
    fields = ('ip_pattern', 'description', 'is_active')


@admin.register(Mutuelle)
class MutuelleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'agences_count', 'bureaux_count_display', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    fields = ('code', 'name', 'description', 'is_active')

    @admin.display(description='Agences')
    def agences_count(self, obj):
        return obj.agences.count()

    @admin.display(description='Bureaux')
    def bureaux_count_display(self, obj):
        return obj.bureaux_count


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'mutuelle', 'region', 'bureaux_count', 'is_active')
    list_filter = ('mutuelle', 'region', 'is_active')
    search_fields = ('code', 'name', 'region')
    autocomplete_fields = ('mutuelle',)

    @admin.display(description='Bureaux')
    def bureaux_count(self, obj):
        return obj.bureaux.count()


@admin.register(Bureau)
class BureauAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'agence', 'mutuelle_display', 'ip_count', 'is_active')
    list_filter = ('agence__mutuelle', 'agence', 'is_active')
    search_fields = ('code', 'name')
    autocomplete_fields = ('agence',)
    inlines = [IPBureauMappingInline]

    @admin.display(description='Mutuelle')
    def mutuelle_display(self, obj):
        return obj.agence.mutuelle

    @admin.display(description='Plages IP')
    def ip_count(self, obj):
        return obj.ip_mappings.count()


@admin.register(IPBureauMapping)
class IPBureauMappingAdmin(admin.ModelAdmin):
    list_display = ('ip_pattern', 'bureau', 'description', 'is_active')
    list_filter = ('is_active', 'bureau__agence__mutuelle')
    search_fields = ('ip_pattern', 'bureau__code', 'bureau__name')
    autocomplete_fields = ('bureau',)


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'directeur', 'parent_direction', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    autocomplete_fields = ('parent_direction', 'directeur')
