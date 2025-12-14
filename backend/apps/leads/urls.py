from django.urls import path
from leads import views

app_name = 'leads'

urlpatterns = [
    path('', views.lead_list_view, name='list'),
    path('<int:lead_id>/', views.lead_detail_view, name='detail'),
    path('<int:lead_id>/change-status/', views.change_status_view, name='change_status'),
    path('<int:lead_id>/add-note/', views.add_note_view, name='add_note'),
]
