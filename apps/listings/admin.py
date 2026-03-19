from django.contrib import admin, messages

from apps.listings.models import CampusLocation, Category, Claim, ClaimProof, Item, ItemImage
from apps.listings.services import ClaimReviewError, review_claim


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 0
    fields = ("image", "alt_text", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("uploaded_by",)


class ClaimProofInline(admin.TabularInline):
    model = ClaimProof
    extra = 0
    fields = ("file", "description", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(CampusLocation)
class CampusLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "item_type",
        "status",
        "reporter",
        "category",
        "location",
        "claimed_by",
        "is_visible",
        "created_at",
    )
    list_filter = ("item_type", "status", "is_visible", "category", "location", "created_at")
    search_fields = (
        "title",
        "description",
        "reporter__email",
        "reporter__username",
        "claimed_by__email",
        "claimed_by__username",
    )
    autocomplete_fields = ("reporter", "category", "location", "claimed_by")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("reporter", "category", "location", "claimed_by")
    date_hierarchy = "created_at"
    inlines = [ItemImageInline]
    actions = ("mark_selected_visible", "mark_selected_hidden", "mark_selected_returned")

    @admin.action(description="Mark selected items as visible")
    def mark_selected_visible(self, request, queryset):
        updated = queryset.update(is_visible=True)
        self.message_user(request, f"Marked {updated} item(s) as visible.", level=messages.SUCCESS)

    @admin.action(description="Hide selected items")
    def mark_selected_hidden(self, request, queryset):
        updated = queryset.update(is_visible=False)
        self.message_user(request, f"Hid {updated} item(s).", level=messages.SUCCESS)

    @admin.action(description="Mark selected items as returned")
    def mark_selected_returned(self, request, queryset):
        updated = queryset.update(status=Item.Status.RETURNED)
        self.message_user(request, f"Marked {updated} item(s) as returned.", level=messages.SUCCESS)


@admin.register(ItemImage)
class ItemImageAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "uploaded_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("item__title", "uploaded_by__email", "uploaded_by__username", "alt_text")
    autocomplete_fields = ("item", "uploaded_by")
    readonly_fields = ("created_at",)
    list_select_related = ("item", "uploaded_by")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "claimant",
        "status",
        "reviewer",
        "reviewed_at",
        "proof_count",
        "created_at",
    )
    list_filter = ("status", "created_at", "reviewed_at", "item__status")
    search_fields = (
        "item__title",
        "claimant__email",
        "claimant__username",
        "description",
        "reviewer_notes",
    )
    autocomplete_fields = ("item", "claimant", "reviewer")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    list_select_related = ("item", "claimant", "reviewer")
    date_hierarchy = "created_at"
    inlines = [ClaimProofInline]
    actions = ("approve_selected_claims", "reject_selected_claims")

    @admin.display(description="Proofs")
    def proof_count(self, obj):
        return obj.proofs.count()

    @admin.action(description="Approve selected pending claims")
    def approve_selected_claims(self, request, queryset):
        approved = 0
        skipped = 0

        for claim in queryset.select_related("item", "claimant").order_by("item_id", "created_at"):
            try:
                review_claim(
                    claim=claim,
                    reviewer=request.user,
                    decision="approve",
                    reviewer_notes="Approved in Django admin.",
                )
                approved += 1
            except ClaimReviewError:
                skipped += 1

        if approved:
            self.message_user(request, f"Approved {approved} claim(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} claim(s) that were already reviewed or no longer eligible.",
                level=messages.WARNING,
            )

    @admin.action(description="Reject selected pending claims")
    def reject_selected_claims(self, request, queryset):
        rejected = 0
        skipped = 0

        for claim in queryset.select_related("item", "claimant").order_by("item_id", "created_at"):
            try:
                review_claim(
                    claim=claim,
                    reviewer=request.user,
                    decision="reject",
                    reviewer_notes="Rejected in Django admin.",
                )
                rejected += 1
            except ClaimReviewError:
                skipped += 1

        if rejected:
            self.message_user(request, f"Rejected {rejected} claim(s).", level=messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} claim(s) that were already reviewed.",
                level=messages.WARNING,
            )


@admin.register(ClaimProof)
class ClaimProofAdmin(admin.ModelAdmin):
    list_display = ("id", "claim", "description", "created_at")
    list_filter = ("created_at",)
    search_fields = ("claim__item__title", "claim__claimant__email", "description")
    autocomplete_fields = ("claim",)
    readonly_fields = ("created_at",)
    list_select_related = ("claim",)
