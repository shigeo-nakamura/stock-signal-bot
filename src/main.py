#!/usr/bin/env python3
"""Stock Signal Bot - BTC momentum -> COIN/MSTR entry/exit alerts via email."""

import logging
import signal
import sys
import time

from . import market, positions, strategy
from .config import load_config
from .notifier import notify_daily_summary, notify_entry, notify_exit
from .positions import (
    close_position,
    get_open_positions,
    is_in_cooldown,
    load_state,
    open_position,
    position_age_days,
    position_pnl_pct,
    save_state,
    set_cooldown,
)
from .utils import now_et, setup_logging

log = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    log.info("Received signal %d, shutting down gracefully...", signum)
    _shutdown = True


def handle_entry_signal(sig: strategy.Signal, config: dict, state: dict) -> None:
    pos_config = config["positions"]

    for ticker in config["stocks"]:
        open_pos = get_open_positions(state)
        if ticker in open_pos:
            log.debug("Already holding %s, skipping entry", ticker)
            continue

        stock_price = market.get_stock_price(ticker)
        if stock_price is None:
            log.warning("Could not get price for %s, skipping", ticker)
            continue

        notify_entry(
            ticker=ticker,
            stock_price=stock_price,
            btc_price=sig.btc_price,
            reason=sig.reason,
            stop_loss_pct=pos_config["stop_loss_pct"],
            target_pct=pos_config["target_profit_pct"],
        )

        open_position(state, ticker, stock_price, sig.btc_price)

    set_cooldown(state, config)


def manage_positions(sig: strategy.Signal, config: dict, state: dict) -> None:
    pos_config = config["positions"]
    open_pos = get_open_positions(state)

    for ticker, pos in open_pos.items():
        current_price = market.get_stock_price(ticker)
        if current_price is None:
            log.warning("Could not get price for %s, skipping position check", ticker)
            continue

        pnl = position_pnl_pct(pos, current_price)
        age = position_age_days(pos)

        # Check exit conditions
        reason = None
        if pnl >= pos_config["target_profit_pct"]:
            reason = f"Target reached (+{pnl*100:.1f}%)"
        elif pnl <= -pos_config["stop_loss_pct"]:
            reason = f"Stop loss ({pnl*100:.1f}%)"
        elif age > pos_config["max_hold_days"]:
            reason = f"Max hold period exceeded ({age:.1f} days)"
        elif sig.exit_reversal:
            reason = f"BTC reversal ({sig.reason})"

        if reason:
            notify_exit(
                ticker=ticker,
                entry_price=pos["entry_price"],
                current_price=current_price,
                pnl_pct=pnl,
                hold_days=age,
                reason=reason,
            )
            close_position(state, ticker, reason)


def maybe_send_daily_summary(config: dict, state: dict) -> None:
    now = now_et()
    today = now.strftime("%Y-%m-%d")

    if state.get("last_daily_summary") == today:
        return

    summary_time_str = config["notifications"]["daily_summary_time"]
    hour, minute = map(int, summary_time_str.split(":"))

    if now.hour < hour or (now.hour == hour and now.minute < minute):
        return

    if not market.is_market_open():
        # Only send on trading days, check if market was open today
        # If it's after close on a weekday, still send
        if now.weekday() >= 5:
            return

    open_pos = get_open_positions(state)
    btc_price = market.get_btc_price()

    stock_prices = {}
    for ticker in open_pos:
        stock_prices[ticker] = market.get_stock_price(ticker)

    notify_daily_summary(open_pos, btc_price, stock_prices)
    state["last_daily_summary"] = today


def run() -> None:
    config = load_config()
    setup_logging(config)

    log.info("Stock Signal Bot starting...")
    log.info("Monitoring stocks: %s", config["stocks"])
    log.info(
        "Target: +%.0f%%, Stop: -%.0f%%, Max hold: %d days",
        config["positions"]["target_profit_pct"] * 100,
        config["positions"]["stop_loss_pct"] * 100,
        config["positions"]["max_hold_days"],
    )

    state_path = config["state"]["file"]
    state = load_state(state_path)
    log.info("Loaded state: %d open positions", len(get_open_positions(state)))

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    interval = config["polling"]["btc_interval_seconds"]
    lookahead = config["polling"]["pre_market_lookahead_min"]

    while not _shutdown:
        try:
            now = now_et()

            # Phase A: BTC analysis (always)
            sig = strategy.analyze_btc(config)

            # Phase B: Stock actions (market hours or near-open only)
            market_open = market.is_market_open(now)
            near_open = market.minutes_to_open(now) <= lookahead

            if market_open or near_open:
                # Entry signals
                if sig.entry and not is_in_cooldown(state, config):
                    handle_entry_signal(sig, config, state)

                # Manage existing positions (only during market hours)
                if market_open:
                    manage_positions(sig, config, state)

            # Daily summary
            maybe_send_daily_summary(config, state)

            # Save state
            save_state(state, state_path)

        except Exception:
            log.exception("Error in main loop")

        # Sleep with shutdown check
        for _ in range(interval):
            if _shutdown:
                break
            time.sleep(1)

    log.info("Shutting down, saving state...")
    save_state(state, state_path)
    log.info("Goodbye.")


if __name__ == "__main__":
    run()
