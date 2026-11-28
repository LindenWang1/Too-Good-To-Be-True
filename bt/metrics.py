"""Performance metrics for one equity curve.

Definitions match compute_metrics() in engine.cpp exactly, so a Python run and a
C++ sweep report the same numbers (tests/test_parity.py checks this).
"""
from __future__ import annotations

import numpy as np


def bar_returns(equity: np.ndarray) -> np.ndarray:
    """Return of each bar: equity[t] / equity[t-1] - 1 (one shorter than equity).
    After ruin equity stays at 0, and those bars count as a return of 0
    (the ruin bar itself is -100%), matching the C++ engine."""
    prev, cur = equity[:-1], equity[1:]
    return np.divide(cur, prev, out=np.ones_like(cur, dtype=float), where=prev > 0) - 1.0


def summarize(equity: np.ndarray, turnover: float, n_trades: int, periods_per_year: float) -> dict:
    """Headline numbers for one backtest.

    sharpe        mean bar return / its std, scaled to a year by sqrt(periods_per_year)
                  (8,760 hourly bars a year for crypto, 252 trading days for ETFs)
    total_return  final equity / starting equity - 1
    max_dd        largest fall from a previous peak, as a fraction (0.3 = -30%)
    ann_turnover  how many times a year the portfolio is traded
    """
    r = bar_returns(equity)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    peak = np.maximum.accumulate(equity)          # running high-water mark
    return {
        "sharpe": float(r.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else 0.0,
        "total_return": float(equity[-1] / equity[0] - 1.0),
        "max_dd": float(np.max(1.0 - equity / peak)),
        "ann_turnover": float(turnover / len(r) * periods_per_year),
        "n_trades": int(n_trades),
        "mean_ret": float(r.mean()),
    }
