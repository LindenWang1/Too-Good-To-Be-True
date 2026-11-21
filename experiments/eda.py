"""Baseline Analysis (the proposal's 'opportunities for analysis'):

  1. Return distributions: volatility, skew, kurtosis per asset
  2. Volatility clustering: autocorrelation of |returns|
  3. Momentum vs. mean reversion: autocorrelation of returns at several lags
  4. Zero-cost equity curves for one representative config per strategy family

Uses ONLY the in-sample period, so the out-of-sample data stays untouched.

    python experiments/eda.py --market crypto
    python experiments/eda.py --synthetic
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats as st  # noqa: E402

from bt import engine_cpp  # noqa: E402
from bt.config import (DONCHIAN, MA_CROSS, RSI_MR, TSMOM, ZSCORE_MR,  # noqa: E402
                       ExecConfig, StrategyConfig)
from bt.data import market_files, read_bars, synthetic_market, to_arrays  # noqa: E402
from bt.markets import MARKETS  # noqa: E402
from bt.paths import results_dir  # noqa: E402

# Market settings come from bt/markets.py, so the in-sample cut-off here is
# always the same one the sweep uses. "synthetic" is only for dry runs.
SETTINGS = {m: {"ppy": c["ppy"], "oos_start": c["oos_start"], "lags": c["acf_lags"]}
            for m, c in MARKETS.items()}
SETTINGS["synthetic"] = {"ppy": 24 * 365, "oos_start": "2022-01-01", "lags": [1, 2, 6, 24, 168]}
REPRESENTATIVE = [
    StrategyConfig(TSMOM, (120, 5)),
    StrategyConfig(MA_CROSS, (20, 100)),
    StrategyConfig(ZSCORE_MR, (40, 2.0, 0.5)),
    StrategyConfig(DONCHIAN, (55, 20)),
    StrategyConfig(RSI_MR, (14, 30, 70)),
]


def acf(x: np.ndarray, lag: int) -> float:
    x = x - x.mean()
    return float(np.dot(x[:-lag], x[lag:]) / np.dot(x, x))


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["crypto", "etf"], default="crypto")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--min-years", type=float, default=2.0,
                    help="skip assets with less in-sample history (same rule as run_sweep.py)")
    a = ap.parse_args()
    name = "synthetic" if a.synthetic else a.market
    cfg = SETTINGS[name]
    frames = synthetic_market() if a.synthetic else {f.stem: read_bars(f) for f in market_files(a.market)}
    if not frames:
        sys.exit("no data: run data/download.py first, or pass --synthetic")
    out = results_dir() / "eda" / name
    out.mkdir(parents=True, exist_ok=True)
    cut = pd.Timestamp(cfg["oos_start"], tz="UTC")

    rows, curves = [], {}
    for asset, df in frames.items():
        df = df[df.ts < cut].reset_index(drop=True)  # in-sample only
        years_is = len(df) / cfg["ppy"]
        if years_is < a.min_years:                   # e.g. XLC: launched 2018, after the ETF cut-off
            print(f"{asset}: skipped ({years_is:.1f} in-sample years < {a.min_years})")
            continue
        r =np.log(df.close / df.close.shift(1)).dropna().to_numpy()
        row = {"asset": asset, "bars": len(df),
               "ann_vol": r.std() * np.sqrt(cfg["ppy"]),
               "skew": st.skew(r), "excess_kurt": st.kurtosis(r)}
        for L in cfg["lags"]:
            row[f"acf_r_{L}"] = acf(r, L)
        for L in cfg["lags"][:3]:
            row[f"acf_absr_{L}"] = acf(np.abs(r), L)
        rows.append(row)
        bars = to_arrays(df)
        curves[asset] = {s.name: engine_cpp.run_backtest(bars["open"], bars["close"], bars["volume"], s,
                                                         ExecConfig()).equity for s in REPRESENTATIVE}
        curves[asset]["buy_and_hold"] = df.close.to_numpy() / df.close.iloc[0] * 1e6

    if not rows:
        sys.exit(f"no asset has {a.min_years}+ years of in-sample data before {cfg['oos_start']}")
    tab = pd.DataFrame(rows).set_index("asset")
    tab.to_csv(out / "return_stats.csv")
    with pd.option_context("display.width", 200, "display.precision", 3, "display.max_columns", 30):
        print(tab)
    n = len(tab)
    se = 1.96 / np.sqrt(tab.bars.median())
    print(f"\n|ACF| above ~{se:.3f} is statistically distinguishable from zero at 95% (white-noise band).")

    # Figure: return autocorrelation by lag (momentum > 0, mean reversion < 0)
    fig, ax = plt.subplots(figsize=(7, 4))
    lag_cols = [c for c in tab.columns if c.startswith("acf_r_")]
    x = np.arange(len(lag_cols))
    w = 0.8 / n
    for i, (asset, row) in enumerate(tab.iterrows()):
        ax.bar(x + i * w - 0.4 + w / 2, row[lag_cols], width=w, label=asset)
    ax.axhspan(-se, se, color="0.85", zorder=0, label="noise band (95%)")
    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_xticks(x, [c.split("_")[-1] for c in lag_cols])
    ax.set_xlabel("Lag (bars)")
    ax.set_ylabel("Autocorrelation of returns")
    ax.set_title("Momentum (>0) or mean reversion (<0)? In-sample only")
    ax.legend(frameon=False, fontsize=7, ncol=2)
    style(ax)
    fig.tight_layout()
    fig.savefig(out / "return_autocorrelation.png", dpi=150)

    # Figure: zero-cost equity curves for the first asset
    first = next(iter(curves))
    fig, ax = plt.subplots(figsize=(7, 4))
    for k, eq in curves[first].items():
        ax.plot(eq / 1e6, lw=1.6 if k == "buy_and_hold" else 1.0,
                color="0.2" if k == "buy_and_hold" else None, label=k)
    ax.set_yscale("log")
    ax.set_xlabel("Bar")
    ax.set_ylabel("Growth of $1 (log scale)")
    ax.set_title(f"{first}: zero-cost equity curves, one config per family")
    ax.legend(frameon=False, fontsize=7)
    style(ax)
    fig.tight_layout()
    fig.savefig(out / "zero_cost_equity.png", dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
