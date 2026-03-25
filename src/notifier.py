from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def _get_credentials() -> tuple[str, str, str] | None:
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("GMAIL_TO")
    if not all([user, password, to]):
        return None
    return user, password, to


def send_email(subject: str, body: str) -> bool:
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    if dry_run:
        log.info("[DRY_RUN] Email: %s\n%s", subject, body)
        return True

    creds = _get_credentials()
    if creds is None:
        log.warning("Email credentials not configured, skipping send")
        return False

    user, password, to = creds
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
        log.info("Email sent: %s", subject)
        return True
    except Exception:
        log.exception("Failed to send email")
        return False


def notify_entry(ticker: str, stock_price: float, btc_price: float, reason: str,
                 stop_loss_pct: float, target_pct: float,
                 strategy_type: str = "trend") -> bool:
    label = "BTC momentum" if strategy_type == "trend" else "BTC oversold dip"
    subject = f"[STOCK-SIGNAL] BUY {ticker} @ ${stock_price:.2f} -- {label}"
    body = (
        f"=== BUY SIGNAL ===\n\n"
        f"Stock: {ticker}\n"
        f"Current Price: ${stock_price:.2f}\n"
        f"BTC Price: ${btc_price:,.0f}\n\n"
        f"Signal: {reason}\n\n"
        f"Suggested Stop Loss: ${stock_price * (1 - stop_loss_pct):.2f} ({-stop_loss_pct*100:.0f}%)\n"
        f"Suggested Target:    ${stock_price * (1 + target_pct):.2f} (+{target_pct*100:.0f}%)\n\n"
        f"Action: Consider buying {ticker} at market open or current price.\n"
        f"Max hold period: 5 business days.\n"
    )
    return send_email(subject, body)


def notify_exit(ticker: str, entry_price: float, current_price: float,
                pnl_pct: float, hold_days: float, reason: str) -> bool:
    direction = "+" if pnl_pct >= 0 else ""
    subject = (
        f"[STOCK-SIGNAL] SELL {ticker} @ ${current_price:.2f} "
        f"-- {reason} ({direction}{pnl_pct*100:.1f}%)"
    )
    body = (
        f"=== SELL SIGNAL ===\n\n"
        f"Stock: {ticker}\n"
        f"Entry Price:   ${entry_price:.2f}\n"
        f"Current Price: ${current_price:.2f}\n"
        f"P&L: {direction}{pnl_pct*100:.1f}%\n"
        f"Hold Duration: {hold_days:.1f} days\n\n"
        f"Reason: {reason}\n\n"
        f"Action: Consider selling {ticker} at current price.\n"
    )
    return send_email(subject, body)


