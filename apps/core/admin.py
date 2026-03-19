from django.contrib import admin

from apps.core.models import UserActivity


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "activity_type",
        "user",
        "item",
        "search_query",
        "page_path",
        "created_at",
    )
    list_filter = ("activity_type", "created_at")
    search_fields = (
        "user__email",
        "user__username",
        "item__title",
        "search_query",
        "page_path",
        "session_key",
    )
    autocomplete_fields = ("user", "item")
    readonly_fields = ("created_at",)
    list_select_related = ("user", "item")
