"""URLs du module Employees."""
from django.urls import path

from . import views

app_name = 'employees'

urlpatterns = [
    # Employés
    path('', views.EmployeeListView.as_view(), name='employee_list'),
    path('nouveau/', views.EmployeeCreateView.as_view(), name='employee_create'),
    path('import/', views.EmployeeImportView.as_view(), name='employee_import'),
    path('import/modele/', views.EmployeeImportTemplateView.as_view(), name='employee_import_template'),
    path('<int:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
    path('<int:pk>/modifier/', views.EmployeeUpdateView.as_view(), name='employee_update'),
    path('<int:pk>/desactiver/', views.EmployeeDeleteView.as_view(), name='employee_delete'),

    # Mon profil (vue agent)
    path('mon-profil/', views.MyProfileView.as_view(), name='my_profile'),
]
