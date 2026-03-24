from datetime import datetime, timedelta
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.core.models import Notification, UserActivity
from apps.core.services import mark_all_notifications_as_read, track_activity
from apps.listings.models import Claim, Item


def health_view(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"status": "ok"})


def home_view(request: HttpRequest) -> HttpResponse:
    base_items_qs = (
        Item.objects.filter(is_visible=True)
        .select_related("category", "location")
        .prefetch_related("images")
    )
    context = {
        "recent_lost_items": base_items_qs.filter(status=Item.Status.LOST).order_by(
            "-created_at"
        )[:4],
        "recent_found_items": base_items_qs.filter(status=Item.Status.FOUND).order_by(
            "-created_at"
        )[:4],
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
        "today_page_views": UserActivity.objects.filter(
            user=request.user,
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            created_at__date=timezone.localdate(),
        ).count(),
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


def privacy_view(request: HttpRequest) -> HttpResponse:
    context = {
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Privacy", "url": None, "active": True},
        ],
    }
    return render(request, "core/privacy.html", context)


def terms_view(request: HttpRequest) -> HttpResponse:
    context = {
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Terms", "url": None, "active": True},
        ],
    }
    return render(request, "core/terms.html", context)


def team_view(request: HttpRequest) -> HttpResponse:
    context = {
        "team_members": [
            {
                "name": "Christian Rios Mancilla",
                "email": "riosman@uwindsor.ca",
            },
            {
                "name": "Sweatha Panneer Selvam",
                "email": "panneers@uwindsor.ca",
            },
            {
                "name": "Hong An Do",
                "email": "doan31@uwindsor.ca",
            },
            {
                "name": "Zhaojun Zhang",
                "email": "zhang6o3@uwindsor.ca",
            },
            {
                "name": "Tingwan Zhou",
                "email": "zhou9x@uwindsor.ca",
            },
        ],
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Team", "url": None, "active": True},
        ],
    }
    return render(request, "core/team.html", context)


@login_required
def history_view(request: HttpRequest) -> HttpResponse:
    if not request.session.session_key:
        request.session.save()

    activities_qs = UserActivity.objects.filter(user=request.user).select_related("item")
    recent_activities = list(activities_qs.order_by("-created_at")[:25])
    today = timezone.localdate()
    start_date = today - timedelta(days=6)

    daily_page_views_qs = (
        activities_qs.filter(
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            created_at__date__gte=start_date,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    counts_by_day = {entry["day"]: entry["count"] for entry in daily_page_views_qs}
    max_daily_visits = max(counts_by_day.values(), default=1)

    daily_page_views = []
    for offset in range(7):
        current_day = start_date + timedelta(days=offset)
        visit_count = counts_by_day.get(current_day, 0)
        daily_page_views.append(
            {
                "date": current_day,
                "count": visit_count,
                "bar_width": int((visit_count / max_daily_visits) * 100) if visit_count else 0,
            }
        )

    context = {
        "page_views_today": activities_qs.filter(
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            created_at__date=today,
        ).count(),
        "page_views_last_7_days": activities_qs.filter(
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            created_at__date__gte=start_date,
        ).count(),
        "search_count": activities_qs.filter(
            activity_type=UserActivity.ActivityType.SEARCH
        ).count(),
        "item_view_count": activities_qs.filter(
            activity_type=UserActivity.ActivityType.ITEM_VIEW
        ).count(),
        "claim_activity_count": activities_qs.filter(
            activity_type__in=[
                UserActivity.ActivityType.CLAIM_SUBMISSION,
                UserActivity.ActivityType.CLAIM_REVIEW,
            ]
        ).count(),
        "message_count": activities_qs.filter(
            activity_type=UserActivity.ActivityType.MESSAGE
        ).count(),
        "current_session_activity_count": activities_qs.filter(
            session_key=request.session.session_key or "",
        ).count(),
        "daily_page_views": daily_page_views,
        "recent_activities": recent_activities,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "User History", "url": None, "active": True},
        ],
    }
    track_activity(
        request,
        UserActivity.ActivityType.PAGE_VIEW,
        metadata={"page": "history"},
    )
    return render(request, "core/history.html", context)


@login_required
def notifications_view(request: HttpRequest) -> HttpResponse:
    notifications = (
        Notification.objects.filter(recipient=request.user)
        .select_related("item", "claim")
        .order_by("-created_at")
    )
    context = {
        "notifications": notifications,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "Notifications", "url": None, "active": True},
        ],
    }
    track_activity(
        request,
        UserActivity.ActivityType.PAGE_VIEW,
        metadata={"page": "notifications"},
    )
    return render(request, "core/notifications.html", context)


@login_required
@require_POST
def notifications_mark_all_read_view(request: HttpRequest) -> HttpResponse:
    updated_count = mark_all_notifications_as_read(user=request.user)
    if updated_count:
        messages.success(request, f"Marked {updated_count} notification(s) as read.")
    else:
        messages.info(request, "No unread notifications right now.")
    return redirect("core:notifications")


def custom_404_view(request, exception):
    return render(request, "404.html", status=404)


def custom_403_view(request, exception):
    return render(request, "403.html", status=403)


def custom_500_view(request):
    return render(request, "500.html", status=500)
