"""Validation beyond the single split: walk-forward selection and bootstrap ranges.

Run AFTER `make analyze`: it uses out-of-sample data, which is
unsealed by then. It re-runs the 182 configurations at the market's headline
cost setting (a few seconds per asset with the C++ engine).

1. Walk-forward. The main study splits each asset once (in-sample / out-of-sample).
   Here the split moves forward a year at a time: for each test year Y, pick the
   configuration with the best Sharpe on ALL data before Y (expanding window),
   then record how it did in year Y. If the in-sample winner's edge were real,
   it should beat the typical configuration year after year, not just once.

2. Block bootstrap. For each asset's in-sample winner (picked before the official
   out-of-sample start, as in the main study), resample its out-of-sample returns
   in blocks (keeping short-run patterns like volatility clusters) 2,000 times and
   report a 95% range for its annualized Sharpe. A range that straddles zero means
   "we can't tell this strategy from nothing".

Writes, in results/<run>/:
  validation_walkforward.csv   one row per (asset, test year)
  validation_bootstrap.csv     one row per asset
and figures/<run>_walkforward.png.

    python experiments/validation.py --market crypto --long-only
    python experiments/validation.py --market etf
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bt import engine_cpp  # noqa: E402
from bt import plotstyle as ps  # noqa: E402
from bt.costs import spread_for_asset  # noqa: E402
from bt.data import market_files, read_bars, to_arrays  # noqa: E402
from bt.grids import realism_grid, strategy_grid  # noqa: E402
from bt.markets import MARKETS  # noqa: E402
from bt.paths import figures_dir, results_dir  # noqa: E402
from bt.stats import sharpe_per_period  # noqa: E402

# Bootstrap block length in bars: about a week of hours for crypto, a month of days for ETFs.
BLOCK = {"crypto": 168, "etf": 21}


def block_bootstrap_sharpe(r: np.ndarray, block: int, n_boot: int, ppy: float, rng) -> np.ndarray:
    """Annualized Sharpe of n_boot moving-block resamples of the return series r."""
    n = len(r)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n]
    return sharpe_per_period(r[idx]) * np.sqrt(ppy)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", choices=MARKETS, required=True)
    ap.add_argument("--long-only", action="store_true")
    ap.add_argument("--impact-k", type=float, default=0.5)
    ap.add_argument("--min-train-years", type=float, default=2.0)
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args()

    cfg = MARKETS[a.market]
    ppy = cfg["ppy"]
    run = a.market + ("_long_only" if a.long_only else "")
    grid = strategy_grid()
    names = np.array([s.name for s in grid])
    cut = pd.Timestamp(cfg["oos_start"], tz="UTC")
    rng = np.random.default_rng(0)

    wf_rows, bs_rows = [], []
    for path in market_files(a.market):
        asset = path.stem
        df = read_bars(path)
        bars = to_arrays(df)
        split = int((df.ts < cut).sum())
        if split / ppy < a.min_train_years or len(df) - split < 50:
            print(f"{asset}: skipped (too little history)")
            continue
        hs = spread_for_asset(cfg, bars, until=split)["half_spread_bps"]   # same model as the sweep
        ex = dict(realism_grid(hs, a.impact_k, long_only=a.long_only))[cfg["headline"]]
        _, R = engine_cpp.sweep(bars["open"], bars["close"], bars["volume"], grid, ex, ppy,
                                return_series=True)
        ts = df.ts.iloc[1:].reset_index(drop=True)          # R[:, j] is the return INTO bar j + 1

        # 1. Walk-forward: expanding window, one test year at a time.
        first_year = ts.iloc[0].year
        for year in sorted(ts.dt.year.unique()):
            train = (ts < pd.Timestamp(f"{year}-01-01", tz="UTC")).to_numpy()
            test = (ts.dt.year == year).to_numpy()
            if train.sum() / ppy < a.min_train_years or test.sum() < ppy / 4:
                continue
            sr_train = sharpe_per_period(R[:, train])
            sr_test = sharpe_per_period(R[:, test]) * np.sqrt(ppy)
            best = int(np.nanargmax(sr_train))
            wf_rows.append({"asset": asset, "test_year": year, "winner": names[best],
                            "winner_test_sharpe": sr_test[best],
                            "median_config_test_sharpe": float(np.nanmedian(sr_test)),
                            "winner_beats_median": bool(sr_test[best] > np.nanmedian(sr_test)),
                            "winner_positive": bool(sr_test[best] > 0),
                            "official_oos": year >= cut.year, "first_data_year": first_year})

        # 2. Bootstrap the official in-sample winner's out-of-sample Sharpe.
        ins, oos = R[:, : split - 1], R[:, split - 1:]
        best = int(np.nanargmax(sharpe_per_period(ins)))
        boot = block_bootstrap_sharpe(oos[best], BLOCK[a.market], a.n_boot, ppy, rng)
        lo, hi = np.nanpercentile(boot, [2.5, 97.5])
        bs_rows.append({"asset": asset, "winner": names[best],
                        "is_sharpe": float(sharpe_per_period(ins[best]) * np.sqrt(ppy)),
                        "oos_sharpe": float(sharpe_per_period(oos[best]) * np.sqrt(ppy)),
                        "oos_ci_low": lo, "oos_ci_high": hi, "ci_excludes_zero": bool(lo > 0 or hi < 0)})
        print(f"{asset}: walk-forward and bootstrap done")

    if not wf_rows:
        sys.exit("no asset had enough history: run `make data snapshot` first")
    out = results_dir() / run
    out.mkdir(parents=True, exist_ok=True)
    wf, bs = pd.DataFrame(wf_rows), pd.DataFrame(bs_rows)
    wf.to_csv(out / "validation_walkforward.csv", index=False)
    bs.to_csv(out / "validation_bootstrap.csv", index=False)

    # Summary to paste into notes/results.md
    by_year = wf.groupby("test_year").agg(assets=("asset", "size"),
                                          winner_sharpe=("winner_test_sharpe", "median"),
                                          typical_sharpe=("median_config_test_sharpe", "median"),
                                          share_beating_typical=("winner_beats_median", "mean"))
    print(f"\n=== {run}: walk-forward (headline costs: {cfg['headline']}) ===")
    print(by_year.round(2).to_string())
    print(f"In-sample winner beat the typical configuration in "
          f"{wf.winner_beats_median.mean():.0%} of asset-years (luck alone: about 50%).")
    print(f"\n=== {run}: bootstrap 95% range of the winner's out-of-sample Sharpe ===")
    print(bs.round(2).to_string(index=False))
    print(f"Ranges that exclude zero: {int(bs.ci_excludes_zero.sum())} of {len(bs)} assets.")

    # Chart: winner vs typical configuration, by test year.
    fig, ax = ps.figure()
    x = by_year.index.to_numpy()
    ax.axhline(0, color=ps.GRID, lw=1)
    ax.plot(x, by_year.typical_sharpe, "-o", color=ps.QUIET, lw=2, label="Typical configuration (median)")
    ax.plot(x, by_year.winner_sharpe, "-o", color=ps.BLUE, lw=2, label="Winner picked on all earlier years")
    if (x >= cut.year).any():
        ax.axvspan(cut.year - 0.5, x.max() + 0.5, color=ps.GRID, alpha=0.4, lw=0)
        ax.text(cut.year - 0.4, ax.get_ylim()[1], "official out-of-sample", va="top", color=ps.QUIET, fontsize=11)
    ax.set_xticks(x[::2] if len(x) > 10 else x)
    ax.set_xlabel("Test year")
    ax.set_ylabel("Sharpe in the test year (median across assets)")
    ax.set_title(f"Walk-forward: does picking the past winner pay? ({run})", loc="left", color=ps.INK)
    ax.legend(frameon=False)
    ps.save(fig, figures_dir() / f"{run}_walkforward.png")
    print(f"\nsaved {out}/validation_*.csv and figures/{run}_walkforward.png")


if __name__ == "__main__":
    main()
