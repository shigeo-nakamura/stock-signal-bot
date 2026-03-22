import os

from src.notifier import send_email


def test_dry_run_email(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    result = send_email("Test Subject", "Test Body")
    assert result is True


def test_missing_credentials_returns_false(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_TO", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    result = send_email("Test", "Test")
    assert result is False
