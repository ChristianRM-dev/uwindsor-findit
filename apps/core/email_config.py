from __future__ import annotations

from typing import Mapping


API_EMAIL_BACKEND = "apps.core.email_backends.ApiEmailBackend"
CONSOLE_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


def resolve_email_backend(env: Mapping[str, str | None]) -> str:
    provider = (env.get("EMAIL_PROVIDER") or "").strip().lower()
    explicit_backend = (env.get("DJANGO_EMAIL_BACKEND") or "").strip()

    if explicit_backend:
        return explicit_backend
    if provider == "brevo":
        return API_EMAIL_BACKEND
    return CONSOLE_EMAIL_BACKEND
