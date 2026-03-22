import json
import tempfile
import os

from src.positions import (
    load_state,
    save_state,
    open_position,
    close_position,
    get_open_positions,
    position_pnl_pct,
)


def test_load_state_missing_file():
    state = load_state("/tmp/nonexistent_state.json")
    assert "positions" in state
    assert state["positions"] == {}


def test_save_and_load_state():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    try:
        state = load_state(path)
        open_position(state, "COIN", 285.50, 95000.0)
        save_state(state, path)

        loaded = load_state(path)
        assert "COIN" in loaded["positions"]
        assert loaded["positions"]["COIN"]["entry_price"] == 285.50
        assert loaded["positions"]["COIN"]["status"] == "open"
    finally:
        os.unlink(path)


def test_close_position():
    state = {"positions": {}, "last_daily_summary": "", "last_signal_time": "", "signal_cooldown_until": ""}
    open_position(state, "MSTR", 400.0, 90000.0)
    assert len(get_open_positions(state)) == 1

    result = close_position(state, "MSTR", "Target reached")
    assert result is not None
    assert result["status"] == "closed"
    assert len(get_open_positions(state)) == 0


def test_position_pnl_pct():
    pos = {"entry_price": 100.0}
    assert abs(position_pnl_pct(pos, 107.0) - 0.07) < 0.001
    assert abs(position_pnl_pct(pos, 95.0) - (-0.05)) < 0.001
