"""URLs du module Planning."""
from django.urls import path

from . import views

app_name = 'planning'

urlpatterns = [
    path('', views.PlanningEditView.as_view(), name='edit'),
    # Jours fériés
    path('jours-feries/', views.HolidayListView.as_view(), name='holiday_list'),
    path('jours-feries/nouveau/', views.HolidayCreateView.as_view(), name='holiday_create'),
    path('jours-feries/<int:pk>/modifier/', views.HolidayUpdateView.as_view(), name='holiday_update'),
    path('jours-feries/<int:pk>/supprimer/', views.HolidayDeleteView.as_view(), name='holiday_delete'),
]
