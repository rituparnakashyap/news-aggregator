from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, call, patch

import pytest

from news_aggregator.config.schema import EmailDeliveryConfig
from news_aggregator.output.emailer import (
    _build_message,
    _markdown_to_html,
    _send_smtp,
    dispatch_deliveries,
    send_email_digest,
)

SAMPLE_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USER": "user@example.com",
    "SMTP_PASSWORD": "secret",
    "EMAIL_FROM": "Digest <user@example.com>",
}

SAMPLE_CFG = EmailDeliveryConfig(
    type="email",
    recipients=["alice@example.com", "bob@example.com"],
    subject_prefix="[Test Digest]",
)


# --- _markdown_to_html ---

def test_markdown_to_html_contains_h1():
    html = _markdown_to_html("# Hello World")
    assert "<h1>" in html


def test_markdown_to_html_wraps_in_skeleton():
    html = _markdown_to_html("text")
    assert "<html>" in html
    assert "<body>" in html


def test_markdown_to_html_converts_bold():
    html = _markdown_to_html("**bold**")
    assert "<strong>" in html


# --- _build_message ---

def test_build_message_subject():
    msg = _build_message("My Subject", "<p>hi</p>", "from@x.com", ["to@x.com"])
    assert msg["Subject"] == "My Subject"


def test_build_message_from_header():
    msg = _build_message("S", "<p>hi</p>", "from@x.com", ["to@x.com"])
    assert msg["From"] == "from@x.com"


def test_build_message_to_header_joined():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["a@x.com", "b@x.com"])
    assert "a@x.com" in msg["To"]
    assert "b@x.com" in msg["To"]


def test_build_message_has_html_part():
    msg = _build_message("S", "<p>body</p>", "f@x.com", ["t@x.com"])
    payloads = msg.get_payload()
    assert any(p.get_content_type() == "text/html" for p in payloads)


# --- _send_smtp ---

def test_send_smtp_starttls_on_port_587():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["t@x.com"])
    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        _send_smtp(msg, "smtp.example.com", 587, "user", "pass")
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "pass")
    mock_server.sendmail.assert_called_once()


def test_send_smtp_uses_smtp_ssl_on_port_465():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["t@x.com"])
    mock_server = MagicMock()
    with patch("smtplib.SMTP_SSL") as mock_ssl_cls:
        mock_ssl_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_ssl_cls.return_value.__exit__ = MagicMock(return_value=False)
        _send_smtp(msg, "smtp.example.com", 465, "user", "pass")
    mock_ssl_cls.assert_called_once_with("smtp.example.com", 465)
    mock_server.login.assert_called_once_with("user", "pass")


def test_send_smtp_no_login_without_credentials():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["t@x.com"])
    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        _send_smtp(msg, "smtp.example.com", 587, "", "")
    mock_server.login.assert_not_called()


def test_send_smtp_no_starttls_on_port_25():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["t@x.com"])
    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        _send_smtp(msg, "relay.internal", 25, "", "")
    mock_server.starttls.assert_not_called()


def test_send_smtp_swallows_exception():
    msg = _build_message("S", "<p>hi</p>", "f@x.com", ["t@x.com"])
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.side_effect = smtplib.SMTPException("connection refused")
        # Should not raise
        _send_smtp(msg, "bad-host", 587, "u", "p")


# --- send_email_digest ---

def test_send_email_skips_when_no_smtp_host():
    with patch("news_aggregator.output.emailer._send_smtp") as mock_send:
        send_email_digest("# md", SAMPLE_CFG, {})
    mock_send.assert_not_called()


def test_send_email_calls_send_smtp():
    with patch("news_aggregator.output.emailer._send_smtp") as mock_send:
        send_email_digest("# md", SAMPLE_CFG, SAMPLE_ENV)
    mock_send.assert_called_once()


def test_send_email_subject_contains_prefix():
    captured = {}

    def fake_send(msg, host, port, user, password):
        captured["subject"] = msg["Subject"]

    with patch("news_aggregator.output.emailer._send_smtp", side_effect=fake_send):
        send_email_digest("# md", SAMPLE_CFG, SAMPLE_ENV)

    assert captured["subject"].startswith("[Test Digest]")


# --- dispatch_deliveries ---

def test_dispatch_deliveries_calls_send_email_digest():
    with patch("news_aggregator.output.emailer.send_email_digest") as mock_email:
        dispatch_deliveries("# md", [SAMPLE_CFG], SAMPLE_ENV)
    mock_email.assert_called_once_with("# md", SAMPLE_CFG, SAMPLE_ENV)


def test_dispatch_deliveries_handles_multiple_email_targets():
    cfg2 = EmailDeliveryConfig(type="email", recipients=["c@example.com"])
    with patch("news_aggregator.output.emailer.send_email_digest") as mock_email:
        dispatch_deliveries("# md", [SAMPLE_CFG, cfg2], SAMPLE_ENV)
    assert mock_email.call_count == 2


def test_dispatch_deliveries_empty_list_does_nothing():
    with patch("news_aggregator.output.emailer.send_email_digest") as mock_email:
        dispatch_deliveries("# md", [], SAMPLE_ENV)
    mock_email.assert_not_called()
