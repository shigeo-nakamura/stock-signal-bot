from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from . import market
from .utils import compute_bollinger, compute_ema, compute_rsi

log = logging.getLogger(__name__)


@dataclass
class Signal:
    entry: bool = False
    exit_reversal: bool = False
    btc_price: float = 0.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    rsi: float = 0.0
    bb_upper: float = 0.0
    reason: str = ""


def analyze_btc(config: dict) -> Signal:
    """Analyze BTC price data and generate entry/exit signals."""
    strat = config["strategy"]

    signal = Signal()

    # Fetch data
    hourly = market.get_btc_hourly()
    if hourly is None or len(hourly) < strat["ema_slow"] + 5:
        log.warning("Insufficient BTC hourly data")
        return signal

    fifteen = market.get_btc_15min()
    if fifteen is None or len(fifteen) < strat["bb_period"] + 5:
        log.warning("Insufficient BTC 15min data")
        return signal

    close_h = hourly["Close"]
    close_15 = fifteen["Close"]

    # Compute indicators on hourly data
    ema_f = compute_ema(close_h, strat["ema_fast"])
    ema_s = compute_ema(close_h, strat["ema_slow"])
    rsi = compute_rsi(close_h, strat["rsi_period"])

    # Compute Bollinger Bands on 15-min data
    bb_upper, _, _ = compute_bollinger(close_15, strat["bb_period"], strat["bb_std"])

    # Current values
    signal.btc_price = float(close_h.iloc[-1])
    signal.ema_fast = float(ema_f.iloc[-1])
    signal.ema_slow = float(ema_s.iloc[-1])
    signal.rsi = float(rsi.iloc[-1])
    signal.bb_upper = float(bb_upper.iloc[-1])

    current_btc_15 = float(close_15.iloc[-1])

    # --- Entry signal ---
    # Check EMA crossover within lookback window
    lookback = strat["ema_crossover_lookback"]
    crossover_detected = False
    for i in range(-lookback, 0):
        try:
            prev_fast = float(ema_f.iloc[i - 1])
            prev_slow = float(ema_s.iloc[i - 1])
            curr_fast = float(ema_f.iloc[i])
            curr_slow = float(ema_s.iloc[i])
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                crossover_detected = True
                break
        except (IndexError, KeyError):
            continue

    # Also accept if EMA fast is currently above slow (sustained trend)
    ema_bullish = signal.ema_fast > signal.ema_slow

    # RSI in range
    rsi_ok = strat["rsi_entry_min"] <= signal.rsi <= strat["rsi_entry_max"]

    # Bollinger breakout on 15-min
    bb_breakout = current_btc_15 > signal.bb_upper

    if (crossover_detected or ema_bullish) and rsi_ok and bb_breakout:
        signal.entry = True
        signal.reason = (
            f"BTC momentum: EMA{strat['ema_fast']}/{strat['ema_slow']} bullish"
            f"{' (crossover)' if crossover_detected else ''}, "
            f"RSI={signal.rsi:.1f}, BB breakout"
        )
        log.info("Entry signal: %s", signal.reason)

    # --- Exit signal (BTC reversal) ---
    # EMA fast crossed below slow within lookback
    for i in range(-lookback, 0):
        try:
            prev_fast = float(ema_f.iloc[i - 1])
            prev_slow = float(ema_s.iloc[i - 1])
            curr_fast = float(ema_f.iloc[i])
            curr_slow = float(ema_s.iloc[i])
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                signal.exit_reversal = True
                signal.reason = (
                    f"BTC reversal: EMA{strat['ema_fast']} crossed below EMA{strat['ema_slow']}"
                )
                log.info("Exit signal: %s", signal.reason)
                break
        except (IndexError, KeyError):
            continue

    return signal
