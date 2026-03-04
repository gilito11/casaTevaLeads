from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('subscribe/', views.subscribe_push, name='subscribe'),
    path('unsubscribe/', views.unsubscribe_push, name='unsubscribe'),
    path('settings/', views.alert_settings_view, name='alert_settings'),
    path('dropdown/', views.notification_dropdown_view, name='dropdown'),
    path('count/', views.notification_count_view, name='count'),
    path('<int:pk>/read/', views.notification_mark_read_view, name='mark_read'),
    path('mark-all-read/', views.notification_mark_all_read_view, name='mark_all_read'),
]
