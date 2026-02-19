from django.db import models


class UserActivity(models.Model):
    class ActivityType(models.TextChoices):
        PAGE_VIEW = "PAGE_VIEW", "Page view"
        SEARCH = "SEARCH", "Search"
        ITEM_VIEW = "ITEM_VIEW", "Item view"
        MESSAGE = "MESSAGE", "Message"

    user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="activities",
        null=True,
        blank=True,
    )
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    page_path = models.CharField(max_length=255, blank=True)
    search_query = models.CharField(max_length=255, blank=True)
    item = models.ForeignKey(
        "listings.Item",
        on_delete=models.SET_NULL,
        related_name="activity_events",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["activity_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.activity_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
