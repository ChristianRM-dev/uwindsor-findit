from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse

from apps.listings.forms import ClaimCreateForm, ReportLostItemForm
from apps.listings.models import CampusLocation, Category, Claim, ClaimProof, Item
from apps.listings.models import ItemImage


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
        "login_url": login_url,
        "register_url": register_url,
        "search_url": reverse("listings:search_results"),
    }
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

        return redirect(reverse("listings:item_detail_public", kwargs={"pk": item.pk}))

    context = {
        "form": form,
        "cancel_url": reverse("core:dashboard"),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": "Report Lost Item", "url": None, "active": True},
        ],
    }
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
def claim_detail_view(request, claim_id: int):
    claim = get_object_or_404(
        Claim.objects.select_related("item", "claimant", "item__reporter").prefetch_related("proofs"),
        pk=claim_id,
    )

    can_view = (
        request.user.is_staff
        or claim.claimant_id == request.user.id
        or claim.item.reporter_id == request.user.id
    )
    if not can_view:
        raise Http404("Claim not found.")

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

    context = {
        "claim": claim,
        "proofs": proof_entries,
        "image_proofs": image_proofs,
        "non_image_proofs": non_image_proofs,
        "parsed_claim": _parse_claim_description(claim.description),
        "item_details_url": reverse("listings:item_detail_public", kwargs={"pk": claim.item_id}),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Dashboard", "url": reverse("core:dashboard"), "active": False},
            {"label": parent_label, "url": parent_url, "active": False},
            {"label": f"Claim #{claim.id}", "url": None, "active": True},
        ],
    }
    return render(request, "listings/claim_detail.html", context)
