from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.dateparse import parse_date

from apps.core.models import UserActivity
from apps.core.services import track_activity
from apps.listings.forms import (
    ClaimCreateForm,
    ClaimReviewForm,
    ItemEditForm,
    ReportFoundItemForm,
    ReportLostItemForm,
)
from apps.listings.models import CampusLocation, Category, Claim, ClaimProof, Item
from apps.listings.models import ItemImage
from apps.listings.services import ClaimReviewError, review_claim

SEARCH_SORT_OPTIONS = (
    ("relevance", "Most relevant"),
    ("newest", "Newest first"),
    ("oldest", "Oldest first"),
    ("event_date_desc", "Most recent event date"),
    ("event_date_asc", "Oldest event date"),
)
SEARCH_SORT_LABELS = dict(SEARCH_SORT_OPTIONS)

def _build_claim_proof_entries(proofs):
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")
    proof_entries = []

    for proof in proofs:
        filename = proof.file.name.rsplit("/", 1)[-1]
        proof_entries.append(
            {
                "proof": proof,
                "filename": filename,
                "is_image": filename.lower().endswith(image_extensions),
            }
        )

    return proof_entries


def _parse_claim_description(description: str):
    parsed = {
        "full_name": None,
        "email": None,
        "relationship_to_item": None,
        "where_lost": None,
        "claim_details": "",
        "is_structured": False,
    }
    details_lines = []
    in_details_section = False

    for raw_line in description.splitlines():
        line = raw_line.strip()
        if line.startswith("Full name:"):
            parsed["full_name"] = line.split(":", 1)[1].strip() or None
            parsed["is_structured"] = True
            continue
        if line.startswith("Email:"):
            parsed["email"] = line.split(":", 1)[1].strip() or None
            parsed["is_structured"] = True
            continue
        if line.startswith("Relationship to item:"):
            parsed["relationship_to_item"] = line.split(":", 1)[1].strip() or None
            parsed["is_structured"] = True
            continue
        if line.startswith("Where lost:"):
            parsed["where_lost"] = line.split(":", 1)[1].strip() or None
            parsed["is_structured"] = True
            continue
        if line == "Claim details:":
            in_details_section = True
            parsed["is_structured"] = True
            continue

        if in_details_section:
            details_lines.append(raw_line.rstrip())
        elif line:
            details_lines.append(raw_line.rstrip())

    claim_details = "\n".join(details_lines).strip()
    if claim_details:
        parsed["claim_details"] = claim_details
    elif parsed["is_structured"]:
        parsed["claim_details"] = "No detailed description provided."
    else:
        parsed["claim_details"] = description.strip()

    return parsed


def _build_report_page_context(*, form, item_type: str):
    item_label = "Found" if item_type == Item.ItemType.FOUND else "Lost"
    action_label = "found" if item_type == Item.ItemType.FOUND else "lost"

    return {
        "form": form,
        "cancel_url": reverse("core:dashboard"),
        "page_title": f"Report a {item_label} Item",
        "page_subtitle": f"Provide as many details as possible to help others identify what you {action_label}.",
        "submit_label": "Submit Report",
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": f"Report {item_label} Item", "url": None, "active": True},
        ],
    }


def _user_can_review_claim(user, claim: Claim) -> bool:
    return user.is_staff or claim.item.reporter_id == user.id


def _build_claim_detail_context(request, claim: Claim, *, review_form=None):
    proof_entries = _build_claim_proof_entries(claim.proofs.all())
    image_proofs = [entry for entry in proof_entries if entry["is_image"]]
    non_image_proofs = [entry for entry in proof_entries if not entry["is_image"]]

    if claim.claimant_id == request.user.id:
        parent_label = "My Claims"
        parent_url = reverse("listings:my_claims")
    elif claim.item.reporter_id == request.user.id:
        parent_label = "Claims Received"
        parent_url = reverse("listings:my_received_claims")
    else:
        parent_label = "Dashboard"
        parent_url = reverse("core:dashboard")

    can_review_claim = _user_can_review_claim(request.user, claim)

    return {
        "claim": claim,
        "proofs": proof_entries,
        "image_proofs": image_proofs,
        "non_image_proofs": non_image_proofs,
        "parsed_claim": _parse_claim_description(claim.description),
        "can_review_claim": can_review_claim,
        "show_review_form": can_review_claim and claim.status == Claim.Status.PENDING,
        "review_form": review_form or ClaimReviewForm(),
        "review_url": reverse("listings:claim_review", kwargs={"claim_id": claim.id}),
        "item_details_url": reverse("listings:item_detail_public", kwargs={"pk": claim.item_id}),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": parent_label, "url": parent_url, "active": False},
            {"label": f"Claim #{claim.id}", "url": None, "active": True},
        ],
    }


def _search_url_for_params(**params) -> str:
    cleaned_params = {
        key: value
        for key, value in params.items()
        if value not in ("", None)
    }
    base_url = reverse("listings:search_results")
    if not cleaned_params:
        return base_url
    return f"{base_url}?{urlencode(cleaned_params)}"


def _build_search_relevance_score(query: str):
    return (
        Case(
            When(title__iexact=query, then=Value(120)),
            default=Value(0),
            output_field=IntegerField(),
        )
        + Case(
            When(title__istartswith=query, then=Value(90)),
            default=Value(0),
            output_field=IntegerField(),
        )
        + Case(
            When(title__icontains=query, then=Value(60)),
            default=Value(0),
            output_field=IntegerField(),
        )
        + Case(
            When(description__icontains=query, then=Value(25)),
            default=Value(0),
            output_field=IntegerField(),
        )
        + Case(
            When(category__name__icontains=query, then=Value(15)),
            default=Value(0),
            output_field=IntegerField(),
        )
        + Case(
            When(location__name__icontains=query, then=Value(10)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )


def _build_search_suggestions(query: str):
    search_term = query.strip()
    if not search_term:
        return []

    suggestions = []
    seen = set()

    title_matches = (
        Item.objects.filter(is_visible=True, title__icontains=search_term)
        .order_by("-created_at")
        .select_related("category")
    )
    for item in title_matches:
        key = ("title", item.title.lower())
        if key in seen:
            continue
        suggestions.append(
            {
                "label": item.title,
                "hint": "Matching item title",
                "url": _search_url_for_params(q=item.title, sort="relevance"),
            }
        )
        seen.add(key)
        if len(suggestions) >= 3:
            break

    category_matches = Category.objects.filter(is_active=True, name__icontains=search_term).order_by("name")[:2]
    for category in category_matches:
        key = ("category", category.slug)
        if key in seen:
            continue
        suggestions.append(
            {
                "label": category.name,
                "hint": "Filter by category",
                "url": _search_url_for_params(category=category.slug, sort="newest"),
            }
        )
        seen.add(key)

    location_matches = CampusLocation.objects.filter(is_active=True, name__icontains=search_term).order_by("name")[:2]
    for location in location_matches:
        key = ("location", location.code)
        if key in seen:
            continue
        suggestions.append(
            {
                "label": location.name,
                "hint": "Filter by location",
                "url": _search_url_for_params(location=location.code, sort="newest"),
            }
        )
        seen.add(key)

    return suggestions[:6]


def _get_trending_categories():
    return (
        Category.objects.filter(is_active=True, items__is_visible=True)
        .annotate(
            visible_item_count=Count(
                "items",
                filter=Q(items__is_visible=True),
                distinct=True,
            )
        )
        .filter(visible_item_count__gt=0)
        .order_by("-visible_item_count", "name")[:5]
    )


def search_results_view(request):
    q = (request.GET.get("q") or "").strip()
    category_slug = (request.GET.get("category") or "").strip()
    location_code = (request.GET.get("location") or "").strip()
    status = (request.GET.get("status") or "").strip()
    requested_sort = (request.GET.get("sort") or "newest").strip()
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()
    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None
    selected_category = Category.objects.filter(is_active=True, slug=category_slug).first() if category_slug else None
    selected_location = CampusLocation.objects.filter(is_active=True, code=location_code).first() if location_code else None
    sort = requested_sort if requested_sort in SEARCH_SORT_LABELS else "newest"
    if sort == "event_date":
        sort = "event_date_desc"
    if sort == "relevance" and not q:
        sort = "newest"

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
    if date_from:
        items_qs = items_qs.filter(event_date__date__gte=date_from)
    if date_to:
        items_qs = items_qs.filter(event_date__date__lte=date_to)

    if sort == "relevance":
        items_qs = items_qs.annotate(
            relevance_score=_build_search_relevance_score(q)
        ).order_by("-relevance_score", "-event_date", "-created_at")
    elif sort == "oldest":
        items_qs = items_qs.order_by("created_at")
    elif sort == "event_date_desc":
        items_qs = items_qs.order_by("-event_date")
    elif sort == "event_date_asc":
        items_qs = items_qs.order_by("event_date")
    else:
        items_qs = items_qs.order_by("-created_at")

    paginator = Paginator(items_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_chips = []
    if q:
        query_chips.append({"label": "q", "value": q})
    if category_slug:
        query_chips.append({"label": "category", "value": selected_category.name if selected_category else category_slug})
    if location_code:
        query_chips.append({"label": "location", "value": selected_location.name if selected_location else location_code})
    if status:
        query_chips.append({"label": "status", "value": status})
    if date_from_raw:
        query_chips.append({"label": "from", "value": date_from_raw})
    if date_to_raw:
        query_chips.append({"label": "to", "value": date_to_raw})
    if sort != "newest":
        query_chips.append({"label": "sort", "value": SEARCH_SORT_LABELS.get(sort, sort)})

    search_suggestions = _build_search_suggestions(q)
    pagination_query = urlencode(
        {
            key: value
            for key, value in {
                "q": q,
                "category": category_slug,
                "location": location_code,
                "status": status,
                "sort": sort,
                "date_from": date_from_raw,
                "date_to": date_to_raw,
            }.items()
            if value not in ("", None)
        }
    )

    context = {
        "page_obj": page_obj,
        "items": page_obj.object_list,
        "categories": Category.objects.filter(is_active=True),
        "locations": CampusLocation.objects.filter(is_active=True),
        "trending_categories": _get_trending_categories(),
        "search_suggestions": search_suggestions,
        "search_hint_values": [suggestion["label"] for suggestion in search_suggestions],
        "sort_options": SEARCH_SORT_OPTIONS,
        "active_sort_label": SEARCH_SORT_LABELS.get(sort, "Newest first"),
        "pagination_query": pagination_query,
        "query_chips": query_chips,
        "filters": {
            "q": q,
            "category": category_slug,
            "location": location_code,
            "status": status,
            "sort": sort,
            "date_from": date_from_raw,
            "date_to": date_to_raw,
        },
        "result_count": paginator.count,
    }

    has_search_filters = any(
        [
            q,
            category_slug,
            location_code,
            status,
            date_from_raw,
            date_to_raw,
            sort != "newest",
            request.GET.get("page"),
        ]
    )
    if has_search_filters:
        track_activity(
            request,
            UserActivity.ActivityType.SEARCH,
            search_query=q,
            metadata={
                "category": selected_category.name if selected_category else "",
                "category_slug": category_slug,
                "location": selected_location.name if selected_location else "",
                "location_code": location_code,
                "status": status,
                "sort": sort,
                "date_from": date_from_raw,
                "date_to": date_to_raw,
                "result_count": paginator.count,
            },
        )
    else:
        track_activity(
            request,
            UserActivity.ActivityType.PAGE_VIEW,
            metadata={"page": "search"},
        )
    return render(request, "listings/search_results.html", context)


def item_detail_view(request, pk: int):
    item = get_object_or_404(
        Item.objects.filter(is_visible=True)
        .select_related("category", "location", "reporter")
        .prefetch_related("images"),
        pk=pk,
    )

    is_guest = not request.user.is_authenticated
    claim_url = None
    if request.user.is_authenticated:
        can_claim_item = (
            item.status == Item.Status.LOST
            and item.reporter_id != request.user.id
        )
        if can_claim_item:
            try:
                claim_url = reverse("listings:claim_create", kwargs={"item_id": item.id})
            except NoReverseMatch:
                claim_url = None
    login_url = reverse("users:login")
    register_url = reverse("users:register")

    context = {
        "item": item,
        "images": item.images.all(),
        "is_guest": is_guest,
        "claim_url": claim_url,
        "contact_url": reverse("chat:contact_owner", kwargs={"item_id": item.pk}) if request.user.is_authenticated and item.reporter_id != request.user.id else None,
        "login_url": login_url,
        "register_url": register_url,
        "search_url": reverse("listings:search_results"),
        "is_owner": request.user.is_authenticated and item.reporter_id == request.user.id,
        "edit_url": reverse("listings:item_edit", kwargs={"pk": item.pk}) if request.user.is_authenticated and item.reporter_id == request.user.id else None,
        "delete_url": reverse("listings:item_delete", kwargs={"pk": item.pk}) if request.user.is_authenticated and item.reporter_id == request.user.id else None,
    }
    track_activity(
        request,
        UserActivity.ActivityType.ITEM_VIEW,
        item=item,
        metadata={
            "status": item.status,
            "item_type": item.item_type,
            "is_owner": request.user.is_authenticated and item.reporter_id == request.user.id,
        },
    )
    return render(request, "listings/item_detail.html", context)


@login_required
def report_lost_item_view(request):
    form = ReportLostItemForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.reporter = request.user
            item.item_type = Item.ItemType.LOST
            item.status = Item.Status.LOST
            item.save()

            for photo in request.FILES.getlist("photos")[: ReportLostItemForm.max_files]:
                ItemImage.objects.create(
                    item=item,
                    image=photo,
                    uploaded_by=request.user,
                )

        track_activity(
            request,
            UserActivity.ActivityType.ITEM_REPORT,
            item=item,
            metadata={
                "item_type": item.item_type,
                "status": item.status,
                "photo_count": item.images.count(),
            },
        )

        return redirect(reverse("listings:item_detail_public", kwargs={"pk": item.pk}))

    context = _build_report_page_context(form=form, item_type=Item.ItemType.LOST)
    return render(request, "listings/report_lost_item.html", context)


@login_required
def report_found_item_view(request):
    form = ReportFoundItemForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.reporter = request.user
            item.item_type = Item.ItemType.FOUND
            item.status = Item.Status.FOUND
            item.save()

            for photo in request.FILES.getlist("photos")[: ReportFoundItemForm.max_files]:
                ItemImage.objects.create(
                    item=item,
                    image=photo,
                    uploaded_by=request.user,
                )

        track_activity(
            request,
            UserActivity.ActivityType.ITEM_REPORT,
            item=item,
            metadata={
                "item_type": item.item_type,
                "status": item.status,
                "photo_count": item.images.count(),
            },
        )

        return redirect(reverse("listings:item_detail_public", kwargs={"pk": item.pk}))

    context = _build_report_page_context(form=form, item_type=Item.ItemType.FOUND)
    return render(request, "listings/report_lost_item.html", context)


@login_required
def claim_create_view(request, item_id: int):
    item = get_object_or_404(
        Item.objects.filter(is_visible=True)
        .select_related("category", "location")
        .prefetch_related("images"),
        pk=item_id,
    )

    existing_claim = Claim.objects.filter(item=item, claimant=request.user).first()
    claim_restriction_message = None
    if item.status != Item.Status.LOST:
        claim_restriction_message = "Only items with Lost status can be claimed."
    elif item.reporter_id == request.user.id:
        claim_restriction_message = "You cannot claim your own reported item."
    elif existing_claim:
        claim_restriction_message = "You already submitted a claim for this item."

    if request.method == "POST":
        form = ClaimCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            if claim_restriction_message:
                form.add_error(None, claim_restriction_message)
            else:
                with transaction.atomic():
                    where_lost_location = form.cleaned_data["where_lost_location"]
                    description = (
                        f"Full name: {form.cleaned_data['full_name']}\n"
                        f"Email: {form.cleaned_data['email']}\n"
                        f"Relationship to item: {form.cleaned_data['relationship_to_item']}\n"
                        f"Where lost: {where_lost_location.name}\n\n"
                        f"Claim details:\n{form.cleaned_data['detailed_description']}"
                    )
                    claim = Claim.objects.create(
                        item=item,
                        claimant=request.user,
                        description=description,
                    )

                    for uploaded_file in form.cleaned_data["proof_files"]:
                        ClaimProof.objects.create(
                            claim=claim,
                            file=uploaded_file,
                        )

                track_activity(
                    request,
                    UserActivity.ActivityType.CLAIM_SUBMISSION,
                    item=item,
                    metadata={
                        "claim_id": claim.id,
                        "relationship_to_item": form.cleaned_data["relationship_to_item"],
                        "proof_count": claim.proofs.count(),
                    },
                )

                return redirect("listings:my_claims")
    else:
        form = ClaimCreateForm(user=request.user)

    status_badge_map = {
        Item.Status.FOUND: "text-bg-success",
        Item.Status.LOST: "text-bg-warning",
        Item.Status.CLAIMED: "text-bg-primary",
        Item.Status.RETURNED: "text-bg-secondary",
    }
    context = {
        "item": item,
        "form": form,
        "item_images": item.images.all(),
        "show_summary_loading": request.GET.get("loading") == "1",
        "status_badge_class": status_badge_map.get(item.status, "text-bg-secondary"),
        "item_details_url": reverse("listings:item_detail_public", kwargs={"pk": item.id}),
        "my_claims_url": reverse("listings:my_claims"),
        "logout_url": reverse("users:logout"),
        "home_url": reverse("core:home"),
        "search_url": reverse("listings:search_results"),
        "claim_restriction_message": claim_restriction_message,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Item Details", "url": reverse("listings:item_detail_public", kwargs={"pk": item.id}), "active": False},
            {"label": "Claim Item", "url": None, "active": True},
        ],
    }
    return render(request, "listings/claim_create.html", context)


@login_required
def my_claims_view(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip().upper()
    sort = (request.GET.get("sort") or "newest").strip().lower()
    state = (request.GET.get("state") or "").strip().lower()

    all_claims_qs = Claim.objects.filter(claimant=request.user).select_related("item")

    summary_counts = {
        "pending": all_claims_qs.filter(status=Claim.Status.PENDING).count(),
        "approved": all_claims_qs.filter(status=Claim.Status.APPROVED).count(),
        "rejected": all_claims_qs.filter(status=Claim.Status.REJECTED).count(),
    }

    claims_qs = all_claims_qs
    if q:
        search_query = (
            Q(item__title__icontains=q)
            | Q(description__icontains=q)
        )
        if q.isdigit():
            search_query |= Q(pk=int(q))
        claims_qs = claims_qs.filter(
            search_query
        )

    valid_statuses = {Claim.Status.PENDING, Claim.Status.APPROVED, Claim.Status.REJECTED}
    if status_filter in valid_statuses:
        claims_qs = claims_qs.filter(status=status_filter)

    if sort == "oldest":
        claims_qs = claims_qs.order_by("created_at")
    elif sort == "updated":
        claims_qs = claims_qs.order_by("-updated_at")
    else:
        claims_qs = claims_qs.order_by("-created_at")

    paginator = Paginator(claims_qs, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "claims": page_obj.object_list,
        "page_obj": page_obj,
        "summary_counts": summary_counts,
        "filters": {
            "q": q,
            "status": status_filter,
            "sort": sort,
        },
        "show_loading_state": state == "loading",
        "show_error_state": state == "error",
        "my_claims_url": reverse("listings:my_claims"),
        "received_claims_url": reverse("listings:my_received_claims"),
        "my_items_url": reverse("listings:my_items"),
        "search_url": reverse("listings:search_results"),
        "home_url": reverse("core:home"),
        "logout_url": reverse("users:logout"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "My Claims", "url": None, "active": True},
        ],
    }
    return render(request, "listings/my_claims.html", context)


@login_required
def my_received_claims_view(request):
    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip().upper()
    sort = (request.GET.get("sort") or "newest").strip().lower()

    all_claims_qs = (
        Claim.objects.filter(item__reporter=request.user)
        .select_related("item", "claimant")
    )

    claims_qs = all_claims_qs
    if q:
        search_query = (
            Q(item__title__icontains=q)
            | Q(description__icontains=q)
            | Q(claimant__username__icontains=q)
            | Q(claimant__email__icontains=q)
        )
        if q.isdigit():
            search_query |= Q(pk=int(q))
        claims_qs = claims_qs.filter(search_query)

    valid_statuses = {Claim.Status.PENDING, Claim.Status.APPROVED, Claim.Status.REJECTED}
    if status_filter in valid_statuses:
        claims_qs = claims_qs.filter(status=status_filter)

    if sort == "oldest":
        claims_qs = claims_qs.order_by("created_at")
    elif sort == "updated":
        claims_qs = claims_qs.order_by("-updated_at")
    else:
        claims_qs = claims_qs.order_by("-created_at")

    paginator = Paginator(claims_qs, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "claims": page_obj.object_list,
        "page_obj": page_obj,
        "filters": {
            "q": q,
            "status": status_filter,
            "sort": sort,
        },
        "my_claims_url": reverse("listings:my_claims"),
        "received_claims_url": reverse("listings:my_received_claims"),
        "my_items_url": reverse("listings:my_items"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "Claims Received", "url": None, "active": True},
        ],
    }
    return render(request, "listings/my_received_claims.html", context)


@login_required
def my_items_view(request):
    items_qs = (
        Item.objects.filter(reporter=request.user, is_visible=True)
        .select_related("category", "location")
        .annotate(
            pending_claims_count=Count(
                "claims",
                filter=Q(claims__status=Claim.Status.PENDING),
                distinct=True,
            )
        )
        .order_by("-created_at")
    )

    paginator = Paginator(items_qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "items": page_obj.object_list,
        "page_obj": page_obj,
        "my_claims_url": reverse("listings:my_claims"),
        "received_claims_url": reverse("listings:my_received_claims"),
        "my_items_url": reverse("listings:my_items"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "My Items", "url": None, "active": True},
        ],
    }
    return render(request, "listings/my_items.html", context)

@login_required
def item_edit_view(request, pk: int):
    item = get_object_or_404(
        Item.objects.filter(is_visible=True).select_related("category", "location", "reporter"),
        pk=pk,
    )

    if item.reporter_id != request.user.id:
        raise Http404("Item not found.")

    form = ItemEditForm(request.POST or None, request.FILES or None, instance=item)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            updated_item = form.save(commit=False)
            if updated_item.status in {Item.Status.LOST, Item.Status.FOUND}:
                updated_item.claimed_by = None
            updated_item.save()
            form.save_m2m()

            for image in form.cleaned_data["remove_images"]:
                image.delete()

            for photo in request.FILES.getlist("photos")[: ItemEditForm.max_files]:
                ItemImage.objects.create(
                    item=updated_item,
                    image=photo,
                    uploaded_by=request.user,
                )

        messages.success(request, "Item updated successfully.")
        return redirect("listings:item_detail_public", pk=item.pk)

    context = {
        "item": item,
        "form": form,
        "images": item.images.all(),
        "cancel_url": reverse("listings:my_items"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "My Items", "url": reverse("listings:my_items"), "active": False},
            {"label": f"Edit #{item.id}", "url": None, "active": True},
        ],
    }
    return render(request, "listings/item_edit.html", context)


@login_required
def item_delete_view(request, pk: int):
    item = get_object_or_404(
        Item.objects.filter(is_visible=True).select_related("reporter"),
        pk=pk,
    )

    if item.reporter_id != request.user.id:
        raise Http404("Item not found.")

    if request.method == "POST":
        item.is_visible = False
        item.save(update_fields=["is_visible", "updated_at"])
        messages.success(request, "Item deleted successfully.")
        return redirect("listings:my_items")

    context = {
        "item": item,
        "cancel_url": reverse("listings:my_items"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "My Items", "url": reverse("listings:my_items"), "active": False},
            {"label": f"Delete #{item.id}", "url": None, "active": True},
        ],
    }
    return render(request, "listings/item_delete_confirm.html", context)


def faq_view(request):
    context = {
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "FAQ", "url": None, "active": True},
        ],
    }
    return render(request, "listings/faq.html", context)


@login_required
def claim_detail_view(request, claim_id: int):
    claim = get_object_or_404(
        Claim.objects.select_related("item", "claimant", "item__reporter", "reviewer").prefetch_related("proofs"),
        pk=claim_id,
    )

    can_view = (
        request.user.is_staff
        or claim.claimant_id == request.user.id
        or claim.item.reporter_id == request.user.id
    )
    if not can_view:
        raise Http404("Claim not found.")

    context = _build_claim_detail_context(request, claim)
    return render(request, "listings/claim_detail.html", context)


@login_required
def claim_review_view(request, claim_id: int):
    claim = get_object_or_404(
        Claim.objects.select_related("item", "claimant", "item__reporter", "reviewer").prefetch_related("proofs"),
        pk=claim_id,
    )

    if not _user_can_review_claim(request.user, claim):
        raise Http404("Claim not found.")

    if request.method != "POST":
        return redirect("listings:claim_detail", claim_id=claim.id)

    if claim.status != Claim.Status.PENDING:
        messages.info(request, "This claim has already been reviewed.")
        return redirect("listings:claim_detail", claim_id=claim.id)

    review_form = ClaimReviewForm(request.POST)
    if not review_form.is_valid():
        context = _build_claim_detail_context(request, claim, review_form=review_form)
        return render(request, "listings/claim_detail.html", context, status=200)

    decision = review_form.cleaned_data["decision"]
    reviewer_notes = review_form.cleaned_data["reviewer_notes"]

    try:
        review_claim(
            claim=claim,
            reviewer=request.user,
            decision=decision,
            reviewer_notes=reviewer_notes,
        )
    except ClaimReviewError as exc:
        messages.error(request, str(exc))
        return redirect("listings:claim_detail", claim_id=claim.id)

    track_activity(
        request,
        UserActivity.ActivityType.CLAIM_REVIEW,
        item=claim.item,
        metadata={
            "claim_id": claim.id,
            "decision": decision,
            "via": "claim_detail",
        },
    )

    if decision == ClaimReviewForm.DECISION_APPROVE:
        messages.success(request, "Claim approved. The item is now marked as claimed.")
    else:
        messages.success(request, "Claim rejected.")

    return redirect("listings:claim_detail", claim_id=claim.id)
