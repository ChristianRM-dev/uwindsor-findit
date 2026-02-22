from __future__ import annotations

import io
import os
import shutil
import tempfile
from datetime import timedelta

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import CampusLocation, Category, Item, ItemImage


class ReportLostItemViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="findit-test-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        self.url = reverse("listings:report_lost_item")
        self.dashboard_url = reverse("core:dashboard")

        User = get_user_model()
        self.user = User.objects.create_user(
            username="reporter@uwindsor.ca",
            email="reporter@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Electronics", slug="electronics", is_active=True)
        self.location = CampusLocation.objects.create(name="Leddy Library", code="leddy-library", is_active=True)

    def _valid_image_file(self, name: str = "photo.png") -> SimpleUploadedFile:
        image = Image.new("RGB", (50, 50), color=(120, 120, 120))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def _oversized_png(self, name: str = "huge.png") -> SimpleUploadedFile:
        # Random RGB bytes reduce PNG compression and produce a reliably large file.
        random_pixels = os.urandom(2200 * 2200 * 3)
        image = Image.frombytes("RGB", (2200, 2200), random_pixels)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_authenticated_get_renders_form(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report a Lost Item")
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="category"')
        self.assertContains(response, 'name="event_date"')
        self.assertContains(response, 'name="location"')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="photos"')
        self.assertContains(response, f'href="{self.dashboard_url}"')

    def test_creates_lost_item_and_image_and_redirects(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Black backpack",
            "category": str(self.category.pk),
            "event_date": (timezone.now() - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Lost near the second floor.",
        }
        photo = self._valid_image_file()

        response = self.client.post(self.url, data={**payload, "photos": photo}, format="multipart")

        form_errors = response.context["form"].errors if getattr(response, "context", None) else None
        self.assertEqual(response.status_code, 302, msg=form_errors)
        created_item = Item.objects.get(title="Black backpack")
        self.assertEqual(created_item.item_type, Item.ItemType.LOST)
        self.assertEqual(created_item.status, Item.Status.LOST)
        self.assertEqual(created_item.reporter, self.user)
        self.assertEqual(response.url, reverse("listings:item_detail_public", kwargs={"pk": created_item.pk}))
        self.assertEqual(ItemImage.objects.filter(item=created_item).count(), 1)

    def test_rejects_future_date(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Laptop",
            "category": str(self.category.pk),
            "event_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Future date should fail.",
        }

        response = self.client.post(self.url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Date lost cannot be in the future.")
        self.assertEqual(Item.objects.count(), 0)

    def test_rejects_more_than_five_photos(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Wallet",
            "category": str(self.category.pk),
            "event_date": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Too many files should fail.",
            "photos": [self._valid_image_file(f"img-{idx}.png") for idx in range(6)],
        }

        response = self.client.post(self.url, data=payload, format="multipart")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You can upload up to 5 photos.")
        self.assertEqual(Item.objects.count(), 0)

    def test_rejects_invalid_extension(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        bad_file = SimpleUploadedFile("notes.txt", b"not-an-image", content_type="text/plain")
        payload = {
            "title": "Headphones",
            "category": str(self.category.pk),
            "event_date": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Invalid extension should fail.",
            "photos": bad_file,
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Item.objects.count(), 0)
        self.assertContains(response, "only JPG/PNG files are allowed")

    def test_rejects_oversized_photo(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Jacket",
            "category": str(self.category.pk),
            "event_date": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Oversized file should fail.",
            "photos": self._oversized_png(),
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Item.objects.count(), 0)
        self.assertContains(response, "file size must be &lt;= 5MB")

    def test_form_querysets_include_only_active_catalogs(self):
        Category.objects.create(name="Inactive category", slug="inactive-category", is_active=False)
        CampusLocation.objects.create(name="Inactive location", code="inactive-location", is_active=False)

        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        form = response.context["form"]
        category_names = set(form.fields["category"].queryset.values_list("name", flat=True))
        location_names = set(form.fields["location"].queryset.values_list("name", flat=True))

        self.assertIn("Electronics", category_names)
        self.assertNotIn("Inactive category", category_names)
        self.assertIn("Leddy Library", location_names)
        self.assertNotIn("Inactive location", location_names)
