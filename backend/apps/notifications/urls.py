from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('subscribe/', views.subscribe_push, name='subscribe'),
    path('unsubscribe/', views.unsubscribe_push, name='unsubscribe'),
    path('settings/', views.alert_settings_view, name='alert_settings'),
]
