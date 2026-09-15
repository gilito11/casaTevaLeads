from django.urls import path
from . import views

urlpatterns = [
    path('valorar/', views.valorar_api, name='valorar'),
    path('lead/', views.lead_api, name='lead'),
    path('demo-request/', views.demo_request_api, name='demo_request'),
]
