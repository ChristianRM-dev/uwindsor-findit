import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.email_backends import ApiEmailBackend
from apps.core.models import Notification, UserActivity
from apps.listings.models import CampusLocation, Category, Claim, Item


class ApiEmailBackendTests(SimpleTestCase):
    @override_settings(
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_key",
        DEFAULT_FROM_EMAIL="FindIt <no-reply@example.com>",
    )
    def test_resend_backend_posts_expected_payload(self):
        backend = ApiEmailBackend()
        message = EmailMultiAlternatives(
            subject="Password reset",
            body="Reset your password",
            to=["student@example.com"],
            cc=["advisor@example.com"],
            bcc=["audit@example.com"],
            reply_to=["support@example.com"],
            headers={"X-Entity-Ref-ID": "thread-123"},
        )
        message.attach_alternative("<p>Reset your password</p>", "text/html")

        response = MagicMock()
        response.read.return_value = b'{"id":"email_123"}'
        response.__enter__.return_value = response
        response.__exit__.return_value = False

        with patch(
            "apps.core.email_backends.urlopen",
            return_value=response,
        ) as mocked_urlopen:
            sent_count = backend.send_messages([message])

        self.assertEqual(sent_count, 1)
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(payload["from"], "FindIt <no-reply@example.com>")
        self.assertEqual(payload["to"], ["student@example.com"])
        self.assertEqual(payload["cc"], ["advisor@example.com"])
        self.assertEqual(payload["bcc"], ["audit@example.com"])
        self.assertEqual(payload["reply_to"], ["support@example.com"])
        self.assertEqual(payload["subject"], "Password reset")
        self.assertEqual(payload["text"], "Reset your password")
        self.assertEqual(payload["html"], "<p>Reset your password</p>")
        self.assertEqual(payload["headers"]["X-Entity-Ref-ID"], "thread-123")

    @override_settings(
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="",
        DEFAULT_FROM_EMAIL="FindIt <no-reply@example.com>",
    )
    def test_resend_backend_requires_api_key(self):
        backend = ApiEmailBackend()
        message = EmailMultiAlternatives(
            subject="Hello",
            body="World",
            to=["student@example.com"],
        )

        with self.assertRaises(ImproperlyConfigured):
            backend.send_messages([message])


class HealthViewTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


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

        self.category = Category.objects.create(
            name="Misc", slug="misc", is_active=True
        )
        self.location = CampusLocation.objects.create(
            name="Library Main", code="library-main", is_active=True
        )
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
        self.assertContains(response, "User History")
        self.assertContains(response, 'aria-label="Private navigation"')
        self.assertNotContains(response, "Search lost & found items...")
        self.assertNotContains(response, "Claims Recibidos")
        self.assertContains(response, f'href="{reverse("core:home")}"')
        self.assertContains(response, "Recent Activity")
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.PAGE_VIEW,
                page_path=self.url,
            ).exists()
        )

    def test_dashboard_renders_recent_activity_entries(self):
        UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.SEARCH,
            page_path=reverse("listings:search_results"),
            search_query="wallet",
            metadata={"result_count": 2, "status": "LOST"},
        )
        UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.ITEM_VIEW,
            page_path=reverse(
                "listings:item_detail_public", kwargs={"pk": self.item.pk}
            ),
            item=self.item,
            metadata={},
        )

        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Searched for")
        self.assertContains(response, "wallet")
        self.assertContains(response, "Lost | 2 result(s)")
        self.assertContains(response, f"Viewed item: {self.item.title}")


class UserHistoryViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="history@uwindsor.ca",
            email="history@uwindsor.ca",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(
            name="History Items", slug="history-items", is_active=True
        )
        self.location = CampusLocation.objects.create(
            name="History Hall", code="history-hall", is_active=True
        )
        self.item = Item.objects.create(
            reporter=self.user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="History Notebook",
            description="History fixture item",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.url = reverse("core:history")

    def test_history_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_history_renders_counts_and_daily_visits(self):
        self.client.login(username=self.user.username, password="StrongPass123!")
        session = self.client.session
        session.save()
        session_key = session.session_key

        today_view = UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            page_path=reverse("core:home"),
            session_key=session_key,
        )
        older_view = UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.PAGE_VIEW,
            page_path=reverse("core:dashboard"),
            session_key=session_key,
        )
        UserActivity.objects.filter(pk=older_view.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.SEARCH,
            page_path=reverse("listings:search_results"),
            search_query="wallet",
            session_key=session_key,
            metadata={"result_count": 2, "status": "FOUND"},
        )
        UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.ITEM_VIEW,
            page_path=reverse("listings:item_detail_public", kwargs={"pk": self.item.pk}),
            item=self.item,
            session_key=session_key,
        )
        UserActivity.objects.create(
            user=self.user,
            activity_type=UserActivity.ActivityType.MESSAGE,
            page_path="/messages/",
            item=self.item,
            session_key=session_key,
            metadata={"context": "item_thread", "conversation_id": 3},
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User History")
        self.assertContains(response, "Visits Per Day")
        self.assertContains(response, "Recent Tracked Activity")
        self.assertEqual(response.context["page_views_today"], 1)
        self.assertEqual(response.context["page_views_last_7_days"], 2)
        self.assertEqual(response.context["search_count"], 1)
        self.assertEqual(response.context["item_view_count"], 1)
        self.assertEqual(response.context["message_count"], 1)
        self.assertGreaterEqual(response.context["current_session_activity_count"], 4)
        self.assertContains(response, 'href="%s"' % reverse("core:history"))
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.PAGE_VIEW,
                page_path=self.url,
            ).exists()
        )


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
        self.assertNotContains(
            response, f'href="{reverse("listings:my_received_claims")}"'
        )
        self.assertNotContains(response, "Claims Recibidos")
        self.assertContains(response, f'href="{reverse("users:login")}"')
        self.assertContains(response, f'href="{reverse("users:register")}"')
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.PAGE_VIEW,
                page_path=self.url,
            ).exists()
        )

    def test_footer_links_to_privacy_and_terms_pages(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("core:privacy")}"')
        self.assertContains(response, f'href="{reverse("core:terms")}"')

        privacy_response = self.client.get(reverse("core:privacy"))
        self.assertEqual(privacy_response.status_code, 200)
        self.assertContains(privacy_response, "Privacy")

        terms_response = self.client.get(reverse("core:terms"))
        self.assertEqual(terms_response.status_code, 200)
        self.assertContains(terms_response, "Terms of Use")


class NotificationViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="notifications@uwindsor.ca",
            email="notifications@uwindsor.ca",
            password="StrongPass123!",
        )
        self.other_user = User.objects.create_user(
            username="notifications-other@uwindsor.ca",
            email="notifications-other@uwindsor.ca",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(
            name="Notifications", slug="notifications", is_active=True
        )
        self.location = CampusLocation.objects.create(
            name="Chrysler", code="chrysler", is_active=True
        )
        self.item = Item.objects.create(
            reporter=self.other_user,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Orange USB Drive",
            description="Notification fixture item",
            category=self.category,
            location=self.location,
            event_date=timezone.now() - timedelta(days=1),
            is_visible=True,
        )
        self.claim = Claim.objects.create(
            item=self.item,
            claimant=self.user,
            description="Notification fixture claim",
            status=Claim.Status.PENDING,
        )
        self.unread_notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.CLAIM_APPROVED,
            title="Claim approved for Orange USB Drive",
            body="Your claim was approved.",
            link_path=reverse(
                "listings:claim_detail", kwargs={"claim_id": self.claim.pk}
            ),
            item=self.item,
            claim=self.claim,
        )
        self.read_notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.CLAIM_SUBMITTED,
            title="Claim submitted for Orange USB Drive",
            body="A claim was submitted.",
            is_read=True,
            read_at=timezone.now(),
            item=self.item,
            claim=self.claim,
        )
        self.url = reverse("core:notifications")
        self.mark_all_url = reverse("core:notifications_mark_all_read")

    def test_notifications_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_notifications_page_renders_entries_and_navigation(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notifications")
        self.assertContains(response, self.unread_notification.title)
        self.assertContains(response, self.read_notification.title)
        self.assertContains(response, 'aria-label="Notifications"')
        self.assertContains(response, reverse("core:notifications_mark_all_read"))
        self.assertContains(
            response,
            reverse("listings:claim_detail", kwargs={"claim_id": self.claim.pk}),
        )
        self.assertContains(response, "Unread")
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.user,
                activity_type=UserActivity.ActivityType.PAGE_VIEW,
                page_path=self.url,
            ).exists()
        )

    def test_mark_all_read_updates_only_current_users_notifications(self):
        other_notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.CLAIM_REJECTED,
            title="Other notification",
            body="Other body",
        )

        self.client.login(username=self.user.username, password="StrongPass123!")
        response = self.client.post(self.mark_all_url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marked 1 notification(s) as read.")
        self.unread_notification.refresh_from_db()
        other_notification.refresh_from_db()
        self.assertTrue(self.unread_notification.is_read)
        self.assertIsNotNone(self.unread_notification.read_at)
        self.assertFalse(other_notification.is_read)


class HomeLandingContentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reporter = User.objects.create_user(
            username="home-content@uwindsor.ca",
            email="home-content@uwindsor.ca",
            password="StrongPass123!",
        )
        self.category = Category.objects.create(
            name="Electronics", slug="electronics", is_active=True
        )
        self.location = CampusLocation.objects.create(
            name="Leddy Library", code="leddy-library", is_active=True
        )
        self.url = reverse("core:home")

        self._create_items(status=Item.Status.LOST, count=5, prefix="Lost")
        self._create_items(status=Item.Status.FOUND, count=3, prefix="Found")
        self._create_items(
            status=Item.Status.LOST, count=1, prefix="Hidden", is_visible=False
        )

    def _create_items(self, *, status, count, prefix, is_visible=True):
        now = timezone.now()
        created_items = []

        for index in range(count):
            item = Item.objects.create(
                reporter=self.reporter,
                item_type=(
                    Item.ItemType.LOST
                    if status == Item.Status.LOST
                    else Item.ItemType.FOUND
                ),
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
        self.assertContains(
            response, f'action="{reverse("listings:search_results")}"', count=2
        )
        self.assertContains(
            response, f'href="{reverse("listings:search_results")}?status=LOST"'
        )
        self.assertContains(
            response, f'href="{reverse("listings:search_results")}?status=FOUND"'
        )
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
        self.assertContains(response, "1. Report")
        self.assertContains(response, "Trust and safety")

    def test_contact_page_renders(self):
        response = self.client.get(reverse("core:contact"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact")
        self.assertContains(response, "View Team Details")
        self.assertContains(response, "Login or account-access issues")

    def test_team_page_renders_all_members(self):
        response = self.client.get(reverse("core:team"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Team Details")
        self.assertContains(response, "Christian Rios Mancilla")
        self.assertContains(response, "riosman@uwindsor.ca")
        self.assertContains(response, "Sweatha Panneer Selvam")
        self.assertContains(response, "panneers@uwindsor.ca")
        self.assertContains(response, "Hong An Do")
        self.assertContains(response, "doan31@uwindsor.ca")
        self.assertContains(response, "Zhaojun Zhang")
        self.assertContains(response, "zhang6o3@uwindsor.ca")
        self.assertContains(response, "Tingwan Zhou")
        self.assertContains(response, "zhou9x@uwindsor.ca")


class SecuritySettingsTests(TestCase):
    def test_security_settings_are_enabled(self):
        self.assertGreater(settings.SESSION_COOKIE_AGE, 0)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
