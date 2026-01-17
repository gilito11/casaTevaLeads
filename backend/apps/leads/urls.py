from django.urls import path
from leads import views

app_name = 'leads'

urlpatterns = [
    # Leads
    path('', views.lead_list_view, name='list'),
    path('bulk-change-status/', views.bulk_change_status_view, name='bulk_change_status'),
    path('bulk-delete/', views.bulk_delete_view, name='bulk_delete'),
    path('bulk-assign/', views.bulk_assign_view, name='bulk_assign'),

    # Calendar
    path('calendar/', views.calendar_view, name='calendar'),

    # Contact Queue (auto-contact)
    path('contact-queue/', views.contact_queue_view, name='contact_queue'),
    path('contact-queue/<int:queue_id>/cancel/', views.cancel_queued_contact_view, name='cancel_queued'),
    path('bulk-enqueue/', views.bulk_enqueue_view, name='bulk_enqueue'),

    # Contacts
    path('contacts/', views.contact_list_view, name='contact_list'),
    path('contacts/<int:contact_id>/', views.contact_detail_view, name='contact_detail'),
    path('contacts/<int:contact_id>/update/', views.contact_update_view, name='contact_update'),
    path('contacts/<int:contact_id>/add-interaction/', views.add_interaction_view, name='add_interaction'),
    path('interactions/<int:interaction_id>/delete/', views.delete_interaction_view, name='delete_interaction'),

    # Lead detail (must be last due to catch-all pattern)
    path('<str:lead_id>/', views.lead_detail_view, name='detail'),
    path('<str:lead_id>/change-status/', views.change_status_view, name='change_status'),
    path('<str:lead_id>/add-note/', views.add_note_view, name='add_note'),
    path('<str:lead_id>/delete/', views.delete_lead_view, name='delete'),
    path('<str:lead_id>/contact/', views.contact_from_lead_view, name='contact_from_lead'),
    path('<str:lead_id>/assign/', views.assign_lead_view, name='assign'),
    path('<str:lead_id>/enqueue/', views.enqueue_contact_view, name='enqueue_contact'),
]
