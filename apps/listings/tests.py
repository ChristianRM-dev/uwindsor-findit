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

from apps.core.models import UserActivity
from apps.listings.models import CampusLocation, Category, Claim, ClaimProof, Item, ItemImage


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
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.ITEM_REPORT,
                item=created_item,
                metadata__item_type=Item.ItemType.LOST,
            ).exists()
        )

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

    def test_event_date_has_max_attr_and_single_help_text(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approximate date is fine.", count=1)
        self.assertNotContains(response, "Date when the item was lost/found.")

        form = response.context["form"]
        event_date_max = form.fields["event_date"].widget.attrs.get("max")
        self.assertIsNotNone(event_date_max)
        self.assertRegex(event_date_max, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


class ReportFoundItemViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="findit-found-test-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        self.url = reverse("listings:report_found_item")
        self.dashboard_url = reverse("core:dashboard")

        User = get_user_model()
        self.user = User.objects.create_user(
            username="finder@uwindsor.ca",
            email="finder@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Accessories", slug="accessories", is_active=True)
        self.location = CampusLocation.objects.create(name="Odette", code="odette", is_active=True)

    def _valid_image_file(self, name: str = "photo.png") -> SimpleUploadedFile:
        image = Image.new("RGB", (50, 50), color=(80, 120, 160))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_authenticated_get_renders_found_form(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report a Found Item")
        self.assertContains(response, "When did you find it?")
        self.assertContains(response, f'href="{self.dashboard_url}"')

    def test_creates_found_item_and_image_and_redirects(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Silver keychain",
            "category": str(self.category.pk),
            "event_date": (timezone.now() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Found near the main lobby desk.",
        }

        response = self.client.post(
            self.url,
            data={**payload, "photos": self._valid_image_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 302)
        created_item = Item.objects.get(title="Silver keychain")
        self.assertEqual(created_item.item_type, Item.ItemType.FOUND)
        self.assertEqual(created_item.status, Item.Status.FOUND)
        self.assertEqual(created_item.reporter, self.user)
        self.assertEqual(ItemImage.objects.filter(item=created_item).count(), 1)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.ITEM_REPORT,
                item=created_item,
                metadata__item_type=Item.ItemType.FOUND,
            ).exists()
        )

    def test_found_form_rejects_future_date(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Campus card",
            "category": str(self.category.pk),
            "event_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Future date should fail.",
        }

        response = self.client.post(self.url, data=payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Date found cannot be in the future.")
        self.assertEqual(Item.objects.count(), 0)


class SearchAndItemActivityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="activity-viewer@uwindsor.ca",
            email="activity-viewer@uwindsor.ca",
            password="StrongPass123!",
        )
        self.owner = User.objects.create_user(
            username="activity-owner@uwindsor.ca",
            email="activity-owner@uwindsor.ca",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(name="Search Docs", slug="search-docs", is_active=True)
        self.location = CampusLocation.objects.create(name="Search Hall", code="search-hall", is_active=True)
        self.item = Item.objects.create(
            reporter=self.owner,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Blue Wallet",
            description="Wallet near admin building.",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.search_url = reverse("listings:search_results")
        self.detail_url = reverse("listings:item_detail_public", kwargs={"pk": self.item.pk})

    def test_search_view_logs_search_activity(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.search_url,
            {
                "q": "wallet",
                "category": self.category.slug,
                "status": Item.Status.LOST,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.SEARCH,
                search_query="wallet",
                metadata__category=self.category.slug,
                metadata__status=Item.Status.LOST,
            ).exists()
        )

    def test_item_detail_logs_item_view_activity(self):
        self.client.force_login(self.user)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.ITEM_VIEW,
                item=self.item,
            ).exists()
        )


class ClaimCreateViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="findit-claim-test-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        User = get_user_model()
        self.user = User.objects.create_user(
            username="claimant@uwindsor.ca",
            email="claimant@uwindsor.ca",
            password="StrongPass123!",
            first_name="Avery",
            last_name="Jones",
        )
        self.reporter = User.objects.create_user(
            username="reporter@uwindsor.ca",
            email="reporter@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Documents", slug="documents", is_active=True)
        self.location = CampusLocation.objects.create(name="Library", code="library", is_active=True)
        self.item = Item.objects.create(
            reporter=self.reporter,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Black Wallet",
            description="Found in study lounge.",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )

        self.url = reverse("listings:claim_create", kwargs={"item_id": self.item.pk})
        self.my_claims_url = reverse("listings:my_claims")

    def _valid_image_file(self, name: str = "proof.png") -> SimpleUploadedFile:
        image = Image.new("RGB", (50, 50), color=(120, 120, 120))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def _valid_pdf_file(self, name: str = "receipt.pdf") -> SimpleUploadedFile:
        content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_authenticated_get_renders_claim_screen(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Claim Item")
        self.assertContains(response, "FindIt")
        self.assertContains(response, "Item summary")
        self.assertContains(response, "Claim form")
        self.assertContains(response, 'name="full_name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="relationship_to_item"')
        self.assertContains(response, 'name="detailed_description"')
        self.assertContains(response, 'name="where_lost_location"')
        self.assertContains(response, 'name="proof_files"')
        self.assertContains(response, "Library")
        self.assertContains(response, 'aria-label="Private navigation"')
        self.assertContains(response, "Claims Received")
        self.assertNotContains(response, "Search lost & found items...")
        self.assertNotContains(response, "Claims Recibidos")

    def test_loading_state_renders_item_summary_skeleton(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(f"{self.url}?loading=1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "placeholder-glow")

    def test_valid_post_creates_claim_and_proofs(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "full_name": "Avery Jones",
            "email": "claimant@uwindsor.ca",
            "relationship_to_item": "Owner",
            "detailed_description": "Wallet has a blue stripe and two student cards.",
            "where_lost_location": str(self.location.pk),
            "consent": "on",
            "proof_files": [self._valid_image_file(), self._valid_pdf_file()],
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.my_claims_url)

        self.assertEqual(Claim.objects.count(), 1)
        created_claim = Claim.objects.get()
        self.assertEqual(created_claim.item, self.item)
        self.assertEqual(created_claim.claimant, self.user)
        self.assertIn("Relationship to item: Owner", created_claim.description)
        self.assertIn("Where lost: Library", created_claim.description)
        self.assertEqual(ClaimProof.objects.filter(claim=created_claim).count(), 2)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.CLAIM_SUBMISSION,
                item=self.item,
                metadata__claim_id=created_claim.id,
            ).exists()
        )

    def test_invalid_post_shows_top_alert_and_field_errors(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please fix the highlighted fields before submitting.")
        self.assertContains(response, "This field is required.")
        self.assertEqual(Claim.objects.count(), 0)

    def test_rejects_unsupported_file_format(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        bad_file = SimpleUploadedFile("notes.txt", b"plain-text", content_type="text/plain")

        payload = {
            "full_name": "Avery Jones",
            "email": "claimant@uwindsor.ca",
            "relationship_to_item": "Owner",
            "detailed_description": "Details",
            "where_lost_location": str(self.location.pk),
            "consent": "on",
            "proof_files": bad_file,
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "File too large / unsupported format.")
        self.assertEqual(Claim.objects.count(), 0)

    def test_rejects_more_than_three_files(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "full_name": "Avery Jones",
            "email": "claimant@uwindsor.ca",
            "relationship_to_item": "Owner",
            "detailed_description": "Details",
            "where_lost_location": str(self.location.pk),
            "consent": "on",
            "proof_files": [
                self._valid_image_file("a.png"),
                self._valid_image_file("b.png"),
                self._valid_image_file("c.png"),
                self._valid_pdf_file("d.pdf"),
            ],
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload 1-3 files.")
        self.assertEqual(Claim.objects.count(), 0)

    def test_rejects_claim_when_item_is_not_lost(self):
        self.item.status = Item.Status.CLAIMED
        self.item.save(update_fields=["status"])

        self.client.login(username=self.user.username, password="StrongPass123!")
        payload = {
            "full_name": "Avery Jones",
            "email": "claimant@uwindsor.ca",
            "relationship_to_item": "Owner",
            "detailed_description": "Wallet has a blue stripe and two student cards.",
            "where_lost_location": str(self.location.pk),
            "consent": "on",
            "proof_files": [self._valid_image_file()],
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only items with Lost status can be claimed.")
        self.assertEqual(Claim.objects.count(), 0)

    def test_rejects_claim_for_own_reported_item(self):
        self.item.reporter = self.user
        self.item.save(update_fields=["reporter"])

        self.client.login(username=self.user.username, password="StrongPass123!")
        payload = {
            "full_name": "Avery Jones",
            "email": "claimant@uwindsor.ca",
            "relationship_to_item": "Owner",
            "detailed_description": "Wallet has a blue stripe and two student cards.",
            "where_lost_location": str(self.location.pk),
            "consent": "on",
            "proof_files": [self._valid_image_file()],
        }

        response = self.client.post(self.url, data=payload, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You cannot claim your own reported item.")
        self.assertEqual(Claim.objects.count(), 0)


class MyClaimsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="myclaims@uwindsor.ca",
            email="myclaims@uwindsor.ca",
            password="StrongPass123!",
        )
        self.reporter = User.objects.create_user(
            username="reporter2@uwindsor.ca",
            email="reporter2@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Electronics", slug="electronics", is_active=True)
        self.location = CampusLocation.objects.create(name="Leddy Library", code="leddy-library", is_active=True)
        self.url = reverse("listings:my_claims")

    def _make_item(self, title: str) -> Item:
        return Item.objects.create(
            reporter=self.reporter,
            item_type=Item.ItemType.FOUND,
            status=Item.Status.FOUND,
            title=title,
            description=f"{title} description",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=2),
            is_visible=True,
        )

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_renders_full_my_claims_layout(self):
        item_1 = self._make_item("Wallet")
        item_2 = self._make_item("Jacket")
        item_3 = self._make_item("Keys")

        Claim.objects.create(item=item_1, claimant=self.user, description="Pending claim")
        Claim.objects.create(
            item=item_2,
            claimant=self.user,
            description="Approved claim",
            status=Claim.Status.APPROVED,
        )
        Claim.objects.create(item=item_3, claimant=self.user, description="Pending claim 2")

        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FindIt")
        self.assertContains(response, "My Claims")
        self.assertContains(response, "Track the status of your claims.")
        self.assertContains(response, "Refresh")
        self.assertContains(response, "Pending")
        self.assertContains(response, "Approved")
        self.assertContains(response, "Rejected")
        self.assertContains(response, "Claims")
        self.assertContains(response, "Search claims...")
        self.assertContains(response, "All statuses")
        self.assertContains(response, "Newest first")
        self.assertContains(response, "View item")
        self.assertContains(response, "Claim details")
        self.assertContains(response, 'aria-label="Private navigation"')
        self.assertNotContains(response, "Report Lost Item")
        self.assertNotContains(response, "Search lost & found items...")
        self.assertNotContains(response, "Claims Recibidos")

    def test_empty_state_renders_expected_content(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No claims yet")
        self.assertContains(response, "When you submit a claim, it will appear here.")
        self.assertContains(response, "Browse items")

    def test_loading_and_error_states_render(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        loading_response = self.client.get(f"{self.url}?state=loading")
        self.assertEqual(loading_response.status_code, 200)
        self.assertContains(loading_response, "placeholder")

        error_response = self.client.get(f"{self.url}?state=error")
        self.assertEqual(error_response.status_code, 200)
        self.assertContains(error_response, "Unable to load your claims. Please try again.")
        self.assertContains(error_response, "Retry")


class MyReceivedClaimsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reporter = User.objects.create_user(
            username="owner@uwindsor.ca",
            email="owner@uwindsor.ca",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other@uwindsor.ca",
            email="other@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant_1 = User.objects.create_user(
            username="claimant1@uwindsor.ca",
            email="claimant1@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant_2 = User.objects.create_user(
            username="claimant2@uwindsor.ca",
            email="claimant2@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Documents", slug="documents-2", is_active=True)
        self.location = CampusLocation.objects.create(name="CAW", code="caw", is_active=True)

        self.my_item = Item.objects.create(
            reporter=self.reporter,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Blue Wallet",
            description="Own reported item",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=3),
            is_visible=True,
        )
        self.other_item = Item.objects.create(
            reporter=self.other_user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Black Jacket",
            description="Other user's item",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=2),
            is_visible=True,
        )

        self.claim_1 = Claim.objects.create(
            item=self.my_item,
            claimant=self.claimant_1,
            description="Claim 1",
            status=Claim.Status.PENDING,
        )
        self.claim_2 = Claim.objects.create(
            item=self.my_item,
            claimant=self.claimant_2,
            description="Claim 2",
            status=Claim.Status.APPROVED,
        )
        Claim.objects.create(
            item=self.other_item,
            claimant=self.claimant_1,
            description="Should not be visible",
            status=Claim.Status.PENDING,
        )

        self.url = reverse("listings:my_received_claims")

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_reporter_only_sees_claims_for_own_items(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Claims Received")
        self.assertContains(response, self.my_item.title)
        self.assertNotContains(response, self.other_item.title)
        self.assertContains(response, self.claimant_1.email)
        self.assertContains(response, self.claimant_2.email)
        self.assertContains(response, "Review claim")
        self.assertContains(response, "Claim details")

    def test_filters_status_and_search(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")
        response = self.client.get(self.url, {"status": "APPROVED", "q": "claimant2"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#CLM-{self.claim_2.id:04d}")
        self.assertNotContains(response, f"#CLM-{self.claim_1.id:04d}")


class MyItemsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="items-owner@uwindsor.ca",
            email="items-owner@uwindsor.ca",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="items-other@uwindsor.ca",
            email="items-other@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant = User.objects.create_user(
            username="items-claimant@uwindsor.ca",
            email="items-claimant@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Electronics 2", slug="electronics-2", is_active=True)
        self.location = CampusLocation.objects.create(name="Essex Hall", code="essex-hall", is_active=True)

        self.item_1 = Item.objects.create(
            reporter=self.user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Laptop Sleeve",
            description="Own item with pending claim",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.item_2 = Item.objects.create(
            reporter=self.user,
            item_type=Item.ItemType.FOUND,
            status=Item.Status.FOUND,
            title="Umbrella",
            description="Own item without pending claim",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.other_item = Item.objects.create(
            reporter=self.other_user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Other item",
            description="Not mine",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )

        Claim.objects.create(
            item=self.item_1,
            claimant=self.claimant,
            description="Pending claim for item 1",
            status=Claim.Status.PENDING,
        )
        Claim.objects.create(
            item=self.item_1,
            claimant=self.other_user,
            description="Approved claim for item 1",
            status=Claim.Status.APPROVED,
        )

        self.url = reverse("listings:my_items")

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_lists_only_user_items_with_pending_badge(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Items")
        self.assertContains(response, self.item_1.title)
        self.assertContains(response, self.item_2.title)
        self.assertNotContains(response, self.other_item.title)
        self.assertContains(response, "Pending claims: 1")
        self.assertContains(response, "Report Lost")
        self.assertContains(response, "Report Found")
        self.assertContains(response, "Claims Received")


class ClaimDetailViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="findit-claim-detail-test-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        User = get_user_model()
        self.reporter = User.objects.create_user(
            username="claim-detail-reporter@uwindsor.ca",
            email="claim-detail-reporter@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant = User.objects.create_user(
            username="claim-detail-claimant@uwindsor.ca",
            email="claim-detail-claimant@uwindsor.ca",
            password="StrongPass123!",
        )
        self.third_user = User.objects.create_user(
            username="claim-detail-third@uwindsor.ca",
            email="claim-detail-third@uwindsor.ca",
            password="StrongPass123!",
        )
        self.admin_user = User.objects.create_user(
            username="claim-detail-admin@uwindsor.ca",
            email="claim-detail-admin@uwindsor.ca",
            password="StrongPass123!",
            is_staff=True,
        )

        self.category = Category.objects.create(name="Keys", slug="keys", is_active=True)
        self.location = CampusLocation.objects.create(name="Odette", code="odette", is_active=True)
        self.item = Item.objects.create(
            reporter=self.reporter,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Car Keys",
            description="Keychain with red strap",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.claim = Claim.objects.create(
            item=self.item,
            claimant=self.claimant,
            description="Claim details body",
            status=Claim.Status.PENDING,
        )
        image_file = self._valid_image_file("proof-image.png")
        doc_file = SimpleUploadedFile("proof-document.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        ClaimProof.objects.create(claim=self.claim, file=image_file)
        ClaimProof.objects.create(claim=self.claim, file=doc_file)

        self.url = reverse("listings:claim_detail", kwargs={"claim_id": self.claim.id})
        self.review_url = reverse("listings:claim_review", kwargs={"claim_id": self.claim.id})

    def _valid_image_file(self, name: str = "proof.png") -> SimpleUploadedFile:
        image = Image.new("RGB", (50, 50), color=(120, 120, 120))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_redirects_guest_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_claimant_can_view_detail(self):
        self.client.login(username=self.claimant.username, password="StrongPass123!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertContains(response, "Proof files (2)")
        self.assertContains(response, "Image evidence")
        self.assertContains(response, "Other files")
        self.assertContains(response, "proof-image.png")
        self.assertContains(response, "proof-document.pdf")
        self.assertNotContains(response, "Review claim")

    def test_reporter_can_view_detail(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.claimant.email)
        self.assertContains(response, "Review claim")
        self.assertContains(response, f'action="{self.review_url}"')

    def test_admin_can_view_detail(self):
        self.client.login(username=self.admin_user.username, password="StrongPass123!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Claim details")
        self.assertContains(response, "Review claim")

    def test_unrelated_user_gets_404(self):
        self.client.login(username=self.third_user.username, password="StrongPass123!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_reviewed_claim_shows_reviewer_metadata(self):
        self.claim.status = Claim.Status.APPROVED
        self.claim.reviewer = self.admin_user
        self.claim.reviewer_notes = "Claim details match the recovered item."
        self.claim.reviewed_at = timezone.now()
        self.claim.save()

        self.client.login(username=self.claimant.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reviewed by")
        self.assertContains(response, self.admin_user.username)
        self.assertContains(response, "Claim details match the recovered item.")


class ClaimReviewViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reporter = User.objects.create_user(
            username="review-owner@uwindsor.ca",
            email="review-owner@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant_1 = User.objects.create_user(
            username="review-claimant-1@uwindsor.ca",
            email="review-claimant-1@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant_2 = User.objects.create_user(
            username="review-claimant-2@uwindsor.ca",
            email="review-claimant-2@uwindsor.ca",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="review-other@uwindsor.ca",
            email="review-other@uwindsor.ca",
            password="StrongPass123!",
        )
        self.admin_user = User.objects.create_user(
            username="review-admin@uwindsor.ca",
            email="review-admin@uwindsor.ca",
            password="StrongPass123!",
            is_staff=True,
        )

        self.category = Category.objects.create(name="Review Docs", slug="review-docs", is_active=True)
        self.location = CampusLocation.objects.create(name="Review Hall", code="review-hall", is_active=True)
        self.item = Item.objects.create(
            reporter=self.reporter,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Student ID Wallet",
            description="Brown wallet with student ID",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=2),
            is_visible=True,
        )
        self.claim = Claim.objects.create(
            item=self.item,
            claimant=self.claimant_1,
            description="Primary claim",
            status=Claim.Status.PENDING,
        )
        self.other_pending_claim = Claim.objects.create(
            item=self.item,
            claimant=self.claimant_2,
            description="Backup claim",
            status=Claim.Status.PENDING,
        )

        self.url = reverse("listings:claim_review", kwargs={"claim_id": self.claim.id})
        self.detail_url = reverse("listings:claim_detail", kwargs={"claim_id": self.claim.id})

    def test_redirects_guest_to_login(self):
        response = self.client.post(self.url, {"decision": "approve"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_reporter_can_approve_claim_and_close_other_pending_claims(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "decision": "approve",
                "reviewer_notes": "Proof matches the serial details on the wallet.",
            },
        )

        self.assertRedirects(response, self.detail_url)
        self.claim.refresh_from_db()
        self.other_pending_claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.claim.status, Claim.Status.APPROVED)
        self.assertEqual(self.claim.reviewer, self.reporter)
        self.assertEqual(self.claim.reviewer_notes, "Proof matches the serial details on the wallet.")
        self.assertIsNotNone(self.claim.reviewed_at)
        self.assertEqual(self.item.status, Item.Status.CLAIMED)
        self.assertEqual(self.item.claimed_by, self.claimant_1)
        self.assertEqual(self.other_pending_claim.status, Claim.Status.REJECTED)
        self.assertEqual(self.other_pending_claim.reviewer, self.reporter)
        self.assertIn("another claim for this item was approved", self.other_pending_claim.reviewer_notes.lower())
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.reporter,
                activity_type=UserActivity.ActivityType.CLAIM_REVIEW,
                item=self.item,
                metadata__claim_id=self.claim.id,
                metadata__decision="approve",
            ).exists()
        )

    def test_reporter_can_reject_claim_with_notes(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "decision": "reject",
                "reviewer_notes": "The identifying details do not match the item report.",
            },
        )

        self.assertRedirects(response, self.detail_url)
        self.claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.claim.status, Claim.Status.REJECTED)
        self.assertEqual(self.claim.reviewer, self.reporter)
        self.assertEqual(self.item.status, Item.Status.LOST)
        self.assertIsNone(self.item.claimed_by)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.reporter,
                activity_type=UserActivity.ActivityType.CLAIM_REVIEW,
                item=self.item,
                metadata__claim_id=self.claim.id,
                metadata__decision="reject",
            ).exists()
        )

    def test_reject_requires_reviewer_notes(self):
        self.client.login(username=self.reporter.username, password="StrongPass123!")

        response = self.client.post(self.url, {"decision": "reject"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please provide a reason when rejecting a claim.")
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, Claim.Status.PENDING)

    def test_claimant_cannot_review_claim(self):
        self.client.login(username=self.claimant_1.username, password="StrongPass123!")

        response = self.client.post(self.url, {"decision": "approve"})

        self.assertEqual(response.status_code, 404)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, Claim.Status.PENDING)

    def test_admin_can_review_claim(self):
        self.client.login(username=self.admin_user.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "decision": "approve",
                "reviewer_notes": "Approved by admin review.",
            },
        )

        self.assertRedirects(response, self.detail_url)
        self.claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.claim.status, Claim.Status.APPROVED)
        self.assertEqual(self.claim.reviewer, self.admin_user)
        self.assertEqual(self.item.claimed_by, self.claimant_1)

    def test_already_reviewed_claim_cannot_be_reviewed_twice(self):
        self.claim.status = Claim.Status.APPROVED
        self.claim.reviewer = self.reporter
        self.claim.reviewed_at = timezone.now()
        self.claim.save()

        self.client.login(username=self.reporter.username, password="StrongPass123!")
        response = self.client.post(self.url, {"decision": "reject"}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This claim has already been reviewed.")
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, Claim.Status.APPROVED)

    def test_cannot_approve_claim_when_item_is_no_longer_lost(self):
        self.item.status = Item.Status.RETURNED
        self.item.save(update_fields=["status"])

        self.client.login(username=self.reporter.username, password="StrongPass123!")
        response = self.client.post(
            self.url,
            {
                "decision": "approve",
                "reviewer_notes": "Trying to approve after item status changed.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only items that are still marked as lost can be approved.")
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, Claim.Status.PENDING)


class ItemEditViewTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="findit-item-edit-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        User = get_user_model()
        self.user = User.objects.create_user(
            username="item-owner@uwindsor.ca",
            email="item-owner@uwindsor.ca",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="item-other@uwindsor.ca",
            email="item-other@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Keys", slug="keys", is_active=True)
        self.location = CampusLocation.objects.create(name="Library", code="library-main", is_active=True)
        self.item = Item.objects.create(
            reporter=self.user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Key fob",
            description="Black key fob",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.image_1 = ItemImage.objects.create(item=self.item, image=self._valid_image_file("img-1.png"))
        self.image_2 = ItemImage.objects.create(item=self.item, image=self._valid_image_file("img-2.png"))
        self.url = reverse("listings:item_edit", kwargs={"pk": self.item.pk})

    def _valid_image_file(self, name: str = "photo.png") -> SimpleUploadedFile:
        image = Image.new("RGB", (50, 50), color=(100, 110, 120))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_owner_can_update_status_remove_image_and_add_new_one(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        payload = {
            "title": "Key fob updated",
            "category": str(self.category.pk),
            "status": Item.Status.RETURNED,
            "event_date": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": "Returned to the owner.",
            "remove_images": [str(self.image_1.pk)],
        }

        response = self.client.post(
            self.url,
            data={**payload, "photos": self._valid_image_file("replacement.png")},
            format="multipart",
        )

        self.assertRedirects(response, reverse("listings:item_detail_public", kwargs={"pk": self.item.pk}))
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Key fob updated")
        self.assertEqual(self.item.status, Item.Status.RETURNED)
        self.assertFalse(ItemImage.objects.filter(pk=self.image_1.pk).exists())
        self.assertEqual(ItemImage.objects.filter(item=self.item).count(), 2)
        self.assertTrue(ItemImage.objects.filter(item=self.item, image__icontains="replacement").exists())

    def test_rejects_when_total_image_count_would_exceed_limit(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        for idx in range(3):
            ItemImage.objects.create(item=self.item, image=self._valid_image_file(f"extra-{idx}.png"))

        payload = {
            "title": self.item.title,
            "category": str(self.category.pk),
            "status": Item.Status.LOST,
            "event_date": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "location": str(self.location.pk),
            "description": self.item.description,
        }

        response = self.client.post(
            self.url,
            data={**payload, "photos": self._valid_image_file("overflow.png")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You can keep up to 5 photos total.")

    def test_non_owner_gets_404(self):
        self.client.login(username=self.other_user.username, password="StrongPass123!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
