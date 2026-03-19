from django.contrib.auth.decorators import login_required
from datetime import datetime
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from types import SimpleNamespace

from apps.core.models import UserActivity
from apps.core.services import track_activity
from apps.listings.models import Claim, Item

def home_view(request: HttpRequest) -> HttpResponse:
    base_items_qs = (
        Item.objects.filter(is_visible=True)
        .select_related("category", "location")
        .prefetch_related("images")
    )
    context = {
        "recent_lost_items": base_items_qs.filter(status=Item.Status.LOST).order_by("-created_at")[:4],
        "recent_found_items": base_items_qs.filter(status=Item.Status.FOUND).order_by("-created_at")[:4],
    }
    track_activity(
        request,
        UserActivity.ActivityType.PAGE_VIEW,
        metadata={"page": "home"},
    )
    return render(request, "core/home.html", context)

def components_demo_view(request: HttpRequest) -> HttpResponse:
    # Simple demo objects to feed into item_card.html
    demo_item_1 = SimpleNamespace(
        id=1,
        title="Black AirPods Case",
        status="found",
        category="Electronics",
        location="Leddy Library",
        reported_at=datetime(2026, 2, 10),
    )

    demo_item_2 = SimpleNamespace(
        id=2,
        title="Blue Hoodie (Size M)",
        status="lost",
        category="Clothing",
        location="CAW Student Centre",
        reported_at=datetime(2026, 2, 9),
    )

    demo_item_3 = SimpleNamespace(
        id=3,
        title="Student ID Card",
        status="claimed",
        category="Documents",
        location="Essex Hall",
        reported_at=datetime(2026, 2, 7),
    )

    return render(
        request,
        "core/components_demo.html",
        {
            "demo_item_1": demo_item_1,
            "demo_item_2": demo_item_2,
            "demo_item_3": demo_item_3,
        },
    )

@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    recent_activities = (
        UserActivity.objects.filter(user=request.user)
        .select_related("item")
        .order_by("-created_at")[:6]
    )
    pending_received_claims = Claim.objects.filter(
        item__reporter=request.user,
        status=Claim.Status.PENDING,
    ).count()
    my_pending_claims = Claim.objects.filter(
        claimant=request.user,
        status=Claim.Status.PENDING,
    ).count()
    my_items_count = Item.objects.filter(reporter=request.user, is_visible=True).count()

    context = {
        "pending_received_claims": pending_received_claims,
        "my_pending_claims": my_pending_claims,
        "my_items_count": my_items_count,
        "recent_activities": recent_activities,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": None, "active": True},
        ],
    }
    track_activity(
        request,
        UserActivity.ActivityType.PAGE_VIEW,
        metadata={"page": "dashboard"},
    )
    return render(request, "core/dashboard.html", context)


def about_view(request: HttpRequest) -> HttpResponse:
    context = {
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "About", "url": None, "active": True},
        ],
    }
    return render(request, "core/about.html", context)


def contact_view(request: HttpRequest) -> HttpResponse:
    context = {
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Contact", "url": None, "active": True},
        ],
    }
    return render(request, "core/contact.html", context)


def custom_404_view(request, exception):
    return render(request, "404.html", status=404)


def custom_403_view(request, exception):
    return render(request, "403.html", status=403)


def custom_500_view(request):
    return render(request, "500.html", status=500)
