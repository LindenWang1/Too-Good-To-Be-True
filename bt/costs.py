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

The method was designed for daily bars; on hourly crypto bars it is a rough
guide, which is why each cost setting is also run without a spread.
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
