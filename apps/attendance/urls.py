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
]
