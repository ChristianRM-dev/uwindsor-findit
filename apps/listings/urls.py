from django.urls import path

from apps.listings import views

app_name = "listings"

urlpatterns = [
    path("search", views.search_results_view, name="search_results"),
    path("items/<int:pk>", views.item_detail_view, name="item_detail_public"),
    path("items/lost/new", views.report_lost_item_view, name="report_lost_item"),
]
