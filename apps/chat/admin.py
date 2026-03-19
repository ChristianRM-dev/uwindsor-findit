from django.contrib import admin

from apps.chat.models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("sender", "content", "is_read", "read_at", "created_at")
    readonly_fields = ("read_at", "created_at")
    autocomplete_fields = ("sender",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "created_by", "participant_count", "updated_at", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("item__title", "created_by__email", "created_by__username", "participants__email")
    autocomplete_fields = ("item", "created_by")
    filter_horizontal = ("participants",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("item", "created_by")
    inlines = [MessageInline]

    @admin.display(description="Participants")
    def participant_count(self, obj):
        return obj.participants.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "message_preview", "is_read", "read_at", "created_at")
    list_filter = ("is_read", "created_at", "read_at")
    search_fields = ("content", "sender__email", "sender__username", "conversation__item__title")
    autocomplete_fields = ("conversation", "sender")
    readonly_fields = ("created_at", "updated_at", "read_at")
    list_select_related = ("conversation", "sender")

    @admin.display(description="Message")
    def message_preview(self, obj):
        if len(obj.content) <= 80:
            return obj.content
        return f"{obj.content[:77]}..."
