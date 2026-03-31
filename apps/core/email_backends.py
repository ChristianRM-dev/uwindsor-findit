from __future__ import annotations

import base64
import json
import logging
from email.mime.base import MIMEBase
from email.utils import parseaddr
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage

logger = logging.getLogger(__name__)


class ApiEmailBackend(BaseEmailBackend):
    """Send Django email messages through the Brevo transactional email API."""

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
        if provider != "brevo":
            raise ImproperlyConfigured(
                f"Unsupported EMAIL_PROVIDER {provider!r}. Expected 'brevo'."
            )

        api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        if not api_key:
            raise ImproperlyConfigured(
                "BREVO_API_KEY must be set when EMAIL_PROVIDER is 'brevo'."
            )

        payload = self._build_brevo_payload(message)
        self._log_request_debug(payload)
        request = Request(
            getattr(settings, "BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=float(getattr(settings, "BREVO_REQUEST_TIMEOUT", 10)),
            ) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                self._log_response_debug(
                    status=getattr(response, "status", "unknown"),
                    body=response_body,
                )
        except HTTPError as exc:
            if self.fail_silently:
                return False
            detail = exc.read().decode("utf-8", errors="replace")
            self._log_error_debug(f"Brevo API request failed with status {exc.code}: {detail}")
            raise RuntimeError(
                f"Brevo API request failed with status {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            if self.fail_silently:
                return False
            self._log_error_debug("Brevo API request failed before receiving a response.")
            raise RuntimeError("Brevo API request failed.") from exc

        return True

    def _build_brevo_payload(self, message: EmailMessage) -> dict[str, Any]:
        sender = self._serialize_mailbox(
            message.from_email or settings.DEFAULT_FROM_EMAIL,
            field_name="DEFAULT_FROM_EMAIL",
        )

        payload: dict[str, Any] = {
            "sender": sender,
            "to": self._serialize_recipients(message.to),
            "subject": message.subject or "",
        }

        body = message.body or ""
        html_body = None
        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                html_body = alternative.content
                break

        if body:
            payload["textContent"] = body
        if html_body:
            payload["htmlContent"] = html_body
        if not body and not html_body:
            payload["textContent"] = ""

        if message.cc:
            payload["cc"] = self._serialize_recipients(message.cc)
        if message.bcc:
            payload["bcc"] = self._serialize_recipients(message.bcc)
        if message.reply_to:
            payload["replyTo"] = self._serialize_mailbox(
                message.reply_to[0],
                field_name="reply_to",
            )
        if message.extra_headers:
            payload["headers"] = dict(message.extra_headers)

        attachments = self._serialize_attachments(message.attachments)
        if attachments:
            payload["attachment"] = attachments

        return payload

    def _serialize_recipients(self, recipients: list[str]) -> list[dict[str, str]]:
        return [
            self._serialize_mailbox(recipient, field_name="recipient")
            for recipient in recipients
        ]

    def _serialize_mailbox(self, raw_value: str | None, *, field_name: str) -> dict[str, str]:
        name, email = parseaddr(raw_value or "")
        if not email:
            raise ImproperlyConfigured(f"{field_name} must include a valid email address.")

        mailbox = {"email": email}
        if name:
            mailbox["name"] = name
        return mailbox

    def _serialize_attachments(self, attachments) -> list[dict[str, str]]:
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

            filename, content, _mimetype = attachment
            if isinstance(content, str):
                content = content.encode("utf-8")
            serialized.append(
                {
                    "name": filename,
                    "content": base64.b64encode(content).decode("ascii"),
                }
            )
        return serialized

    def _debug_enabled(self) -> bool:
        return bool(getattr(settings, "EMAIL_DEBUG", False))

    def _log_request_debug(self, payload: dict[str, Any]) -> None:
        if not self._debug_enabled():
            return

        summary = {
            "sender": payload.get("sender"),
            "to": payload.get("to", []),
            "cc": payload.get("cc", []),
            "bcc": payload.get("bcc", []),
            "replyTo": payload.get("replyTo"),
            "subject": payload.get("subject", ""),
            "has_text": "textContent" in payload,
            "has_html": "htmlContent" in payload,
            "attachments": [item.get("name") for item in payload.get("attachment", [])],
        }
        logger.info("Brevo email request %s", json.dumps(summary, ensure_ascii=True))

    def _log_response_debug(self, *, status: Any, body: str) -> None:
        if not self._debug_enabled():
            return
        logger.info(
            "Brevo email response %s",
            json.dumps({"status": status, "body": body}, ensure_ascii=True),
        )

    def _log_error_debug(self, message: str) -> None:
        if not self._debug_enabled():
            return
        logger.info(message)
