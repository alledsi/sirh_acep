"""URLs du module Organisation."""
from django.urls import path

from . import views

app_name = 'organization'

urlpatterns = [
    # Mutuelles
    path('mutuelles/', views.MutuelleListView.as_view(), name='mutuelle_list'),
    path('mutuelles/nouvelle/', views.MutuelleCreateView.as_view(), name='mutuelle_create'),
    path('mutuelles/<int:pk>/modifier/', views.MutuelleUpdateView.as_view(), name='mutuelle_update'),
    path('mutuelles/<int:pk>/supprimer/', views.MutuelleDeleteView.as_view(), name='mutuelle_delete'),

    # Agences
    path('agences/', views.AgenceListView.as_view(), name='agence_list'),
    path('agences/nouvelle/', views.AgenceCreateView.as_view(), name='agence_create'),
    path('agences/<int:pk>/modifier/', views.AgenceUpdateView.as_view(), name='agence_update'),
    path('agences/<int:pk>/supprimer/', views.AgenceDeleteView.as_view(), name='agence_delete'),

    # Bureaux
    path('bureaux/', views.BureauListView.as_view(), name='bureau_list'),
    path('bureaux/nouveau/', views.BureauCreateView.as_view(), name='bureau_create'),
    path('bureaux/<int:pk>/', views.BureauDetailView.as_view(), name='bureau_detail'),
    path('bureaux/<int:pk>/modifier/', views.BureauUpdateView.as_view(), name='bureau_update'),
    path('bureaux/<int:pk>/supprimer/', views.BureauDeleteView.as_view(), name='bureau_delete'),

    # Directions
    path('directions/', views.DirectionListView.as_view(), name='direction_list'),
    path('directions/nouvelle/', views.DirectionCreateView.as_view(), name='direction_create'),
    path('directions/<int:pk>/modifier/', views.DirectionUpdateView.as_view(), name='direction_update'),
    path('directions/<int:pk>/supprimer/', views.DirectionDeleteView.as_view(), name='direction_delete'),
]
