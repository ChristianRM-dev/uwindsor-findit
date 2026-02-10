from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("demo/components/", views.components_demo_view, name="components_demo"),
]
