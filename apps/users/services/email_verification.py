from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string


EMAIL_VERIFY_SALT = "findit-email-verify"


def build_absolute_uri(request, path: str) -> str:
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}{path}"


def make_verification_token(user_id: int) -> str:
    signer = TimestampSigner(salt=EMAIL_VERIFY_SALT)
    return signer.sign(str(user_id))


def unsign_verification_token(token: str) -> int:
    signer = TimestampSigner(salt=EMAIL_VERIFY_SALT)
    max_age = getattr(settings, "EMAIL_VERIFICATION_TOKEN_MAX_AGE", 60 * 60 * 24)

    unsigned = signer.unsign(token, max_age=max_age)  # may raise
    return int(unsigned)


def send_verification_email(request, user) -> None:
    token = make_verification_token(user.pk)
    verify_path = f"/auth/verify-email/{token}/"
    verify_url = build_absolute_uri(request, verify_path)

    subject = render_to_string("users/emails/verify_email_subject.txt", {}).strip()
    context = {"verify_url": verify_url}
    body = render_to_string("users/emails/verify_email_body.txt", context)
    html_body = render_to_string("users/emails/verify_email_body.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
