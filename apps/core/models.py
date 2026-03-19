from django.db import models


class UserActivity(models.Model):
    class ActivityType(models.TextChoices):
        PAGE_VIEW = "PAGE_VIEW", "Page view"
        SEARCH = "SEARCH", "Search"
        ITEM_VIEW = "ITEM_VIEW", "Item view"
        ITEM_REPORT = "ITEM_REPORT", "Item report"
        CLAIM_SUBMISSION = "CLAIM_SUBMISSION", "Claim submission"
        CLAIM_REVIEW = "CLAIM_REVIEW", "Claim review"
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

    @property
    def display_title(self) -> str:
        if self.activity_type == self.ActivityType.SEARCH:
            if self.search_query:
                return f'Searched for "{self.search_query}"'
            return "Used item search filters"

        if self.activity_type == self.ActivityType.ITEM_VIEW:
            return f"Viewed item: {self.item.title}" if self.item else "Viewed an item"

        if self.activity_type == self.ActivityType.ITEM_REPORT:
            item_type = (self.metadata or {}).get("item_type", "item").lower()
            if self.item:
                return f"Reported {item_type} item: {self.item.title}"
            return f"Reported {item_type} item"

        if self.activity_type == self.ActivityType.CLAIM_SUBMISSION:
            return f"Submitted a claim for {self.item.title}" if self.item else "Submitted a claim"

        if self.activity_type == self.ActivityType.CLAIM_REVIEW:
            decision = ((self.metadata or {}).get("decision") or "reviewed").capitalize()
            if self.item:
                return f"{decision} claim for {self.item.title}"
            return f"{decision} a claim"

        if self.activity_type == self.ActivityType.MESSAGE:
            return f"Sent a message about {self.item.title}" if self.item else "Sent a message"

        page_labels = {
            "/": "Visited home page",
            "/dashboard/": "Visited dashboard",
            "/search": "Opened search",
        }
        return page_labels.get(self.page_path, "Visited a page")

    @property
    def display_detail(self) -> str:
        metadata = self.metadata or {}

        if self.activity_type == self.ActivityType.SEARCH:
            parts = []
            if metadata.get("status"):
                parts.append(str(metadata["status"]).title())
            if metadata.get("category"):
                parts.append(str(metadata["category"]))
            if metadata.get("location"):
                parts.append(str(metadata["location"]))
            if metadata.get("result_count") is not None:
                parts.append(f'{metadata["result_count"]} result(s)')
            return " | ".join(parts)

        if self.activity_type == self.ActivityType.CLAIM_REVIEW and metadata.get("claim_id"):
            return f'Claim #{metadata["claim_id"]}'

        if self.activity_type == self.ActivityType.CLAIM_SUBMISSION and metadata.get("claim_id"):
            return f'Claim #{metadata["claim_id"]}'

        if self.activity_type == self.ActivityType.MESSAGE and metadata.get("context"):
            context_label = str(metadata["context"]).replace("_", " ").title()
            if metadata.get("conversation_id"):
                return f'{context_label} | Conversation #{metadata["conversation_id"]}'
            return context_label

        if self.item:
            return f"Item #{self.item_id}"

        return self.page_path


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CLAIM_SUBMITTED = "CLAIM_SUBMITTED", "Claim submitted"
        CLAIM_APPROVED = "CLAIM_APPROVED", "Claim approved"
        CLAIM_REJECTED = "CLAIM_REJECTED", "Claim rejected"

    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    body = models.TextField()
    link_path = models.CharField(max_length=255, blank=True)
    item = models.ForeignKey(
        "listings.Item",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    claim = models.ForeignKey(
        "listings.Claim",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["notification_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_type} -> {self.recipient}"
