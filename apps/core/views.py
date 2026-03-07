from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from datetime import datetime
from types import SimpleNamespace

from apps.listings.models import Claim, Item

def home_view(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")

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
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": None, "active": True},
        ],
    }
    return render(request, "core/dashboard.html", context)
