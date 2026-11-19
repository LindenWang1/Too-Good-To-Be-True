"""Per-market settings, in ONE place so every script agrees.

Change a market's out-of-sample start date here and the baseline analysis
(eda.py), the sweep (run_sweep.py) and everything after them follow.

ppy                      bars per year: 8,760 hours (crypto trades 24/7) or 252 trading days
oos_start                first out-of-sample date. Everything before it is in-sample.
                         Fixed before any results were seen -- don't move it after.
shuffle_block            bars per block in the shuffled-data placebo (1 day of hours / 1 week of days)
default_half_spread_bps  fallback spread if a file has no high/low prices
headline                 the realistic cost setting quoted in the talk:
                         crypto = Binance regular-tier fee (10 bps per side);
                         ETFs   = zero commission (typical at major US brokers),
                         both with spread + impact and one bar of latency
acf_lags                 lags (in bars) for the autocorrelation charts in eda.py
"""
from __future__ import annotations

MARKETS = {
    "crypto": {"ppy": 24 * 365, "oos_start": "2023-01-01", "shuffle_block": 24,
               "default_half_spread_bps": 1.0, "headline": "fee10_spread+impact_lat1",
               "acf_lags": [1, 2, 6, 24, 168]},
    "etf": {"ppy": 252, "oos_start": "2018-01-01", "shuffle_block": 5,
            "default_half_spread_bps": 1.0, "headline": "fee0_spread+impact_lat1",
            "acf_lags": [1, 2, 5, 21, 63]},
}

# The "trading for free" setting every comparison starts from.
ZERO_SETTING = "fee0_none_lat0"
