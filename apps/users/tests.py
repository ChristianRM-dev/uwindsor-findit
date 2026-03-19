from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.listings.models import CampusLocation, Category, Claim, Item


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
