from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.core.models import UserActivity
from apps.listings.models import CampusLocation, Category, Item


class ChatViewsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@uwindsor.ca",
            email="owner@uwindsor.ca",
            password="DemoPass123!",
        )
        self.sender = user_model.objects.create_user(
            username="sender@uwindsor.ca",
            email="sender@uwindsor.ca",
            password="DemoPass123!",
        )
        self.category = Category.objects.create(name="Bags", slug="bags", is_active=True)
        self.location = CampusLocation.objects.create(
            name="Lambton Tower",
            code="lambton-tower",
            is_active=True,
        )
        self.item = Item.objects.create(
            reporter=self.owner,
            item_type=Item.ItemType.LOST,
            status=Item.Status.LOST,
            title="Black Backpack",
            description="Backpack near the north entrance.",
            category=self.category,
            location=self.location,
            event_date=timezone.now(),
            is_visible=True,
        )

    def test_item_detail_shows_contact_owner_button_for_non_owner(self):
        self.client.force_login(self.sender)

        response = self.client.get(reverse("listings:item_detail_public", kwargs={"pk": self.item.pk}))

        self.assertContains(response, "Contact Owner")
        self.assertContains(response, reverse("chat:contact_owner", kwargs={"item_id": self.item.pk}))

    def test_contact_owner_post_creates_conversation_and_redirects(self):
        self.client.force_login(self.sender)

        response = self.client.post(
            reverse("chat:contact_owner", kwargs={"item_id": self.item.pk}),
            {"message": "I think this is my backpack because it has a blue notebook inside."},
        )

        conversation = Conversation.objects.get(item=self.item)
        self.assertRedirects(response, reverse("chat:message_thread", kwargs={"conversation_id": conversation.pk}))
        self.assertEqual(conversation.participants.count(), 2)
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(conversation.messages.first().sender, self.sender)
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.sender,
                activity_type=UserActivity.ActivityType.MESSAGE,
                item=self.item,
                metadata__context="contact_owner",
            ).exists()
        )

    def test_message_thread_marks_unread_messages_as_read(self):
        conversation = Conversation.objects.create(item=self.item, created_by=self.sender)
        conversation.participants.add(self.owner, self.sender)
        unread_message = Message.objects.create(
            conversation=conversation,
            sender=self.owner,
            content="Can you describe the zipper color?",
            is_read=False,
        )

        self.client.force_login(self.sender)
        response = self.client.get(reverse("chat:message_thread", kwargs={"conversation_id": conversation.pk}))

        unread_message.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(unread_message.is_read)
        self.assertIsNotNone(unread_message.read_at)

    def test_message_thread_post_creates_reply(self):
        conversation = Conversation.objects.create(item=self.item, created_by=self.sender)
        conversation.participants.add(self.owner, self.sender)

        self.client.force_login(self.sender)
        response = self.client.post(
            reverse("chat:message_thread", kwargs={"conversation_id": conversation.pk}),
            {"message": "It also has a silver Dell laptop inside."},
        )

        self.assertRedirects(response, reverse("chat:message_thread", kwargs={"conversation_id": conversation.pk}))
        self.assertTrue(
            conversation.messages.filter(content="It also has a silver Dell laptop inside.", sender=self.sender).exists()
        )
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.sender,
                activity_type=UserActivity.ActivityType.MESSAGE,
                item=self.item,
                metadata__context="thread_reply",
            ).exists()
        )

    def test_navbar_bell_shows_unread_count(self):
        conversation = Conversation.objects.create(item=self.item, created_by=self.owner)
        conversation.participants.add(self.owner, self.sender)
        Message.objects.create(
            conversation=conversation,
            sender=self.owner,
            content="Please confirm the bag brand.",
            is_read=False,
        )

        self.client.force_login(self.sender)
        response = self.client.get(reverse("listings:item_detail_public", kwargs={"pk": self.item.pk}))

        self.assertContains(response, reverse("chat:message_list"))
        self.assertContains(response, 'badge rounded-pill text-bg-danger')
        self.assertContains(response, 'aria-label="Messages"')
