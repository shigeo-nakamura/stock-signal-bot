from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from .utils import ET

log = logging.getLogger(__name__)

# NYSE holidays 2026 (manually maintained)
NYSE_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def is_market_open(now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(ET)
    else:
        now = now.astimezone(ET)

    if now.weekday() >= 5:
        return False

    date_str = now.strftime("%Y-%m-%d")
    if date_str in NYSE_HOLIDAYS_2026:
        return False

    current_time = now.time()
    return MARKET_OPEN <= current_time < MARKET_CLOSE


def minutes_to_open(now: datetime | None = None) -> int:
    if now is None:
        now = datetime.now(ET)
    else:
        now = now.astimezone(ET)

    if is_market_open(now):
        return 0

    # Find next market open
    candidate = now
    for _ in range(10):
        if candidate.time() >= MARKET_CLOSE or candidate.date() == now.date():
            candidate = candidate.replace(
                hour=MARKET_OPEN.hour,
                minute=MARKET_OPEN.minute,
                second=0,
                microsecond=0,
            )
            if candidate <= now:
                candidate += timedelta(days=1)

        while candidate.weekday() >= 5 or candidate.strftime("%Y-%m-%d") in NYSE_HOLIDAYS_2026:
            candidate += timedelta(days=1)

        if candidate > now:
            break

    diff = candidate - now
    return max(0, int(diff.total_seconds() / 60))


def get_btc_hourly(period: str = "5d") -> pd.DataFrame | None:
    try:
        df = yf.download("BTC-USD", period=period, interval="1h", progress=False)
        if df.empty:
            log.warning("Empty BTC hourly data")
            return None
        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        log.exception("Failed to fetch BTC hourly data")
        return None


def get_btc_15min(period: str = "2d") -> pd.DataFrame | None:
    try:
        df = yf.download("BTC-USD", period=period, interval="15m", progress=False)
        if df.empty:
            log.warning("Empty BTC 15min data")
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        log.exception("Failed to fetch BTC 15min data")
        return None


def get_stock_price(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if hist.empty:
            log.warning("No price data for %s", ticker)
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        return float(hist["Close"].iloc[-1])
    except Exception:
        log.exception("Failed to fetch price for %s", ticker)
        return None


def get_btc_price() -> float | None:
    try:
        t = yf.Ticker("BTC-USD")
        hist = t.history(period="1d", interval="1m")
        if hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        return float(hist["Close"].iloc[-1])
    except Exception:
        log.exception("Failed to fetch BTC price")
        return None
