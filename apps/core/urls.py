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
]
