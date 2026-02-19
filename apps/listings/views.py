from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.listings.models import CampusLocation, Category, Item


def search_results_view(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    location_code = (request.GET.get("location") or "").strip()
    status = (request.GET.get("status") or "").strip()
    sort = (request.GET.get("sort") or "newest").strip()

    items_qs = (
        Item.objects.filter(is_visible=True)
        .select_related("category", "location", "reporter")
        .prefetch_related("images")
    )

    if q:
        items_qs = items_qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )
    if category_slug:
        items_qs = items_qs.filter(category__slug=category_slug)
    if location_code:
        items_qs = items_qs.filter(location__code=location_code)
    if status:
        items_qs = items_qs.filter(status=status)

    if sort == "oldest":
        items_qs = items_qs.order_by("created_at")
    elif sort == "event_date":
        items_qs = items_qs.order_by("-event_date")
    else:
        items_qs = items_qs.order_by("-created_at")

    paginator = Paginator(items_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_chips = []
    if q:
        query_chips.append({"label": "q", "value": q})
    if category_slug:
        query_chips.append({"label": "category", "value": category_slug})
    if location_code:
        query_chips.append({"label": "location", "value": location_code})
    if status:
        query_chips.append({"label": "status", "value": status})

    context = {
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "categories": Category.objects.filter(is_active=True),
        "locations": CampusLocation.objects.filter(is_active=True),
        "query_chips": query_chips,
        "filters": {
            "q": q,
            "category": category_slug,
            "location": location_code,
            "status": status,
            "sort": sort,
        },
        "result_count": paginator.count,
    }
    return render(request, "listings/search_results.html", context)


def item_detail_view(request, pk: int):
    item = get_object_or_404(
        Item.objects.filter(is_visible=True)
        .select_related("category", "location", "reporter")
        .prefetch_related("images"),
        pk=pk,
    )

    is_guest = not request.user.is_authenticated
    claim_url = reverse("listings:claim_create", kwargs={"item_id": item.id}) if request.user.is_authenticated else None
    login_url = reverse("users:login")
    register_url = reverse("users:register")

    context = {
        "item": item,
        "images": item.images.all(),
        "is_guest": is_guest,
        "claim_url": claim_url,
        "login_url": login_url,
        "register_url": register_url,
        "search_url": reverse("listings:search_results"),
    }
    return render(request, "listings/item_detail.html", context)
