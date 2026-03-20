from __future__ import annotations

import base64
import json
from email.utils import parseaddr
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
        if provider == "brevo":
            return self._send_via_brevo(message)
        if provider == "resend":
            return self._send_via_resend(message)

        raise ImproperlyConfigured(
            f"Unsupported EMAIL_PROVIDER {provider!r}. Expected 'brevo' or 'resend'."
        )

    def _send_via_brevo(self, message: EmailMessage) -> bool:
        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "BREVO_API_KEY must be set when EMAIL_PROVIDER is 'brevo'."
            )

        payload = self._build_brevo_payload(message)
        request = Request(
            getattr(
                settings,
                "BREVO_API_URL",
                "https://api.brevo.com/v3/smtp/email",
            ),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            method="POST",
        )

        return self._perform_request(
            request,
            timeout=float(getattr(settings, "BREVO_REQUEST_TIMEOUT", 10)),
            provider_label="Brevo",
        )

    def _send_via_resend(self, message: EmailMessage) -> bool:
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

        return self._perform_request(
            request,
            timeout=float(getattr(settings, "RESEND_REQUEST_TIMEOUT", 10)),
            provider_label="Resend",
        )

    def _perform_request(
        self,
        request: Request,
        *,
        timeout: float,
        provider_label: str,
    ) -> bool:
        try:
            with urlopen(request, timeout=timeout) as response:
                response.read()
        except HTTPError as exc:
            if self.fail_silently:
                return False
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{provider_label} API request failed with status {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            if self.fail_silently:
                return False
            raise RuntimeError(f"{provider_label} API request failed.") from exc

        return True

    def _build_brevo_payload(self, message: EmailMessage) -> dict[str, Any]:
        sender = self._parse_named_email(
            message.from_email or settings.DEFAULT_FROM_EMAIL,
            field_name="DEFAULT_FROM_EMAIL",
        )

        payload: dict[str, Any] = {
            "sender": sender,
            "to": self._serialize_brevo_recipients(message.to),
            "subject": message.subject or "",
        }

        body = message.body or ""
        html_body = self._get_html_body(message)
        if body:
            payload["textContent"] = body
        if html_body:
            payload["htmlContent"] = html_body
        if not body and not html_body:
            payload["textContent"] = ""

        if message.cc:
            payload["cc"] = self._serialize_brevo_recipients(message.cc)
        if message.bcc:
            payload["bcc"] = self._serialize_brevo_recipients(message.bcc)
        if message.reply_to:
            payload["replyTo"] = self._parse_named_email(
                message.reply_to[0],
                field_name="reply_to",
            )
        if message.extra_headers:
            payload["headers"] = dict(message.extra_headers)

        attachments = self._serialize_brevo_attachments(message.attachments)
        if attachments:
            payload["attachment"] = attachments

        return payload

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
        html_body = self._get_html_body(message)
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

    def _get_html_body(self, message: EmailMessage) -> str | None:
        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                return alternative.content
        return None

    def _parse_named_email(self, value: str, *, field_name: str) -> dict[str, str]:
        display_name, email_address = parseaddr(value)
        if not email_address or "@" not in email_address:
            raise ImproperlyConfigured(
                f"{field_name} must contain a valid sender address."
            )

        parsed = {"email": email_address}
        if display_name:
            parsed["name"] = display_name
        return parsed

    def _serialize_brevo_recipients(
        self,
        recipients: list[str] | tuple[str, ...],
    ) -> list[dict[str, str]]:
        serialized = []
        for recipient in recipients:
            parsed = self._parse_named_email(recipient, field_name="recipient")
            serialized.append(parsed)
        return serialized

    def _serialize_brevo_attachments(
        self,
        attachments,
    ) -> list[dict[str, str]]:
        serialized: list[dict[str, str]] = []
        for attachment in attachments:
            if isinstance(attachment, MIMEBase):
                content = attachment.get_payload(decode=True) or b""
                serialized.append(
                    {
                        "name": attachment.get_filename() or "attachment",
                        "content": base64.b64encode(content).decode("ascii"),
                    }
                )
                continue

            filename, content, mimetype = attachment
            if isinstance(content, str):
                content = content.encode("utf-8")
            serialized.append(
                {
                    "name": filename,
                    "content": base64.b64encode(content).decode("ascii"),
                }
            )
        return serialized

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
