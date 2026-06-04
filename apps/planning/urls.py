"""URLs du module Planning."""
from django.urls import path

from . import views

app_name = 'planning'

urlpatterns = [
    path('', views.PlanningEditView.as_view(), name='edit'),
]
