from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
]
