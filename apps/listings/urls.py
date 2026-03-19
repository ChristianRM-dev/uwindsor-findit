from django.urls import path

from apps.listings import views

app_name = "listings"

urlpatterns = [
    path("search", views.search_results_view, name="search_results"),
    path("faq/", views.faq_view, name="faq"),

    path("items/<int:pk>", views.item_detail_view, name="item_detail_public"),
    path("items/<int:pk>/edit/", views.item_edit_view, name="item_edit"),
    path("items/<int:pk>/delete/", views.item_delete_view, name="item_delete"),

    path("items/lost/new", views.report_lost_item_view, name="report_lost_item"),
    path("items/found/new", views.report_found_item_view, name="report_found_item"),

    path("claims/new/<int:item_id>/", views.claim_create_view, name="claim_create"),
    path("claims/<int:claim_id>", views.claim_detail_view, name="claim_detail"),
    path("claims/<int:claim_id>/review/", views.claim_review_view, name="claim_review"),

    path("my/claims", views.my_claims_view, name="my_claims"),
    path("my/received-claims", views.my_received_claims_view, name="my_received_claims"),
    path("my/items", views.my_items_view, name="my_items"),
]
