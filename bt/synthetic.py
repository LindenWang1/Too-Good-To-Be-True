"""Synthetic OHLCV bars for tests and the end-to-end demo (no network needed)."""
from __future__ import annotations

import numpy as np


def make_bars(n: int = 5000, seed: int = 0, ann_vol: float = 0.6, periods_per_year: float = 8760,
              ar1: float = 0.0, start_price: float = 100.0):
    """GARCH-like returns with optional AR(1) predictability (ar1 > 0 = momentum).

    Returns dict with open, close, volume (numpy arrays).
    """
    # Returns follow a GARCH(1,1)-style process: today's volatility depends on
    # yesterday's move, so calm and wild periods cluster, as in real markets.
    # Student-t shocks (5 degrees of freedom) give fat tails. ar1 adds a little
    # momentum (each return leans toward the previous one), the "real signal"
    # some synthetic markets carry so the tests can tell signal from noise.
    rng = np.random.default_rng(seed)
    base = ann_vol / np.sqrt(periods_per_year)
    sig = np.empty(n)
    r = np.empty(n)
    s2 = base ** 2
    prev = 0.0
    for i in range(n):
        s2 = 0.10 * base ** 2 + 0.10 * prev ** 2 + 0.80 * s2  # GARCH(1,1); long-run variance = base^2
        sig[i] = np.sqrt(s2)
        r[i] = ar1 * prev + sig[i] * rng.standard_t(5) / np.sqrt(5 / 3)
        prev = r[i]
    gap = rng.normal(0, base * 0.05, n)          # small gap between each open and the previous close
    close = start_price * np.exp(np.cumsum(r))
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1] * np.exp(gap[1:])
    # Volume rises with volatility, as it does in real markets (matters for the impact model).
    volume = rng.lognormal(mean=np.log(5e4), sigma=0.5, size=n) * (sig / base)
    return {"open": open_, "close": close, "volume": volume}
