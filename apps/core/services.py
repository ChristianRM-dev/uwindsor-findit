from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Notification, UserActivity


def _get_or_create_session_key(request) -> str:
    session = getattr(request, "session", None)
    if session is None:
        return ""

    session_key = session.session_key
    if session_key:
        return session_key

    session.save()
    return session.session_key or ""


def track_activity(
    request,
    activity_type: str,
    *,
    item=None,
    search_query: str = "",
    metadata: dict[str, Any] | None = None,
    page_path: str | None = None,
    user=None,
):
    activity_user = user
    if activity_user is None:
        request_user = getattr(request, "user", None)
        if request_user is not None and getattr(request_user, "is_authenticated", False):
            activity_user = request_user

    return UserActivity.objects.create(
        user=activity_user,
        activity_type=activity_type,
        page_path=page_path or getattr(request, "path", ""),
        search_query=(search_query or "").strip(),
        item=item,
        session_key=_get_or_create_session_key(request),
        metadata=metadata or {},
    )


def get_unread_notification_count(user) -> int:
    if not user.is_authenticated:
        return 0

    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_all_notifications_as_read(*, user) -> int:
    if not user.is_authenticated:
        return 0

    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )


def _display_name(user) -> str:
    full_name = user.get_full_name().strip()
    if full_name:
        return full_name
    return user.email or user.get_username()


def create_notification(
    *,
    recipient,
    notification_type: str,
    title: str,
    body: str,
    link_path: str = "",
    item=None,
    claim=None,
    email_subject: str | None = None,
    email_body: str | None = None,
):
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
        item=item,
        claim=claim,
    )

    if recipient.email:
        try:
            send_mail(
                email_subject or f"[FindIt] {title}",
                email_body or body,
                settings.DEFAULT_FROM_EMAIL,
                [recipient.email],
            )
        except Exception:
            return notification

        notification.email_sent = True
        notification.save(update_fields=["email_sent"])

    return notification


def notify_claim_submitted(*, claim):
    reporter = claim.item.reporter
    if reporter_id := getattr(reporter, "id", None):
        if reporter_id == claim.claimant_id:
            return None

    link_path = reverse("listings:claim_detail", kwargs={"claim_id": claim.id})
    claimant_name = _display_name(claim.claimant)
    item_title = claim.item.title
    title = f"New claim for {item_title}"
    body = f"{claimant_name} submitted a claim for your item."

    return create_notification(
        recipient=reporter,
        notification_type=Notification.NotificationType.CLAIM_SUBMITTED,
        title=title,
        body=body,
        link_path=link_path,
        item=claim.item,
        claim=claim,
        email_body=(
            f"A new claim was submitted for \"{item_title}\".\n\n"
            f"Claimant: {claimant_name}\n"
            f"Review it here: {link_path}"
        ),
    )


def notify_claim_reviewed(*, claim, auto_closed: bool = False):
    link_path = reverse("listings:claim_detail", kwargs={"claim_id": claim.id})
    item_title = claim.item.title

    if claim.status == claim.Status.APPROVED:
        title = f"Claim approved for {item_title}"
        body = f"Your claim for {item_title} was approved."
        email_body = (
            f"Your claim for \"{item_title}\" was approved.\n\n"
            f"View the claim details here: {link_path}"
        )
    else:
        title = f"Claim rejected for {item_title}"
        if auto_closed:
            body = f"Your claim for {item_title} was closed because another claim was approved."
            email_body = (
                f"Your claim for \"{item_title}\" was closed because another claim for this item was approved.\n\n"
                f"View the claim details here: {link_path}"
            )
        else:
            body = f"Your claim for {item_title} was rejected."
            email_body = (
                f"Your claim for \"{item_title}\" was rejected.\n\n"
                f"View the claim details here: {link_path}"
            )

        reviewer_notes = (claim.reviewer_notes or "").strip()
        if reviewer_notes:
            body = f"{body} Reviewer notes: {reviewer_notes}"
            email_body = f"{email_body}\nReviewer notes: {reviewer_notes}"

    return create_notification(
        recipient=claim.claimant,
        notification_type=(
            Notification.NotificationType.CLAIM_APPROVED
            if claim.status == claim.Status.APPROVED
            else Notification.NotificationType.CLAIM_REJECTED
        ),
        title=title,
        body=body,
        link_path=link_path,
        item=claim.item,
        claim=claim,
        email_body=email_body,
    )
