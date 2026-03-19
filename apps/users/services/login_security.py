from __future__ import annotations

import hashlib
import math
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


def _normalize_identifier(identifier: str) -> str:
    return (identifier or "").strip().lower()


def _get_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _build_cache_key(*, request, identifier: str) -> str:
    raw_key = f"{_normalize_identifier(identifier)}|{_get_client_ip(request)}".encode()
    return "users:login-lockout:" + hashlib.sha256(raw_key).hexdigest()


def get_lockout_remaining_seconds(*, request, identifier: str) -> int:
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return 0

    state = cache.get(_build_cache_key(request=request, identifier=normalized_identifier))
    if not state or not state.get("locked_until"):
        return 0

    remaining = int((state["locked_until"] - timezone.now()).total_seconds())
    if remaining <= 0:
        clear_failed_login(request=request, identifier=normalized_identifier)
        return 0

    return remaining


def record_failed_login(*, request, identifier: str) -> int:
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return 0

    current_lockout = get_lockout_remaining_seconds(request=request, identifier=normalized_identifier)
    if current_lockout:
        return current_lockout

    cache_key = _build_cache_key(request=request, identifier=normalized_identifier)
    state = cache.get(cache_key) or {"count": 0}
    attempt_count = int(state.get("count", 0)) + 1

    failure_limit = int(getattr(settings, "LOGIN_FAILURE_LIMIT", 5))
    lockout_seconds = int(getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))
    if attempt_count >= failure_limit:
        locked_until = timezone.now() + timedelta(seconds=lockout_seconds)
        cache.set(
            cache_key,
            {"count": attempt_count, "locked_until": locked_until},
            timeout=lockout_seconds,
        )
        return lockout_seconds

    cache.set(cache_key, {"count": attempt_count}, timeout=lockout_seconds)
    return 0


def clear_failed_login(*, request, identifier: str) -> None:
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return

    cache.delete(_build_cache_key(request=request, identifier=normalized_identifier))


def format_lockout_message(seconds: int) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    if minutes == 1:
        return "Too many login attempts. Try again in about 1 minute."
    return f"Too many login attempts. Try again in about {minutes} minutes."
