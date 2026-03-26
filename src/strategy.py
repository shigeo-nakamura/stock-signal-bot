from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from . import market
from .utils import compute_bollinger, compute_ema, compute_rsi

log = logging.getLogger(__name__)


@dataclass
class Signal:
    # Trend-following (long on momentum)
    entry_trend: bool = False
    # Mean-reversion (long on oversold dip)
    entry_reversal: bool = False
    # Exit signal (BTC trend reversal)
    exit_reversal: bool = False

    btc_price: float = 0.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    rsi: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    reason: str = ""
    strategy_type: str = ""  # "trend" or "reversal"

    @property
    def entry(self) -> bool:
        return self.entry_trend or self.entry_reversal


def analyze_btc(config: dict) -> Signal:
    """Analyze BTC price data and generate trend-following + mean-reversion signals."""
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
    bb_upper, bb_mid, bb_lower = compute_bollinger(
        close_15, strat["bb_period"], strat["bb_std"]
    )

    # Current values
    signal.btc_price = float(close_h.iloc[-1])
    signal.ema_fast = float(ema_f.iloc[-1])
    signal.ema_slow = float(ema_s.iloc[-1])
    signal.rsi = float(rsi.iloc[-1])
    signal.bb_upper = float(bb_upper.iloc[-1])
    signal.bb_lower = float(bb_lower.iloc[-1])

    current_btc_15 = float(close_15.iloc[-1])

    lookback = strat["ema_crossover_lookback"]

    # ============================================================
    # Trend-following entry: BTC momentum -> buy COIN/MSTR
    # ============================================================
    crossover_up = False
    for i in range(-lookback, 0):
        try:
            prev_fast = float(ema_f.iloc[i - 1])
            prev_slow = float(ema_s.iloc[i - 1])
            curr_fast = float(ema_f.iloc[i])
            curr_slow = float(ema_s.iloc[i])
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                crossover_up = True
                break
        except (IndexError, KeyError):
            continue

    ema_bullish = signal.ema_fast > signal.ema_slow
    rsi_trend_ok = strat["rsi_entry_min"] <= signal.rsi <= strat["rsi_entry_max"]
    bb_breakout_up = current_btc_15 > signal.bb_upper

    if (crossover_up or ema_bullish) and rsi_trend_ok and bb_breakout_up:
        signal.entry_trend = True
        signal.strategy_type = "trend"
        signal.reason = (
            f"[TREND] BTC momentum: EMA{strat['ema_fast']}/{strat['ema_slow']} bullish"
            f"{' (crossover)' if crossover_up else ''}, "
            f"RSI={signal.rsi:.1f}, BB upper breakout"
        )
        log.info("Trend entry signal: %s", signal.reason)

    # ============================================================
    # Mean-reversion entry: BTC oversold dip -> buy COIN/MSTR
    # ============================================================
    mr = strat.get("mean_reversion", {})
    if mr.get("enabled", True):
        rsi_oversold = signal.rsi < mr.get("rsi_oversold", 30)
        bb_breakout_down = current_btc_15 < signal.bb_lower

        # Check for RSI divergence: price making lower low but RSI making higher low
        rsi_divergence = False
        div_lookback = mr.get("divergence_lookback", 6)
        if len(rsi) >= div_lookback + 1 and len(close_h) >= div_lookback + 1:
            recent_rsi = rsi.iloc[-div_lookback:]
            recent_price = close_h.iloc[-div_lookback:]
            # Price at new low in window but RSI not at new low
            price_at_low = float(recent_price.iloc[-1]) <= float(recent_price.min()) * 1.001
            rsi_above_low = float(recent_rsi.iloc[-1]) > float(recent_rsi.min()) * 1.02
            if price_at_low and rsi_above_low:
                rsi_divergence = True

        if rsi_oversold and (bb_breakout_down or rsi_divergence):
            signal.entry_reversal = True
            signal.strategy_type = "reversal"
            reasons = []
            reasons.append(f"RSI={signal.rsi:.1f} (oversold)")
            if bb_breakout_down:
                reasons.append("BB lower breakout")
            if rsi_divergence:
                reasons.append("RSI bullish divergence")
            signal.reason = f"[REVERSAL] BTC oversold: {', '.join(reasons)}"
            log.info("Reversal entry signal: %s", signal.reason)

    # ============================================================
    # Exit signal: BTC trend reversal (EMA cross down)
    # ============================================================
    for i in range(-lookback, 0):
        try:
            prev_fast = float(ema_f.iloc[i - 1])
            prev_slow = float(ema_s.iloc[i - 1])
            curr_fast = float(ema_f.iloc[i])
            curr_slow = float(ema_s.iloc[i])
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                signal.exit_reversal = True
                signal.reason = (
                    f"BTC reversal: EMA{strat['ema_fast']} crossed below "
                    f"EMA{strat['ema_slow']}"
                )
                log.info("Exit signal: %s", signal.reason)
                break
        except (IndexError, KeyError):
            continue

    # Suppress entry signal when exit signal fires (contradictory)
    if signal.exit_reversal and signal.entry:
        log.info(
            "Suppressing entry signal (%s) due to concurrent exit signal",
            signal.strategy_type,
        )
        signal.entry_trend = False
        signal.entry_reversal = False
        signal.strategy_type = ""

    return signal
