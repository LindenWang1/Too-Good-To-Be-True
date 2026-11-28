"""In-sample tables for the write-up. Reads ONLY the in-sample files (sweep_is.csv.gz).

    python experiments/is_tables.py

For each run in results/ it prints:
  1. H1 by strategy family: median turnover, median in-sample Sharpe when trading is free
     and at the headline cost setting, and the Sharpe lost to costs; plus the rank
     correlation between turnover and Sharpe lost (+1 = the most-traded family loses most).
  2. The moving-average heatmap's best cell versus its neighbours: a winner far above its
     neighbours is an isolated peak (likely luck); a broad plateau is more believable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bt.paths import results_dir  # noqa: E402

R = results_dir()
for run in ["crypto_long_only", "crypto", "etf"]:
    if not (R / run).exists():
        continue
    info = json.loads((R / run / "run_info.json").read_text())
    d = pd.read_csv(R / run / "sweep_is.csv.gz")
    d = d[~d.asset.str.contains("__placebo")]
    free = d[d.setting == info["zero_setting"]].set_index(["asset", "config"])
    head = d[d.setting == info["headline_setting"]].set_index(["asset", "config"])
    t = free[["family", "ann_turnover", "is_sharpe"]].join(head.is_sharpe.rename("sharpe_headline"))
    t["sharpe_lost"] = t.is_sharpe - t.sharpe_headline
    tab = t.groupby("family").agg(turnover=("ann_turnover", "median"), sharpe_free=("is_sharpe", "median"),
                                  sharpe_headline=("sharpe_headline", "median"), sharpe_lost=("sharpe_lost", "median"))
    tab = tab.sort_values("turnover", ascending=False).round(2)
    rho = tab.turnover.rank().corr(tab.sharpe_lost.rank())
    print(f"\n=== {run}: H1, by family (medians over configs x assets; headline = {info['headline_setting']}) ===")
    print(tab.to_string())
    print(f"Rank correlation, turnover vs Sharpe lost: {rho:+.2f}  (+1 = the most-traded family loses the most)")

    ma = head[head.family == "ma_cross"].reset_index().rename(columns={"is_sharpe": "sharpe_headline"})
    p = ma.config.str.extract(r"\((\d+), (\d+)\)").astype(int)
    ma["fast"], ma["slow"] = p[0], p[1]
    g = ma.groupby(["fast", "slow"]).sharpe_headline.median().unstack("slow")
    r, c = np.unravel_index(np.nanargmax(g.values), g.shape)
    nb = [g.values[i, j] for i in range(r - 1, r + 2) for j in range(c - 1, c + 2)
          if (i, j) != (r, c) and 0 <= i < g.shape[0] and 0 <= j < g.shape[1] and not np.isnan(g.values[i, j])]
    best = g.values[r, c]
    print(f"Moving-average heatmap: best cell fast={g.index[r]}, slow={g.columns[c]}, median Sharpe {best:.2f}; "
          f"its {len(nb)} neighbours average {np.mean(nb):.2f} (gap {best - np.mean(nb):.2f}); "
          f"cells within 0.1 of best: {int((g.values >= best - 0.1).sum())} of {int(np.isfinite(g.values).sum())}")
