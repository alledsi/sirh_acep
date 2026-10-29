"""URLs du module Core (auth + accueil)."""
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.LoginPageView.as_view(), name='login'),
    path('logout/', views.LogoutPageView.as_view(), name='logout'),
    path('mot-de-passe/changer/', views.PasswordChangePageView.as_view(), name='password_change'),
    path('mot-de-passe/change/ok/', views.password_change_done, name='password_change_done'),

    # Messages diffusés (RH / DG)
    path('messages/', views.BroadcastListView.as_view(), name='broadcast_list'),
    path('messages/nouveau/', views.BroadcastCreateView.as_view(), name='broadcast_create'),
    path('messages/<int:pk>/modifier/', views.BroadcastUpdateView.as_view(), name='broadcast_update'),
    path('messages/<int:pk>/supprimer/', views.BroadcastDeleteView.as_view(), name='broadcast_delete'),
    path('messages/<int:pk>/basculer/', views.BroadcastToggleView.as_view(), name='broadcast_toggle'),
    path('messages/ack/', views.broadcast_ack, name='broadcast_ack'),
]
