from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("health/", views.health_view, name="health"),
    path("", views.home_view, name="home"),
    path("about/", views.about_view, name="about"),
    path("contact/", views.contact_view, name="contact"),
    path("team/", views.team_view, name="team"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("notifications/", views.notifications_view, name="notifications"),
    path(
        "notifications/mark-all-read/",
        views.notifications_mark_all_read_view,
        name="notifications_mark_all_read",
    ),
    path("demo/components/", views.components_demo_view, name="components_demo"),
]
