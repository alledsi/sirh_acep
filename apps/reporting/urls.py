"""URLs du module Reporting."""
from django.urls import path

from . import views

app_name = 'reporting'

urlpatterns = [
    # Directeur
    path('direction/', views.DirecteurDashboardView.as_view(), name='directeur_dashboard'),
    path('direction/equipe/', views.DirecteurEquipeView.as_view(), name='directeur_equipe'),
    path('direction/anomalies/', views.DirecteurAnomaliesView.as_view(), name='directeur_anomalies'),

    # Chef d'agence
    path('agence/', views.ChefAgenceDashboardView.as_view(), name='chef_agence_dashboard'),
    path('agence/equipe/', views.ChefAgenceEquipeView.as_view(), name='chef_agence_equipe'),
    path('agence/anomalies/', views.ChefAgenceAnomaliesView.as_view(), name='chef_agence_anomalies'),

    # RH/DG
    path('statistiques/', views.RHStatsView.as_view(), name='rh_stats'),
    path('anomalies/', views.AnomalyListView.as_view(), name='anomaly_list'),
    path('suivi-quotidien/', views.DailyTrackingView.as_view(), name='daily_tracking'),
    path('cumul-mensuel/', views.MonthlyHoursView.as_view(), name='monthly_hours'),
    path('export/', views.ExportStatsView.as_view(), name='export_stats'),

    # Validation d'une anomalie (commun)
    path('anomalies/<int:pk>/valider/', views.AnomalyValidateView.as_view(), name='anomaly_validate'),
]
