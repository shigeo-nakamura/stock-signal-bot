from datetime import datetime
from zoneinfo import ZoneInfo

from src.market import is_market_open, minutes_to_open

ET = ZoneInfo("America/New_York")


def test_market_open_weekday_during_hours():
    # Wednesday 10:00 ET
    dt = datetime(2026, 3, 18, 10, 0, tzinfo=ET)
    assert is_market_open(dt) is True


def test_market_closed_weekend():
    # Saturday
    dt = datetime(2026, 3, 21, 10, 0, tzinfo=ET)
    assert is_market_open(dt) is False


def test_market_closed_before_open():
    # Wednesday 8:00 ET
    dt = datetime(2026, 3, 18, 8, 0, tzinfo=ET)
    assert is_market_open(dt) is False


def test_market_closed_after_close():
    # Wednesday 16:30 ET
    dt = datetime(2026, 3, 18, 16, 30, tzinfo=ET)
    assert is_market_open(dt) is False


def test_minutes_to_open_during_market():
    dt = datetime(2026, 3, 18, 10, 0, tzinfo=ET)
    assert minutes_to_open(dt) == 0


def test_minutes_to_open_before_open():
    dt = datetime(2026, 3, 18, 9, 0, tzinfo=ET)
    assert minutes_to_open(dt) == 30
