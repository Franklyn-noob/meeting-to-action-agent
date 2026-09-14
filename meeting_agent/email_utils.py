"""Email delivery abstraction.

The agent must *never* put email credentials in prompts or tool code.
Locally the email is simulated (logged only), which lets the full pipeline
run offline for demos and tests. The deployed variant uses SES / SMTP via
credentials held in AWS Secrets Manager (wired only in the deploy phase).
"""
from __future__ import annotations

import os
import logging
from typing import Protocol

from meeting_agent.schemas import ActionItem, ActivityEvent, ActivityKind, EscalationReason, Task

logger = logging.getLogger(__name__)


class EmailDraft:
    """Result of drafting a follow-up email."""

    def __init__(self, to: list[str], subject: str, body: str):
        self.to = to
        self.subject = subject
        self.body = body

    def model_dump(self) -> dict:
        return {"to": self.to, "subject": self.subject, "body": self.body}


class EmailSender(Protocol):
    """Strategy for sending a drafted email."""

    def send(self, draft: EmailDraft) -> dict:
        ...  # returns a delivery receipt / status dict


class SimulatedEmailSender:
    """Local/demo sender: logs the email instead of transmitting it.

    This is the default so the agent runs end-to-end with zero credentials.
    """

    def send(self, draft: EmailDraft) -> dict:
        logger.info("[simulated email] to=%s subject=%r", draft.to, draft.subject)
        return {
            "status": "simulated",
            "to": list(draft.to),
            "subject": draft.subject,
            "snippet": (draft.body[:120] + "...") if len(draft.body) > 123 else draft.body,
        }


class SesEmailSender:
    """Deploy-phase sender using Amazon SES via boto3.

    AWS credentials are resolved from the environment / IAM role at runtime —
    never hardcoded. Used only when PERSISTENCE/SENDER=real on the deployed
    AgentCore runtime.
    """

    def __init__(self, region: str | None = None) -> None:
        import boto3  # local import keeps the local path credential-free

        self._client = boto3.client("ses", region_name=region or os.getenv("AWS_REGION"))

    def send(self, draft: EmailDraft) -> dict:
        resp = self._client.send_email(
            Source="agent@example.com",
            Destination={"ToAddresses": draft.to},
            Message={
                "Subject": {"Data": draft.subject},
                "Body": {"Text": {"Data": draft.body}},
            },
        )
        return {"status": "sent", "MessageId": resp["MessageId"]}


class SmtpEmailSender:
    """Real email sender via Gmail SMTP (``smtp.gmail.com:587``, STARTTLS).

    Selected with ``EMAIL_PROVIDER=smtp`` (falls back to simulated otherwise).
    Sender address and app password are read from the environment — never
    hardcoded: ``SMTP_EMAIL`` / ``SMTP_APP_PASSWORD`` (or the lowercase
    ``smtp_email`` / ``smtp_password`` keys loaded from ``./groq.env`` by
    ``run_demo.sh``). Uses the stdlib ``smtplib``/``ssl`` modules, so no extra
    dependencies are required.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int = 587,
        email: str | None = None,
        app_password: str | None = None,
    ) -> None:
        self._host = host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self._port = int(port)
        self._email = email or _resolve_env("SMTP_EMAIL", "smtp_email")
        self._app_password = app_password or _resolve_env(
            "SMTP_APP_PASSWORD", "SMTP_PASSWORD", "smtp_password"
        )
        # App passwords are whitespace-free; strip stray separators (e.g.
        # non-breaking spaces that sneak in when copy/pasting a 4x4-grouped
        # Gmail app password from the UI).
        if self._app_password:
            self._app_password = "".join(self._app_password.split())

    def send(self, draft: EmailDraft) -> dict:
        if not self._email or not self._app_password:
            raise RuntimeError(
                "SMTP sender requires SMTP_EMAIL and SMTP_APP_PASSWORD "
                "(set in the environment, or add them to groq.env as smtp_email="
                "/smtp_password= ; run_demo.sh loads them for EMAIL_PROVIDER=smtp)"
            )
        import smtplib  # stdlib; local import keeps the offline path dependency-light
        import ssl
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self._email
        msg["To"] = ", ".join(draft.to)
        msg["Subject"] = draft.subject
        msg.set_content(draft.body)
        ctx = ssl.create_default_context()
        # Prefer certifi's CA bundle (available via httpx) so TLS verification
        # works even on Python builds with no OS trust store.
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:  # pragma: no cover - certifi is virtually always present
            pass
        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(self._email, self._app_password)
            smtp.sendmail(self._email, draft.to, msg.as_string())
        return {
            "status": "sent",
            "from": self._email,
            "to": list(draft.to),
            "subject": draft.subject,
        }


def _resolve_env(*names: str) -> str | None:
    """Return the first non-empty env var among ``names`` (case-sensitive)."""
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    return None


def get_email_sender() -> EmailSender:
    """Pick the sender strategy from the environment.

    Precedence: ``EMAIL_PROVIDER=smtp`` -> real Gmail SMTP; ``EMAIL_SENDER=ses``
    -> SES; otherwise the local ``SimulatedEmailSender`` (default, offline).
    """
    if os.getenv("EMAIL_PROVIDER", "").lower() == "smtp":
        return SmtpEmailSender()
    if os.getenv("EMAIL_SENDER", "simulated").lower() == "ses":
        return SesEmailSender()
    return SimulatedEmailSender()


def escalate_activity_summary(reason: EscalationReason, detail: str) -> ActivityEvent:
    """Helper: build an activity event marking a real escalation."""
    return ActivityEvent(
        kind=ActivityKind.ESCALATION,
        summary=detail,
        escalation_reason=reason,
    )
