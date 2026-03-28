from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.listings.buildings import sync_official_campus_locations
from apps.listings.models import CampusLocation, Category, Item


DEFAULT_CATEGORIES = [
    "Electronics",
    "Clothing",
    "Documents",
    "Accessories",
    "Keys",
    "Bags",
    "Water Bottles",
    "Other",
]

SAMPLE_ITEMS = [
    {
        "title": "Black Wallet with Student ID",
        "item_type": Item.ItemType.LOST,
        "status": Item.Status.LOST,
        "category_name": "Accessories",
        "location_code": "caw-student-centre",
        "days_ago": 2,
        "description": "Black leather wallet with UWindsor card and transit pass.",
    },
    {
        "title": "Silver USB Drive 32GB",
        "item_type": Item.ItemType.FOUND,
        "status": Item.Status.FOUND,
        "category_name": "Electronics",
        "location_code": "leddy-library",
        "days_ago": 1,
        "description": "Found near the second floor study area.",
    },
    {
        "title": "Blue Hydro Flask Bottle",
        "item_type": Item.ItemType.LOST,
        "status": Item.Status.LOST,
        "category_name": "Water Bottles",
        "location_code": "human-kinetics",
        "days_ago": 3,
        "description": "Blue 24oz bottle with stickers.",
    },
    {
        "title": "TI-84 Calculator",
        "item_type": Item.ItemType.FOUND,
        "status": Item.Status.FOUND,
        "category_name": "Electronics",
        "location_code": "engineering-building",
        "days_ago": 5,
        "description": "Calculator found in classroom after evening lecture.",
    },
]


class Command(BaseCommand):
    help = "Seed minimal catalogs (categories, locations) and sample items."

    @transaction.atomic
    def handle(self, *args, **options):
        categories_created = 0
        items_created = 0

        for category_name in DEFAULT_CATEGORIES:
            category, created = Category.objects.get_or_create(
                name=category_name,
                defaults={"slug": slugify(category_name), "is_active": True},
            )
            if not created and category.slug != slugify(category_name):
                category.slug = slugify(category_name)
                category.save(update_fields=["slug"])
            if created:
                categories_created += 1

        location_stats = sync_official_campus_locations()

        user_model = get_user_model()
        reporter = user_model.objects.order_by("id").first()
        if reporter is None:
            reporter, created = user_model.objects.get_or_create(
                email="seed.user@uwindsor.ca",
                defaults={
                    "username": "seed.user@uwindsor.ca",
                    "student_id": "999000111",
                    "is_active": True,
                },
            )
            if created:
                reporter.set_unusable_password()
                reporter.save(update_fields=["password"])

        for sample in SAMPLE_ITEMS:
            category = Category.objects.get(name=sample["category_name"])
            location = CampusLocation.objects.get(code=sample["location_code"])
            event_date = timezone.now() - timedelta(days=sample["days_ago"])

            _, created = Item.objects.get_or_create(
                reporter=reporter,
                title=sample["title"],
                item_type=sample["item_type"],
                defaults={
                    "status": sample["status"],
                    "description": sample["description"],
                    "category": category,
                    "location": location,
                    "event_date": event_date,
                    "is_visible": True,
                },
            )
            if created:
                items_created += 1

        self.stdout.write(self.style.SUCCESS("Seed completed."))
        self.stdout.write(f"Categories created: {categories_created}")
        self.stdout.write(f"Locations created: {location_stats['created']}")
        self.stdout.write(f"Locations renamed: {location_stats['renamed']}")
        self.stdout.write(f"Locations reactivated: {location_stats['reactivated']}")
        self.stdout.write(f"Location duplicates merged: {location_stats['merged_duplicates']}")
        self.stdout.write(f"Items created: {items_created}")
