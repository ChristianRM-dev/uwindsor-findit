from django.contrib import admin

from apps.listings.models import CampusLocation, Category, Claim, ClaimProof, Item, ItemImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")


@admin.register(CampusLocation)
class CampusLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("title", "item_type", "status", "category", "location", "reporter", "created_at")
    list_filter = ("item_type", "status", "category", "location")
    search_fields = ("title", "description")
    inlines = [ItemImageInline]


class ClaimProofInline(admin.TabularInline):
    model = ClaimProof
    extra = 0


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("item", "claimant", "status", "reviewer", "created_at")
    list_filter = ("status",)
    search_fields = ("description", "item__title", "claimant__email")
    inlines = [ClaimProofInline]
