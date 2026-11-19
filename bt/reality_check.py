"""'Backtest Reality Check': the website's demo tool, as plain functions.

Give it the summary of any backtest (Sharpe, length, how many variants were
tried, turnover...) and it returns:
  * PSR  -- probability the true Sharpe is above 0
  * DSR  -- the same, after accounting for how many variants were tried
  * the Sharpe that luck alone would produce for that many tries
  * break-even fee: the cost per unit of turnover that wipes out the edge

Everything is closed-form, so the website can run the same maths in
JavaScript with no server (site/reality_check.js mirrors this file).
"""
from __future__ import annotations

import numpy as np

from .stats import expected_max_sharpe, psr


def reality_check(sharpe_ann: float, years: float, periods_per_year: float,
                  n_trials: int = 1, ann_vol: float | None = None, ann_turnover: float | None = None,
                  skew: float = 0.0, kurt: float = 3.0, trial_sharpe_sd_ann: float | None = None) -> dict:
    """All Sharpe inputs annualized. `ann_turnover` = traded notional / equity per year
    (both sides counted, as the engine reports it).

    trial_sharpe_sd_ann: spread of the Sharpes across the variants tried. If unknown,
    we assume the variants were pure noise, whose Sharpe estimates have sd ~ 1/sqrt(T)
    per period -- the most charitable assumption, so the real DSR is usually lower.
    """
    T = int(round(years * periods_per_year))                 # number of return observations
    sr = sharpe_ann / np.sqrt(periods_per_year)               # the formulas use per-bar Sharpe
    if trial_sharpe_sd_ann is None:
        var_sr = 1.0 / T
    else:
        var_sr = (trial_sharpe_sd_ann / np.sqrt(periods_per_year)) ** 2
    sr0 = expected_max_sharpe(var_sr, n_trials) if n_trials > 1 else 0.0
    out = {
        "psr": psr(sr, T, skew, kurt, 0.0),
        "dsr": psr(sr, T, skew, kurt, sr0),
        "luck_sharpe_ann": sr0 * np.sqrt(periods_per_year),
        "n_obs": T,
    }
    if ann_vol is not None and ann_turnover:
        # net mean = gross mean - turnover * fee  ->  fee* = Sharpe * vol / turnover
        out["break_even_fee_bps"] = sharpe_ann * ann_vol / ann_turnover * 1e4
    return out
