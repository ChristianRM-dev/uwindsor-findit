from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.listings.models import CampusLocation, Category, Claim, Item


class DashboardViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="dashboard@uwindsor.ca",
            email="dashboard@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant = User.objects.create_user(
            username="dashboard-claimant@uwindsor.ca",
            email="dashboard-claimant@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Misc", slug="misc", is_active=True)
        self.location = CampusLocation.objects.create(name="Library Main", code="library-main", is_active=True)
        self.item = Item.objects.create(
            reporter=self.user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Notebook",
            description="Black notebook",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        Claim.objects.create(
            item=self.item,
            claimant=self.claimant,
            description="This is mine",
            status=Claim.Status.PENDING,
        )

        self.url = reverse("core:dashboard")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_dashboard_renders_quick_actions(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Report Lost Item")
        self.assertContains(response, "My Items")
        self.assertContains(response, "My Claims")
        self.assertContains(response, "Claims Received")
        self.assertContains(response, 'aria-label="Private navigation"')
        self.assertNotContains(response, "Search lost & found items...")
        self.assertNotContains(response, "Claims Recibidos")
        self.assertContains(response, f'href="{reverse("core:home")}"')


class HomePublicNavbarTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="public-navbar@uwindsor.ca",
            email="public-navbar@uwindsor.ca",
            password="StrongPass123!",
        )
        self.url = reverse("core:home")

    def test_authenticated_home_shows_public_navbar_contract(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search lost & found items...")
        self.assertContains(response, f'href="{reverse("core:dashboard")}"')
        self.assertContains(response, "Logout")
        self.assertNotContains(response, f'href="{reverse("listings:my_items")}"')
        self.assertNotContains(response, f'href="{reverse("listings:my_claims")}"')
        self.assertNotContains(response, f'href="{reverse("listings:my_received_claims")}"')
        self.assertNotContains(response, "Claims Recibidos")
