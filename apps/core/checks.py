from __future__ import annotations

from email.utils import parseaddr

from django.conf import settings
from django.core.checks import Error, Warning, register

PUBLIC_MAILBOX_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "outlook.com",
    "yahoo.com",
}


@register()
def email_provider_configuration_check(app_configs, **kwargs):
    provider = getattr(settings, "EMAIL_PROVIDER", "").strip().lower()
    if provider not in {"brevo", "resend"}:
        return []

    issues = []
    default_from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "").strip()

    if provider == "brevo":
        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            issues.append(
                Error(
                    "BREVO_API_KEY must be set when EMAIL_PROVIDER is 'brevo'.",
                    id="core.E101",
                )
            )
    else:
        api_key = getattr(settings, "RESEND_API_KEY", "").strip()
        if not api_key:
            issues.append(
                Error(
                    "RESEND_API_KEY must be set when EMAIL_PROVIDER is 'resend'.",
                    id="core.E001",
                )
            )

    if not default_from_email:
        issues.append(
            Error(
                "DJANGO_DEFAULT_FROM_EMAIL must be set when using an HTTP email provider.",
                id="core.E002",
            )
        )
        return issues

    _, email_address = parseaddr(default_from_email)
    if not email_address or "@" not in email_address:
        issues.append(
            Error(
                "DJANGO_DEFAULT_FROM_EMAIL must contain a valid sender address.",
                hint=(
                    "Use a value such as 'FindIt UWindsor <sender@example.com>' "
                    "with a sender address that your email provider accepts."
                ),
                id="core.E003",
            )
        )
        return issues

    domain = email_address.rsplit("@", 1)[1].lower()
    if domain.endswith("findit.local"):
        issues.append(
            Error(
                "DJANGO_DEFAULT_FROM_EMAIL uses a local-only domain that an email API cannot send from.",
                hint=(
                    "Use a real sender address such as your verified Brevo "
                    "sender, or switch to a verified Resend domain."
                ),
                id="core.E004",
            )
        )
        return issues

    if provider == "brevo" and domain in PUBLIC_MAILBOX_DOMAINS:
        issues.append(
            Warning(
                "DJANGO_DEFAULT_FROM_EMAIL is using a public mailbox domain with Brevo.",
                hint=(
                    "This can work for small demos if the sender is verified in "
                    "Brevo, but deliverability may be lower without domain "
                    "authentication."
                ),
                id="core.W101",
            )
        )

    if provider == "resend" and domain == "resend.dev":
        issues.append(
            Warning(
                "DJANGO_DEFAULT_FROM_EMAIL is using Resend's shared testing domain.",
                hint=(
                    "This is suitable for smoke tests and Resend test inboxes, "
                    "but real-user flows require your own verified sender domain."
                ),
                id="core.W001",
            )
        )

        if getattr(settings, "REQUIRE_EMAIL_VERIFICATION", True):
            issues.append(
                Warning(
                    "REQUIRE_EMAIL_VERIFICATION is enabled while using resend.dev.",
                    hint=(
                        "New users will not be able to complete email "
                        "verification on real addresses until you verify a "
                        "sender domain. For demos, disable "
                        "REQUIRE_EMAIL_VERIFICATION or use pre-created accounts."
                    ),
                    id="core.W002",
                )
            )

    return issues
