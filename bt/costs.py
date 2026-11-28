"""Cost inputs estimated from the data itself.

Corwin & Schultz (2012), "A Simple Way to Estimate Bid-Ask Spreads from Daily
High and Low Prices", Journal of Finance. Idea: a bar's high is usually a
trade at the ask and its low a trade at the bid, so the high/low range holds
both volatility and the spread. Volatility grows with the time window and the
spread does not, so comparing one-bar ranges with two-bar ranges separates them.

For bars t and t+1:
    beta  = ln(H_t / L_t)^2 + ln(H_t+1 / L_t+1)^2
    gamma = ln(max(H_t, H_t+1) / min(L_t, L_t+1))^2
    alpha = (sqrt(2 beta) - sqrt(beta)) / (3 - 2 sqrt 2) - sqrt(gamma / (3 - 2 sqrt 2))
    S     = 2 (e^alpha - 1) / (1 + e^alpha)          (negative estimates set to 0)

The method was designed for daily bars. Like every high-low estimator it is
biased upward when volatility is large relative to the true spread (Jahan-Parvar
& Zikes, Federal Reserve FEDS 2019-051): on the study's data it gives 8-17 bps
half-spreads for Binance pairs whose quoted spreads are a small fraction of a
basis point. So the sweep does NOT charge it: each market uses the spread model
set in bt/markets.py (spread_for_asset below), and the Corwin-Schultz value is
saved next to it in costs_used.csv as a cross-check.

Spread models (bt/markets.py, "spread_model"):
    fixed   one half-spread for every asset in the market (crypto: 1 bp)
    tick    half of one price tick at the asset's median in-sample price
            (US ETFs trade with a one-cent spread: 0.005 / price)
    cs      the Corwin-Schultz estimate (kept for comparison)
"""
from __future__ import annotations

import numpy as np

_K = 3.0 - 2.0 * np.sqrt(2.0)


def corwin_schultz(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Spread estimate (as a fraction of price) for each pair of consecutive bars.
    Returns an array one shorter than the input."""
    h, l = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
    hl = np.log(h / l) ** 2
    beta = hl[:-1] + hl[1:]
    gamma = np.log(np.maximum(h[:-1], h[1:]) / np.minimum(l[:-1], l[1:])) ** 2
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return np.maximum(s, 0.0)


def half_spread_bps(high: np.ndarray, low: np.ndarray, until: int | None = None) -> float:
    """Median half-spread in basis points, using only bars before `until`
    (pass the in-sample split so out-of-sample data never sets a cost)."""
    h, l = (high, low) if until is None else (high[:until], low[:until])
    s = corwin_schultz(h, l)
    return float(np.median(s) / 2 * 1e4)


def tick_half_spread_bps(close: np.ndarray, tick: float, until: int | None = None) -> float:
    """Half of one price tick, in bps of the median price before `until`.
    A $0.01 spread on a $100 ETF is 1 bp wide, so its half-spread is 0.5 bps."""
    c = np.asarray(close, dtype=float)
    c = c if until is None else c[:until]
    return float(tick / 2 / np.median(c) * 1e4)


def spread_for_asset(cfg: dict, bars: dict, until: int | None = None) -> dict:
    """The half-spread every script charges for one asset, from the market's spread model.

    cfg    one entry of bt.markets.MARKETS
    bars   arrays from bt.data.to_arrays (close, and high/low when present)
    until  first out-of-sample bar: only data before it sets the cost
    Returns half_spread_bps (charged), spread_source, and cs_half_spread_bps (the
    Corwin-Schultz estimate, a cross-check only; NaN without high/low prices).
    """
    has_hl = "high" in bars and "low" in bars
    cs = half_spread_bps(bars["high"], bars["low"], until) if has_hl else float("nan")
    model = cfg.get("spread_model", "cs")
    if model == "fixed":
        hs, src = float(cfg["fixed_half_spread_bps"]), "fixed market assumption"
    elif model == "tick":
        hs, src = tick_half_spread_bps(bars["close"], cfg["tick_size"], until), "one tick at median in-sample price"
    elif has_hl:
        hs, src = cs, "corwin-schultz (in-sample)"
    else:
        hs, src = float(cfg["default_half_spread_bps"]), "market default (no high/low)"
    return {"half_spread_bps": hs, "spread_source": src, "cs_half_spread_bps": cs}
