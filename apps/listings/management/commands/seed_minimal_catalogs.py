from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.listings.models import CampusLocation, Category


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


DEFAULT_LOCATIONS = [
    ("Leddy Library", "leddy-library"),
    ("Odette Building", "odette-building"),
    ("CAW Student Centre", "caw-student-centre"),
    ("Lambton Tower", "lambton-tower"),
    ("Toldo Health Education Centre", "toldo-health-centre"),
    ("Human Kinetics Building", "human-kinetics"),
    ("Assumption Hall", "assumption-hall"),
    ("Engineering Building", "engineering-building"),
]


class Command(BaseCommand):
    help = "Seed minimal catalogs for categories and campus locations."

    @transaction.atomic
    def handle(self, *args, **options):
        categories_created = 0
        locations_created = 0

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

        for location_name, location_code in DEFAULT_LOCATIONS:
            location, created = CampusLocation.objects.get_or_create(
                name=location_name,
                defaults={"code": location_code, "is_active": True},
            )
            if not created and location.code != location_code:
                location.code = location_code
                location.save(update_fields=["code"])
            if created:
                locations_created += 1

        self.stdout.write(self.style.SUCCESS("Seed completed."))
        self.stdout.write(f"Categories created: {categories_created}")
        self.stdout.write(f"Locations created: {locations_created}")
