from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

from .email_verification import send_verification_email


class VerificationEmailDeliveryError(Exception):
    """Raised when the verification email could not be sent."""


def require_email_verification() -> bool:
    return getattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)


def create_user_from_register_form(form):
    """
    Creates and returns the user from RegisterForm, respecting email verification config.
    """
    user = form.save(commit=False)
    user.is_active = not require_email_verification()
    user.save()
    form.save_m2m()
    return user


def try_authenticate_user(request, user, raw_password: str):
    """
    Authenticates using username/email and password. Returns user or None.
    """
    return authenticate(request, username=user.username, password=raw_password)


def handle_post_registration(request, user, raw_password: str):
    """
    Returns a dict describing next action after registration.
    - If verification required: sends email and returns {"verification_required": True}
    - Else: returns {"verification_required": False, "authed_user": <User|None>}
    """
    if require_email_verification():
        try:
            send_verification_email(request, user)
        except Exception as exc:
            raise VerificationEmailDeliveryError(
                "Verification email delivery failed."
            ) from exc
        return {"verification_required": True}

    authed = try_authenticate_user(request, user, raw_password)
    return {"verification_required": False, "authed_user": authed}
