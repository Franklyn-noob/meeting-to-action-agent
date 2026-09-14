#!/usr/bin/env python3
"""Standalone smoke test for the real (SMTP) email sender.

Run this locally BEFORE wiring SMTP into the full demo, to confirm the Gmail
SMTP credentials (SMTP_EMAIL + SMTP_APP_PASSWORD) authenticate and can actually
send a real email. Credentials are read from the environment, or (as a local
convenience) from a ./groq.env file containing ``smtp_email=`` / ``smtp_password=``
lines — the secret values are never printed.

    python smoke_smtp.py                                  # sends to the SMTP_EMAIL account (self)
    TO_EMAIL=other@example.com python smoke_smtp.py       # send to a different recipient

Exits 0 on success, 1 on failure. Uses only the Python standard library.
"""
import os
import ssl
import sys
from email.message import EmailMessage


def load_env_file(path: str = "groq.env") -> dict[str, str]:
    """Minimal dotenv parser: KEY=VALUE lines only (secrets stay out of logs)."""
    env: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def first_env(names: tuple[str, ...], envf: dict[str, str]) -> str | None:
    for n in names:
        v = os.environ.get(n) or envf.get(n)
        if v:
            return v
    return None


def main() -> int:
    envf = load_env_file()
    email = first_env(("SMTP_EMAIL", "smtp_email"), envf)
    app_password = first_env(
        ("SMTP_APP_PASSWORD", "SMTP_PASSWORD", "smtp_password"), envf
    )
    # Strip stray whitespace/NBSP (app passwords are whitespace-free; this also
    # fixes the NBSP-separated 4x4 grouping from Gmail's UI).
    if app_password:
        app_password = "".join(app_password.split())
    recipient = os.environ.get("TO_EMAIL", email)
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not email or not app_password:
        print("FAIL: SMTP_EMAIL / SMTP_APP_PASSWORD not set and not found in groq.env.")
        print("      Add to ./groq.env:")
        print("        smtp_email=your.address@gmail.com")
        print("        smtp_password=<your-gmail-app-password>")
        print("      Or export SMTP_EMAIL / SMTP_APP_PASSWORD in the environment.")
        return 1

    import smtplib

    print(f"host={host}:{port}  from={email}  to={recipient}  "
          f"(app password: {'set' if app_password else 'missing'})")

    msg = EmailMessage()
    msg["From"] = email
    msg["To"] = recipient
    msg["Subject"] = "Smoke test: SMTP email sender works"
    msg.set_content(
        "This is an automated smoke test from the Strand meeting-agent demo. "
        "If you received this, real SMTP email delivery is working."
    )

    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover - certifi is virtually always present
        ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(email, app_password)
            smtp.sendmail(email, [recipient], msg.as_string())
            smtp.quit()
    except smtplib.SMTPAuthenticationError as e:
        print(f"FAIL: SMTP authentication failed (bad app password?) -> {type(e).__name__}: {e.smtp_error}")
        return 1
    except Exception as e:  # noqa: BLE001 - report any failure without leaking secrets
        print(f"FAIL: SMTP error -> {type(e).__name__}: {e}")
        return 1

    print("PASS: real email sent via SMTP (check the recipient inbox).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
