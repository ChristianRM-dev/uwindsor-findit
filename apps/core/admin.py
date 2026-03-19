from django.contrib import admin
from django.utils import timezone

from apps.core.models import Notification, UserActivity


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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "notification_type",
        "recipient",
        "title",
        "item",
        "claim",
        "is_read",
        "email_sent",
        "created_at",
    )
    list_filter = ("notification_type", "is_read", "email_sent", "created_at")
    search_fields = (
        "recipient__email",
        "recipient__username",
        "title",
        "body",
        "item__title",
        "claim__id",
    )
    autocomplete_fields = ("recipient", "item", "claim")
    readonly_fields = ("created_at", "read_at")
    list_select_related = ("recipient", "item", "claim")
    actions = ("mark_selected_as_read",)

    @admin.action(description="Mark selected notifications as read")
    def mark_selected_as_read(self, request, queryset):
        updated_count = queryset.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        if updated_count:
            self.message_user(request, f"Marked {updated_count} notification(s) as read.")
