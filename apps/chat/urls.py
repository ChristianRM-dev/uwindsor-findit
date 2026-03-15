from django.urls import path

from apps.chat import views

app_name = "chat"

urlpatterns = [
    path("items/<int:item_id>/contact", views.contact_owner_view, name="contact_owner"),
    path("messages", views.message_list_view, name="message_list"),
    path("messages/<int:conversation_id>", views.message_thread_view, name="message_thread"),
]
