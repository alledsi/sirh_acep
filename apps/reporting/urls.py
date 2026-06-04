"""URLs du module Reporting."""
from django.urls import path

from . import views

app_name = 'reporting'

urlpatterns = [
    # Directeur
    path('direction/', views.DirecteurDashboardView.as_view(), name='directeur_dashboard'),
    path('direction/equipe/', views.DirecteurEquipeView.as_view(), name='directeur_equipe'),
    path('direction/anomalies/', views.DirecteurAnomaliesView.as_view(), name='directeur_anomalies'),

    # RH/DG
    path('statistiques/', views.RHStatsView.as_view(), name='rh_stats'),
    path('anomalies/', views.AnomalyListView.as_view(), name='anomaly_list'),

    # Validation d'une anomalie (commun)
    path('anomalies/<int:pk>/valider/', views.AnomalyValidateView.as_view(), name='anomaly_validate'),
]
