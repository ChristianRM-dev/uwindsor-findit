from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.chat.models import Conversation, Message


def get_or_create_conversation_for_item(*, item, sender, owner):
    conversation = (
        Conversation.objects.filter(item=item)
        .filter(participants=sender)
        .filter(participants=owner)
        .distinct()
        .first()
    )

    if conversation is None:
        conversation = Conversation.objects.create(item=item, created_by=sender)
        conversation.participants.add(sender, owner)

    return conversation


def send_message(*, conversation, sender, content: str):
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content.strip(),
    )
    conversation.save(update_fields=["updated_at"])
    return message


def get_conversation_queryset_for_user(user):
    latest_messages = Prefetch(
        "messages",
        queryset=Message.objects.select_related("sender").order_by("-created_at"),
        to_attr="latest_messages",
    )
    participants = Prefetch(
        "participants",
        to_attr="loaded_participants",
    )

    return (
        Conversation.objects.filter(participants=user)
        .select_related("item", "created_by")
        .prefetch_related(latest_messages, participants)
        .annotate(
            unread_count=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender=user),
            )
        )
        .distinct()
    )


def mark_conversation_as_read(*, conversation, user):
    now = timezone.now()
    return Message.objects.filter(
        conversation=conversation,
        is_read=False,
    ).exclude(sender=user).update(is_read=True, read_at=now)


def get_unread_message_count(user) -> int:
    if not user.is_authenticated:
        return 0

    return Message.objects.filter(
        conversation__participants=user,
        is_read=False,
    ).exclude(sender=user).count()
