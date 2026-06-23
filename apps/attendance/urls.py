"""URLs du module Attendance."""
from django.urls import path

from . import views

app_name = 'attendance'

urlpatterns = [
    # Dashboard et pointage
    path('', views.dashboard, name='dashboard'),
    path('pointer/', views.pointer, name='pointer'),

    # Actions (POST)
    path('pointer/arrivee/', views.action_arrival, name='action_arrival'),
    path('pointer/pause-debut/', views.action_break_start, name='action_break_start'),
    path('pointer/pause-fin/', views.action_break_end, name='action_break_end'),
    path('pointer/depart/', views.action_departure, name='action_departure'),
    path('pointer/annuler-depart/', views.action_cancel_departure, name='action_cancel_departure'),

    # Historique
    path('historique/', views.historique, name='historique'),
    path('pointage/<int:pk>/', views.time_entry_detail, name='time_entry_detail'),

    # Régularisation (RH/DG)
    path('regularisation/', views.TimeEntryRegularizeView.as_view(), name='regularize'),
    path('regularisation/historique/', views.RegularizationListView.as_view(), name='regularize_list'),

    # Justifications d'absence (agent + RH)
    path('justifications/', views.MyJustificationListView.as_view(), name='my_justifications'),
    path('justifications/nouvelle/', views.JustificationCreateView.as_view(), name='my_justifications_new'),
    path('justifications/a-valider/', views.JustificationReviewListView.as_view(), name='justification_review_list'),
    path('justifications/<int:pk>/valider/', views.JustificationReviewView.as_view(), name='justification_review'),
]
