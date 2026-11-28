"""Per-market settings, in ONE place so every script agrees.

Change a market's out-of-sample start date here and the baseline analysis
(eda.py), the sweep (run_sweep.py) and everything after them follow.

ppy                      bars per year: 8,760 hours (crypto trades 24/7) or 252 trading days
oos_start                first out-of-sample date. Everything before it is in-sample.
                         Fixed before any results were seen -- don't move it after.
shuffle_block            bars per block in the shuffled-data placebo (1 day of hours / 1 week of days)
spread_model             how each asset's half-spread is set (bt/costs.py, spread_for_asset):
                         crypto "fixed": 1 bp for every pair. Quoted Binance spreads for these
                           pairs are about 0.01-1 bp (BTC and ETH far below 1), so 1 bp is
                           generous; the fee grid (0-20 bps) covers anything wider.
                         etf "tick": half of one cent at the ETF's median in-sample price
                           (these ETFs trade with a one-cent spread). Yahoo's prices are adjusted
                           backwards for splits and dividends, so they sit below the prices that
                           actually traded. Splits are undone with split_factors; the dividend
                           adjustment is left in, so the spread leans slightly high.
                         Corwin-Schultz is no longer charged: it is biased upward on volatile
                         data (8-17 bps on Binance pairs). It is saved in costs_used.csv as a
                         cross-check. Decided 2026-11-27, before any results were opened.
fixed_half_spread_bps    the "fixed" model's value
tick_size                the "tick" model's price tick
split_factors            share splits AFTER the in-sample period, which Yahoo divides into every
                         earlier price: XLB, XLE, XLK, XLU and XLY split 2-for-1 on 2025-12-05
                         (State Street notice to authorized participants, 2025-11-21). The tick
                         model multiplies their prices back by 2 before computing the spread.
default_half_spread_bps  fallback spread for the "cs" model if a file has no high/low prices
headline                 the realistic cost setting quoted in the talk:
                         crypto = Binance regular-tier fee (10 bps per side);
                         ETFs   = zero commission (typical at major US brokers),
                         both with spread + impact and one bar of latency
acf_lags                 lags (in bars) for the autocorrelation charts in eda.py
"""
from __future__ import annotations

MARKETS = {
    "crypto": {"ppy": 24 * 365, "oos_start": "2023-01-01", "shuffle_block": 24,
               "spread_model": "fixed", "fixed_half_spread_bps": 1.0,
               "default_half_spread_bps": 1.0, "headline": "fee10_spread+impact_lat1",
               "acf_lags": [1, 2, 6, 24, 168]},
    "etf": {"ppy": 252, "oos_start": "2018-01-01", "shuffle_block": 5,
            "spread_model": "tick", "tick_size": 0.01,
            "split_factors": {"XLB": 2, "XLE": 2, "XLK": 2, "XLU": 2, "XLY": 2},
            "default_half_spread_bps": 1.0, "headline": "fee0_spread+impact_lat1",
            "acf_lags": [1, 2, 5, 21, 63]},
}

# The "trading for free" setting every comparison starts from.
ZERO_SETTING = "fee0_none_lat0"
