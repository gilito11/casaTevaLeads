from django.urls import path
from leads import views

app_name = 'leads'

urlpatterns = [
    path('', views.lead_list_view, name='list'),
    path('bulk-change-status/', views.bulk_change_status_view, name='bulk_change_status'),
    path('bulk-delete/', views.bulk_delete_view, name='bulk_delete'),
    path('<str:lead_id>/', views.lead_detail_view, name='detail'),
    path('<str:lead_id>/change-status/', views.change_status_view, name='change_status'),
    path('<str:lead_id>/add-note/', views.add_note_view, name='add_note'),
    path('<str:lead_id>/delete/', views.delete_lead_view, name='delete'),
]
