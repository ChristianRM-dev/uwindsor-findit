from django.contrib import admin

from apps.core.models import UserActivity


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("activity_type", "user", "item", "page_path", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("user__email", "search_query", "page_path")
