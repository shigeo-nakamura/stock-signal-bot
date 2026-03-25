from __future__ import annotations

import os
import yaml


DEFAULT_CONFIG = {
    "strategy": {
        "ema_fast": 12,
        "ema_slow": 50,
        "rsi_period": 14,
        "rsi_entry_min": 40,
        "rsi_entry_max": 70,
        "bb_period": 20,
        "bb_std": 2.0,
        "signal_cooldown_hours": 4,
        "ema_crossover_lookback": 3,
    },
    "stocks": ["COIN", "MSTR"],
    "positions": {
        "target_profit_pct": 0.07,
        "stop_loss_pct": 0.05,
        "max_hold_days": 5,
    },
    "polling": {
        "btc_interval_seconds": 300,
        "pre_market_lookahead_min": 30,
    },
    "logging": {
        "level": "INFO",
    },
    "state": {
        "file": "state/positions.json",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None = None) -> dict:
    config = DEFAULT_CONFIG.copy()

    config_path = path or os.environ.get("CONFIG_PATH", "config/config.yaml")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    return config
