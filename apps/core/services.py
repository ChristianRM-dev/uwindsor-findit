from __future__ import annotations

from typing import Any

from apps.core.models import UserActivity


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
