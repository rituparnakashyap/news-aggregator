from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email import utils as email_utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from news_aggregator.config.schema import DeliveryConfig, EmailDeliveryConfig

logger = logging.getLogger(__name__)


def _markdown_to_html(md: str) -> str:
    import markdown  # lazy import — optional dependency
    body = markdown.markdown(md, extensions=["tables", "fenced_code"])
    return (
        "<html><head><meta charset=\"utf-8\"></head>"
        f"<body>{body}</body></html>"
    )


def _build_message(
    subject: str,
    html_body: str,
    from_addr: str,
    recipients: list[str],
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send_smtp(
    msg: MIMEMultipart,
    host: str,
    port: int,
    user: str,
    password: str,
) -> None:
    envelope_from = email_utils.parseaddr(msg["From"])[1]
    recipients = [addr.strip() for addr in msg["To"].split(",")]
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as server:
                if user and password:
                    server.login(user, password)
                server.sendmail(envelope_from, recipients, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                if port == 587:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.sendmail(envelope_from, recipients, msg.as_string())
    except Exception as e:
        logger.warning("Failed to send email digest: %s", e)


def send_email_digest(
    markdown_content: str,
    cfg: EmailDeliveryConfig,
    env: dict[str, str],
) -> None:
    host = env.get("SMTP_HOST", "")
    if not host:
        logger.warning("Email delivery skipped: SMTP_HOST not configured")
        return

    port = int(env.get("SMTP_PORT", "587"))
    user = env.get("SMTP_USER", "")
    password = env.get("SMTP_PASSWORD", "")
    from_addr = env.get("EMAIL_FROM", user)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"{cfg.subject_prefix} {date_str}"

    html_body = _markdown_to_html(markdown_content)
    msg = _build_message(subject, html_body, from_addr, cfg.recipients)
    _send_smtp(msg, host, port, user, password)
    logger.info("Email digest sent to %s", cfg.recipients)


def dispatch_deliveries(
    markdown_content: str,
    deliveries: list[DeliveryConfig],
    env: dict[str, str],
) -> None:
    for delivery in deliveries:
        if delivery.type == "email":
            send_email_digest(markdown_content, delivery, env)
        # future: elif delivery.type == "slack": send_slack_digest(...)
        else:
            logger.warning("Unknown delivery type %r — skipped", delivery.type)
