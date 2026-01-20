from django.urls import path
from . import views

app_name = 'widget'

urlpatterns = [
    path('valorador.js', views.valorador_js, name='valorador_js'),
]
