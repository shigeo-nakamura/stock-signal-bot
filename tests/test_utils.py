import pandas as pd

from src.utils import compute_bollinger, compute_ema, compute_rsi


def test_compute_ema():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    ema = compute_ema(s, 3)
    assert len(ema) == len(s)
    # EMA should be close to recent values
    assert ema.iloc[-1] > ema.iloc[0]


def test_compute_rsi():
    # Steadily rising prices -> RSI should be high
    s = pd.Series(range(1, 30), dtype=float)
    rsi = compute_rsi(s, 14)
    assert rsi.iloc[-1] > 80

    # Steadily falling prices -> RSI should be low
    s2 = pd.Series(range(30, 1, -1), dtype=float)
    rsi2 = compute_rsi(s2, 14)
    assert rsi2.iloc[-1] < 20


def test_compute_bollinger():
    s = pd.Series([100.0 + i * 0.5 for i in range(30)])
    upper, mid, lower = compute_bollinger(s, 20, 2.0)
    assert len(upper) == 30
    # Upper > mid > lower
    assert upper.iloc[-1] > mid.iloc[-1] > lower.iloc[-1]
