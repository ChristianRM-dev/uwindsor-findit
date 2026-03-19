from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.chat.forms import ContactOwnerForm, MessageReplyForm
from apps.chat.models import Conversation
from apps.chat.services import (
    get_conversation_queryset_for_user,
    get_or_create_conversation_for_item,
    mark_conversation_as_read,
    send_message,
)
from apps.core.models import UserActivity
from apps.core.services import track_activity
from apps.listings.models import Item


@login_required
def contact_owner_view(request: HttpRequest, item_id: int) -> HttpResponse:
    item = get_object_or_404(
        Item.objects.filter(is_visible=True).select_related("category", "location", "reporter"),
        pk=item_id,
    )
    if item.reporter_id == request.user.id:
        messages.warning(request, "You cannot contact yourself about your own item.")
        return redirect("listings:item_detail_public", pk=item.pk)

    form = ContactOwnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        conversation = get_or_create_conversation_for_item(
            item=item,
            sender=request.user,
            owner=item.reporter,
        )
        send_message(
            conversation=conversation,
            sender=request.user,
            content=form.cleaned_data["message"],
        )
        track_activity(
            request,
            UserActivity.ActivityType.MESSAGE,
            item=item,
            metadata={
                "conversation_id": conversation.id,
                "context": "contact_owner",
            },
        )
        messages.success(request, "Message sent successfully.")
        return redirect("chat:message_thread", conversation_id=conversation.pk)

    context = {
        "form": form,
        "item": item,
        "owner": item.reporter,
        "cancel_url": reverse("listings:item_detail_public", kwargs={"pk": item.pk}),
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Browse Items", "url": reverse("listings:search_results"), "active": False},
            {"label": item.title, "url": reverse("listings:item_detail_public", kwargs={"pk": item.pk}), "active": False},
            {"label": "Contact Owner", "url": None, "active": True},
        ],
    }
    return render(request, "chat/contact_owner.html", context)


@login_required
def message_list_view(request: HttpRequest) -> HttpResponse:
    conversations = get_conversation_queryset_for_user(request.user)
    conversation_cards = []
    for conversation in conversations:
        other_participant = next(
            (participant for participant in conversation.loaded_participants if participant.id != request.user.id),
            None,
        )
        latest_message = conversation.latest_messages[0] if conversation.latest_messages else None
        conversation_cards.append(
            {
                "conversation": conversation,
                "other_participant": other_participant,
                "latest_message": latest_message,
                "unread_count": conversation.unread_count,
            }
        )

    context = {
        "conversation_cards": conversation_cards,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Messages", "url": None, "active": True},
        ],
    }
    return render(request, "chat/message_list.html", context)


@login_required
def message_thread_view(request: HttpRequest, conversation_id: int) -> HttpResponse:
    conversation = get_object_or_404(
        Conversation.objects.select_related("item")
        .prefetch_related("participants", "messages__sender"),
        pk=conversation_id,
    )
    if not conversation.participants.filter(pk=request.user.pk).exists():
        raise Http404("Conversation not found.")

    if request.method == "POST":
        form = MessageReplyForm(request.POST)
        if form.is_valid():
            send_message(
                conversation=conversation,
                sender=request.user,
                content=form.cleaned_data["message"],
            )
            track_activity(
                request,
                UserActivity.ActivityType.MESSAGE,
                item=conversation.item,
                metadata={
                    "conversation_id": conversation.id,
                    "context": "thread_reply",
                },
            )
            messages.success(request, "Reply sent.")
            return redirect("chat:message_thread", conversation_id=conversation.pk)
    else:
        form = MessageReplyForm()

    mark_conversation_as_read(conversation=conversation, user=request.user)
    thread_messages = conversation.messages.select_related("sender").all()
    other_participant = conversation.participants.exclude(pk=request.user.pk).first()

    context = {
        "conversation": conversation,
        "thread_messages": thread_messages,
        "other_participant": other_participant,
        "form": form,
        "breadcrumb_items": [
            {"label": "Home", "url": reverse("core:home"), "active": False},
            {"label": "Messages", "url": reverse("chat:message_list"), "active": False},
            {"label": conversation.item.title if conversation.item else f"Conversation #{conversation.pk}", "url": None, "active": True},
        ],
    }
    return render(request, "chat/message_thread.html", context)
