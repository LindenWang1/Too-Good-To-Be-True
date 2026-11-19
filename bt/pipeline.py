"""Sweep one asset over strategy grid x realism grid; split results in/out of sample."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

from . import engine_cpp
from .config import FAMILY_NAMES, ExecConfig, StrategyConfig
from .stats import (deflated_sharpe, deflated_sharpe_clustered, pbo_cscv, psr_vec,
                    sharpe_per_period)


def _ann(sr_pp, ppy):
    return sr_pp * np.sqrt(ppy)


def sweep_asset(asset: str, bars: dict, split: int, grid: list[StrategyConfig],
                realism: list[tuple[str, ExecConfig]], ppy: float,
                pbo_splits: int = 16, pbo_max_combos: int | None = 1000) -> tuple[pd.DataFrame, dict]:
    """Run every (config, realism) pair on the full series once, then score
    returns[:split] as in-sample and returns[split:] as out-of-sample.

    Positions carry across the split (no restart), as they would in live trading.

    Returns a long DataFrame (one row per config x realism setting) and, per
    setting, asset-level stats: the in-sample winner, its Deflated Sharpe
    (naive and clustered), and PBO.
    """
    n = len(bars["close"])
    if not (50 < split < n - 50):
        raise ValueError(f"{asset}: split index {split} leaves too little in- or out-of-sample data (n={n})")
    rows, asset_stats = [], {}
    for label, ex in realism:
        m, R = engine_cpp.sweep(bars["open"], bars["close"], bars["volume"], grid, ex, ppy, return_series=True)
        ins, oos = R[:, : split - 1], R[:, split - 1:]
        sr_is = sharpe_per_period(ins)
        sr_oos = sharpe_per_period(oos)
        T = ins.shape[1]
        sk = st.skew(ins, axis=1)
        ku = st.kurtosis(ins, axis=1, fisher=False)
        psr0 = psr_vec(sr_is, T, sk, ku, 0.0)

        best = int(np.argmax(sr_is))
        naive = deflated_sharpe(ins[best], sr_is)            # every config counted as a trial
        clus = deflated_sharpe_clustered(ins, best)          # near-duplicates merged
        # A config "passes DSR" if its PSR clears the clustered luck benchmark SR0.
        passes = psr_vec(sr_is, T, sk, ku, clus["sr0"])
        p = pbo_cscv(ins.T, n_splits=pbo_splits, max_combos=pbo_max_combos)
        asset_stats[label] = {
            "asset": asset, "setting": label, "best": grid[best].name,
            "best_is_sharpe": _ann(naive["sr"], ppy),
            "n_trials": naive["n_trials"], "n_eff": clus["n_eff"],
            "sr0_naive_ann": _ann(naive["sr0"], ppy), "sr0_ann": _ann(clus["sr0"], ppy),
            "dsr_best_naive": naive["dsr"], "dsr_best": clus["dsr"], "pbo": p["pbo"],
            "best_oos_sharpe": _ann(sr_oos[best], ppy),
        }
        exd = {k: v for k, v in ex.as_dict().items() if k != "capital"}
        for i, s in enumerate(grid):
            rows.append({
                "asset": asset, "setting": label, "family": FAMILY_NAMES[s.family], "config": s.name,
                **exd,
                "is_sharpe": _ann(sr_is[i], ppy), "oos_sharpe": _ann(sr_oos[i], ppy),
                "is_psr0": psr0[i], "is_dsr": passes[i],
                "ann_turnover": m[i, 3], "n_trades": m[i, 4], "max_dd": m[i, 2],
            })
    return pd.DataFrame(rows), asset_stats
