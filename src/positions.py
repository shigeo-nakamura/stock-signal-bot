from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from .utils import now_et

log = logging.getLogger(__name__)


def _default_state() -> dict:
    return {
        "positions": {},
        "last_daily_summary": "",
        "last_signal_time": "",
        "signal_cooldown_until": "",
    }


def load_state(path: str) -> dict:
    if os.path.isfile(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            log.exception("Failed to load state file, starting fresh")
    return _default_state()


def save_state(state: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, path)


def open_position(
    state: dict, ticker: str, entry_price: float, btc_price: float
) -> None:
    now = now_et()
    state["positions"][ticker] = {
        "entry_price": entry_price,
        "entry_time": now.isoformat(),
        "signal_btc_price": btc_price,
        "status": "open",
    }
    state["last_signal_time"] = now.isoformat()
    log.info("Opened position: %s @ %.2f (BTC: %.0f)", ticker, entry_price, btc_price)


def close_position(state: dict, ticker: str, reason: str) -> dict | None:
    pos = state["positions"].get(ticker)
    if not pos or pos["status"] != "open":
        return None
    pos["status"] = "closed"
    pos["close_time"] = now_et().isoformat()
    pos["close_reason"] = reason
    log.info("Closed position: %s reason=%s", ticker, reason)
    return pos


def get_open_positions(state: dict) -> dict[str, dict]:
    return {
        ticker: pos
        for ticker, pos in state["positions"].items()
        if pos.get("status") == "open"
    }


def is_in_cooldown(state: dict, config: dict) -> bool:
    cooldown_str = state.get("signal_cooldown_until", "")
    if not cooldown_str:
        return False
    try:
        cooldown_until = datetime.fromisoformat(cooldown_str)
        return now_et() < cooldown_until
    except ValueError:
        return False


def set_cooldown(state: dict, config: dict) -> None:
    from datetime import timedelta

    hours = config["strategy"]["signal_cooldown_hours"]
    state["signal_cooldown_until"] = (now_et() + timedelta(hours=hours)).isoformat()


def position_age_days(pos: dict) -> float:
    entry = datetime.fromisoformat(pos["entry_time"])
    return (now_et() - entry).total_seconds() / 86400


def position_pnl_pct(pos: dict, current_price: float) -> float:
    return (current_price - pos["entry_price"]) / pos["entry_price"]
