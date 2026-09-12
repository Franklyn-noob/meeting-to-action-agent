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


def get_email_sender() -> EmailSender:
    """Pick the sender strategy from the environment."""
    if os.getenv("EMAIL_SENDER", "simulated") == "ses":
        return SesEmailSender()
    return SimulatedEmailSender()


def escalate_activity_summary(reason: EscalationReason, detail: str) -> ActivityEvent:
    """Helper: build an activity event marking a real escalation."""
    return ActivityEvent(
        kind=ActivityKind.ESCALATION,
        summary=detail,
        escalation_reason=reason,
    )
