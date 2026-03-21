from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class CampusLocation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=60, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Item(models.Model):
    class ItemType(models.TextChoices):
        LOST = "LOST", "Lost"
        FOUND = "FOUND", "Found"

    class Status(models.TextChoices):
        LOST = "LOST", "Lost"
        FOUND = "FOUND", "Found"
        CLAIMED = "CLAIMED", "Claimed"
        RETURNED = "RETURNED", "Returned"

    reporter = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="reported_items",
    )
    item_type = models.CharField(max_length=10, choices=ItemType.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="items",
    )
    location = models.ForeignKey(
        CampusLocation,
        on_delete=models.PROTECT,
        related_name="items",
    )
    event_date = models.DateTimeField(help_text="Date when the item was lost/found.")
    claimed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="claimed_items",
        null=True,
        blank=True,
    )
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["item_type", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["event_date"]),
        ]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        if self.event_date and self.event_date > timezone.now():
            raise ValidationError({"event_date": "The event date cannot be in the future."})


class ItemImage(models.Model):
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="items/%Y/%m/%d")
    alt_text = models.CharField(max_length=160, blank=True)
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="uploaded_item_images",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Image for item #{self.item_id}"


class Claim(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    claimant = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="claims",
    )
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    student_id = models.CharField(max_length=50, blank=True)
    relationship_to_item = models.CharField(max_length=40, blank=True)
    lost_date = models.DateTimeField(null=True, blank=True)
    lost_location = models.ForeignKey(
        CampusLocation,
        on_delete=models.PROTECT,
        related_name="claims_lost_here",
        null=True,
        blank=True,
    )
    lost_location_details = models.CharField(max_length=255, blank=True)
    student_card_image = models.ImageField(
        upload_to="claims/student_cards/%Y/%m/%d",
        blank=True,
    )
    description = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewer = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="reviewed_claims",
        null=True,
        blank=True,
    )
    reviewer_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["item", "claimant"], name="uniq_claim_per_user_item"),
        ]

    def __str__(self) -> str:
        return f"Claim #{self.pk} for item #{self.item_id}"


class ClaimProof(models.Model):
    claim = models.ForeignKey(
        Claim,
        on_delete=models.CASCADE,
        related_name="proofs",
    )
    file = models.FileField(upload_to="claims/proofs/%Y/%m/%d")
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Proof #{self.pk} for claim #{self.claim_id}"
