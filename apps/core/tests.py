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
        self.assertContains(response, "Report Found Item")
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
        self.assertContains(response, f'href="{reverse("users:login")}"')
        self.assertContains(response, f'href="{reverse("users:register")}"')


class HomeLandingContentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reporter = User.objects.create_user(
            username="home-content@uwindsor.ca",
            email="home-content@uwindsor.ca",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(name="Electronics", slug="electronics", is_active=True)
        self.location = CampusLocation.objects.create(name="Leddy Library", code="leddy-library", is_active=True)
        self.url = reverse("core:home")

        self._create_items(status=Item.Status.LOST, count=5, prefix="Lost")
        self._create_items(status=Item.Status.FOUND, count=3, prefix="Found")
        self._create_items(status=Item.Status.LOST, count=1, prefix="Hidden", is_visible=False)

    def _create_items(self, *, status, count, prefix, is_visible=True):
        now = timezone.now()
        created_items = []

        for index in range(count):
            item = Item.objects.create(
                reporter=self.reporter,
                item_type=Item.ItemType.LOST if status == Item.Status.LOST else Item.ItemType.FOUND,
                status=status,
                title=f"{prefix} Item {index}",
                description=f"{prefix} description {index}",
                category=self.category,
                location=self.location,
                event_date=now - timedelta(days=index + 1),
                is_visible=is_visible,
            )
            Item.objects.filter(pk=item.pk).update(
                created_at=now + timedelta(minutes=index),
                updated_at=now + timedelta(minutes=index),
            )
            item.refresh_from_db()
            created_items.append(item)

        return created_items

    def test_home_renders_hero_quick_actions_and_recent_tabs(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lost something on campus?")
        self.assertContains(response, 'method="get"', count=2)
        self.assertContains(response, f'action="{reverse("listings:search_results")}"', count=2)
        self.assertContains(response, f'href="{reverse("listings:search_results")}?status=LOST"')
        self.assertContains(response, f'href="{reverse("listings:search_results")}?status=FOUND"')
        self.assertContains(response, f'href="{reverse("listings:faq")}"')
        self.assertContains(response, 'id="recent-lost-tab"')
        self.assertContains(response, 'id="recent-found-tab"')
        self.assertContains(response, "Lost Item 4")
        self.assertContains(response, "Lost Item 3")
        self.assertContains(response, "Lost Item 2")
        self.assertContains(response, "Lost Item 1")
        self.assertNotContains(response, "Lost Item 0")
        self.assertContains(response, "Found Item 2")
        self.assertContains(response, "Found Item 1")
        self.assertContains(response, "Found Item 0")
        self.assertNotContains(response, "Hidden Item 0")
        self.assertContains(response, f'href="{reverse("users:login")}"')
        self.assertContains(response, f'href="{reverse("users:register")}"')

    def test_home_shows_empty_state_when_found_tab_has_no_items(self):
        Item.objects.filter(status=Item.Status.FOUND).delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No found items yet")
        self.assertContains(response, "Create an account to stay ready.")
        self.assertContains(response, f'href="{reverse("users:register")}"')


class StaticPageTests(TestCase):
    def test_about_page_renders(self):
        response = self.client.get(reverse("core:about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "About FindIt")
        self.assertContains(response, "Report lost and found items")

    def test_contact_page_renders(self):
        response = self.client.get(reverse("core:contact"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact")
        self.assertContains(response, "support@findit.local")
