from __future__ import annotations

import base64
import json
from email.mime.base import MIMEBase
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage


class ApiEmailBackend(BaseEmailBackend):
    """Send Django email messages through an HTTP API provider."""

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            if self._send(message):
                sent_count += 1
        return sent_count

    def _send(self, message: EmailMessage) -> bool:
        if not message.recipients():
            return False

        provider = getattr(settings, "EMAIL_PROVIDER", "").strip().lower()
        if provider != "resend":
            raise ImproperlyConfigured(
                f"Unsupported EMAIL_PROVIDER {provider!r}. Expected 'resend'."
            )

        api_key = getattr(settings, "RESEND_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "RESEND_API_KEY must be set when EMAIL_PROVIDER is 'resend'."
            )

        payload = self._build_resend_payload(message)
        request = Request(
            getattr(settings, "RESEND_API_URL", "https://api.resend.com/emails"),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=float(getattr(settings, "RESEND_REQUEST_TIMEOUT", 10)),
            ) as response:
                response.read()
        except HTTPError as exc:
            if self.fail_silently:
                return False
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Resend API request failed with status {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            if self.fail_silently:
                return False
            raise RuntimeError("Resend API request failed.") from exc

        return True

    def _build_resend_payload(self, message: EmailMessage) -> dict[str, Any]:
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        if not from_email:
            raise ImproperlyConfigured(
                "DEFAULT_FROM_EMAIL must be set for the Resend email backend."
            )

        payload: dict[str, Any] = {
            "from": from_email,
            "to": list(message.to),
            "subject": message.subject or "",
        }

        body = message.body or ""
        html_body = None
        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                html_body = alternative.content
                break

        if body:
            payload["text"] = body
        if html_body:
            payload["html"] = html_body
        if not body and not html_body:
            payload["text"] = ""

        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        if message.extra_headers:
            payload["headers"] = dict(message.extra_headers)

        attachments = self._serialize_attachments(message.attachments)
        if attachments:
            payload["attachments"] = attachments

        return payload

    def _serialize_attachments(self, attachments) -> list[dict[str, str]]:
        serialized: list[dict[str, str]] = []
        for attachment in attachments:
            if isinstance(attachment, MIMEBase):
                content = attachment.get_payload(decode=True) or b""
                serialized.append(
                    {
                        "filename": attachment.get_filename() or "attachment",
                        "content": base64.b64encode(content).decode("ascii"),
                        "content_type": attachment.get_content_type(),
                    }
                )
                continue

            filename, content, mimetype = attachment
            if isinstance(content, str):
                content = content.encode("utf-8")
            serialized.append(
                {
                    "filename": filename,
                    "content": base64.b64encode(content).decode("ascii"),
                    "content_type": mimetype or "application/octet-stream",
                }
            )
        return serialized
