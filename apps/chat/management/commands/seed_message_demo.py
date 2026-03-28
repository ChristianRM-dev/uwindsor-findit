from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.listings.models import CampusLocation, Category, Item


DEMO_PASSWORD = "DemoPass123!"


class Command(BaseCommand):
    help = "Seed demo users, items, and conversation data for the message module."

    @transaction.atomic
    def handle(self, *args, **options):
        owner = self._upsert_user(
            email="owner.demo@uwindsor.ca",
            student_id="900000001",
            first_name="Maya",
            last_name="Owner",
        )
        contact_user = self._upsert_user(
            email="message.demo@uwindsor.ca",
            student_id="900000002",
            first_name="Ethan",
            last_name="Sender",
        )

        category, _ = Category.objects.get_or_create(
            name="Bags",
            defaults={"slug": "bags", "is_active": True},
        )
        if not category.is_active:
            category.is_active = True
            category.save(update_fields=["is_active"])

        location, _ = CampusLocation.objects.get_or_create(
            name="Lambton Tower",
            defaults={"code": "lambton-tower", "is_active": True},
        )
        if not location.is_active:
            location.is_active = True
            location.save(update_fields=["is_active"])

        target_item, _ = Item.objects.get_or_create(
            reporter=owner,
            title="Black Patagonia Backpack",
            item_type=Item.ItemType.LOST,
            defaults={
                "status": Item.Status.LOST,
                "description": (
                    "Black Patagonia backpack with a laptop sleeve and engineering notes inside."
                ),
                "category": category,
                "location": location,
                "event_date": timezone.now() - timedelta(days=2),
                "is_visible": True,
            },
        )

        conversation = self._get_or_create_conversation(
            item=target_item,
            created_by=contact_user,
            participants=[owner, contact_user],
        )
        message_count = self._seed_messages(conversation, owner, contact_user)

        self.stdout.write(self.style.SUCCESS("Message demo seed completed."))
        self.stdout.write(f"Owner login: {owner.email} / {DEMO_PASSWORD}")
        self.stdout.write(f"Contact-user login: {contact_user.email} / {DEMO_PASSWORD}")
        self.stdout.write(f"Item detail URL: /items/{target_item.pk}")
        self.stdout.write(f"Conversation id: {conversation.pk}")
        self.stdout.write(f"Messages ensured: {message_count}")

    def _upsert_user(self, *, email: str, student_id: str, first_name: str, last_name: str):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "student_id": student_id,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )

        updated_fields = []
        if user.username != email:
            user.username = email
            updated_fields.append("username")
        if user.student_id != student_id:
            user.student_id = student_id
            updated_fields.append("student_id")
        if user.first_name != first_name:
            user.first_name = first_name
            updated_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            updated_fields.append("last_name")
        if not user.is_active:
            user.is_active = True
            updated_fields.append("is_active")

        if created or not user.check_password(DEMO_PASSWORD):
            user.set_password(DEMO_PASSWORD)
            updated_fields.append("password")

        if updated_fields:
            user.save(update_fields=updated_fields)

        return user

    def _get_or_create_conversation(self, *, item: Item, created_by, participants):
        conversation = (
            Conversation.objects.filter(item=item, created_by=created_by)
            .order_by("id")
            .first()
        )
        if conversation is None:
            conversation = Conversation.objects.create(item=item, created_by=created_by)

        conversation.participants.add(*participants)
        return conversation

    def _seed_messages(self, conversation: Conversation, owner, contact_user) -> int:
        seeded_messages = [
            (
                contact_user,
                "Hi, I think this backpack might be mine. It should have a blue notebook in the front pocket.",
            ),
            (
                owner,
                "Thanks for reaching out. I did see a blue notebook inside. Can you confirm the laptop brand too?",
            ),
            (
                contact_user,
                "Yes, it is a silver Dell laptop. I can meet at the C.A.W. Student Centre this afternoon.",
            ),
        ]

        ensured = 0
        for sender, content in seeded_messages:
            _, created = Message.objects.get_or_create(
                conversation=conversation,
                sender=sender,
                content=content,
                defaults={"is_read": sender == contact_user, "read_at": timezone.now()},
            )
            ensured += 1 if created else 0

        unread_owner_message = (
            Message.objects.filter(conversation=conversation, sender=owner)
            .order_by("-created_at")
            .first()
        )
        if unread_owner_message is not None:
            unread_owner_message.is_read = False
            unread_owner_message.read_at = None
            unread_owner_message.save(update_fields=["is_read", "read_at"])

        return len(seeded_messages)
