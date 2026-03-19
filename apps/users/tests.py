from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.core.models import Notification, UserActivity
from apps.listings.models import CampusLocation, Category, Claim, Item


class ProfileViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="profile-user@uwindsor.ca",
            email="profile-user@uwindsor.ca",
            password="StrongPass123!",
            first_name="Jenny",
            last_name="Zhao",
            student_id="123456789",
            phone_number="519-555-1000",
        )
        self.other_user = User.objects.create_user(
            username="profile-other@uwindsor.ca",
            email="profile-other@uwindsor.ca",
            password="StrongPass123!",
            student_id="987654321",
        )
        self.url = reverse("users:profile")
        self.dashboard_url = reverse("core:dashboard")

    def test_profile_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('users:login')}?next=", response.url)

    def test_profile_page_renders_prefilled_form_and_navigation_links(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Profile")
        self.assertContains(response, self.user.email)
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="student_id"')
        self.assertContains(response, 'name="phone_number"')
        self.assertContains(response, 'href="/auth/profile/"')
        self.assertContains(response, "Back to dashboard")

    def test_profile_post_updates_user_fields(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "first_name": "Jennifer",
                "last_name": "Zhang",
                "student_id": "111222333",
                "phone_number": "+1 (519) 555-8899",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile updated successfully.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jennifer")
        self.assertEqual(self.user.last_name, "Zhang")
        self.assertEqual(self.user.student_id, "111222333")
        self.assertEqual(self.user.phone_number, "+1 (519) 555-8899")

    def test_profile_rejects_duplicate_student_id(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "student_id": self.other_user.student_id,
                "phone_number": self.user.phone_number,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This student ID is already in use.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.student_id, "123456789")

    def test_profile_rejects_invalid_student_id_and_phone_number(self):
        self.client.login(username=self.user.username, password="StrongPass123!")

        response = self.client.post(
            self.url,
            {
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "student_id": "abc123",
                "phone_number": "519-555-ABCD",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student ID must be exactly 9 digits.")
        self.assertContains(response, "Phone number can only contain digits, spaces, and - + ( ).")


class AdminPanelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            username="site-admin",
            email="site-admin@uwindsor.ca",
            password="StrongPass123!",
        )
        self.owner = User.objects.create_user(
            username="panel-owner@uwindsor.ca",
            email="panel-owner@uwindsor.ca",
            password="StrongPass123!",
            student_id="123456789",
            phone_number="519-555-0100",
        )
        self.claimant_1 = User.objects.create_user(
            username="panel-claimant-1@uwindsor.ca",
            email="panel-claimant-1@uwindsor.ca",
            password="StrongPass123!",
        )
        self.claimant_2 = User.objects.create_user(
            username="panel-claimant-2@uwindsor.ca",
            email="panel-claimant-2@uwindsor.ca",
            password="StrongPass123!",
        )

        self.category = Category.objects.create(name="Admin Docs", slug="admin-docs", is_active=True)
        self.location = CampusLocation.objects.create(name="Admin Hall", code="admin-hall", is_active=True)
        self.item = Item.objects.create(
            reporter=self.owner,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Admin Test Wallet",
            description="Wallet used for admin panel tests.",
            category=self.category,
            location=self.location,
            event_date=timezone.now(),
            is_visible=True,
        )
        self.pending_claim = Claim.objects.create(
            item=self.item,
            claimant=self.claimant_1,
            description="Primary pending claim",
            status=Claim.Status.PENDING,
        )
        self.secondary_claim = Claim.objects.create(
            item=self.item,
            claimant=self.claimant_2,
            description="Secondary pending claim",
            status=Claim.Status.PENDING,
        )

        self.conversation = Conversation.objects.create(item=self.item, created_by=self.claimant_1)
        self.conversation.participants.add(self.owner, self.claimant_1)
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.claimant_1,
            content="Admin panel test message",
        )

        self.client.force_login(self.admin_user)

    def test_admin_index_and_registered_model_pages_render(self):
        index_response = self.client.get(reverse("admin:index"))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, "FindIt Administration")
        self.assertContains(index_response, "Listings")
        self.assertContains(index_response, "Chat")
        self.assertContains(index_response, "Core")
        self.assertContains(index_response, "Users")

        user_response = self.client.get(reverse("admin:users_user_changelist"))
        self.assertEqual(user_response.status_code, 200)
        self.assertContains(user_response, self.owner.email)

        item_response = self.client.get(reverse("admin:listings_item_changelist"))
        self.assertEqual(item_response.status_code, 200)
        self.assertContains(item_response, self.item.title)

        claim_response = self.client.get(reverse("admin:listings_claim_changelist"))
        self.assertEqual(claim_response.status_code, 200)
        self.assertContains(claim_response, self.pending_claim.claimant.email)

        conversation_response = self.client.get(reverse("admin:chat_conversation_changelist"))
        self.assertEqual(conversation_response.status_code, 200)
        self.assertContains(conversation_response, self.item.title)

        message_response = self.client.get(reverse("admin:chat_message_changelist"))
        self.assertEqual(message_response.status_code, 200)
        self.assertContains(message_response, self.message.content)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_claim_admin_approve_action_reviews_claim_and_closes_others(self):
        response = self.client.post(
            reverse("admin:listings_claim_changelist"),
            {
                "action": "approve_selected_claims",
                ACTION_CHECKBOX_NAME: [str(self.pending_claim.pk)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved 1 claim(s).")

        self.pending_claim.refresh_from_db()
        self.secondary_claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.pending_claim.status, Claim.Status.APPROVED)
        self.assertEqual(self.pending_claim.reviewer, self.admin_user)
        self.assertEqual(self.pending_claim.reviewer_notes, "Approved in Django admin.")
        self.assertEqual(self.item.status, Item.Status.CLAIMED)
        self.assertEqual(self.item.claimed_by, self.claimant_1)
        self.assertEqual(self.secondary_claim.status, Claim.Status.REJECTED)
        self.assertEqual(self.secondary_claim.reviewer, self.admin_user)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.claimant_1,
                claim=self.pending_claim,
                notification_type=Notification.NotificationType.CLAIM_APPROVED,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.claimant_2,
                claim=self.secondary_claim,
                notification_type=Notification.NotificationType.CLAIM_REJECTED,
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.admin_user,
                activity_type=UserActivity.ActivityType.CLAIM_REVIEW,
                item=self.item,
                metadata__claim_id=self.pending_claim.id,
                metadata__decision="approve",
                metadata__via="admin",
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_claim_admin_reject_action_reviews_claim(self):
        response = self.client.post(
            reverse("admin:listings_claim_changelist"),
            {
                "action": "reject_selected_claims",
                ACTION_CHECKBOX_NAME: [str(self.pending_claim.pk)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rejected 1 claim(s).")

        self.pending_claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.pending_claim.status, Claim.Status.REJECTED)
        self.assertEqual(self.pending_claim.reviewer, self.admin_user)
        self.assertEqual(self.pending_claim.reviewer_notes, "Rejected in Django admin.")
        self.assertEqual(self.item.status, Item.Status.LOST)
        self.assertIsNone(self.item.claimed_by)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.claimant_1,
                claim=self.pending_claim,
                notification_type=Notification.NotificationType.CLAIM_REJECTED,
            ).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.admin_user,
                activity_type=UserActivity.ActivityType.CLAIM_REVIEW,
                item=self.item,
                metadata__claim_id=self.pending_claim.id,
                metadata__decision="reject",
                metadata__via="admin",
            ).exists()
        )
