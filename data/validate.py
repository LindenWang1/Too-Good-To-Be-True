"""Data-quality report for every asset in a market. Run after download / snapshot.

    python data/validate.py --market crypto
    python data/validate.py --market etf
    python data/validate.py --synthetic        # dry run without data

Writes results/data_quality_<market>.csv and prints a table. Anything flagged
should be explained (or fixed in make_snapshot.clean) before the full sweep.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bt.data import market_files, read_bars, synthetic_market  # noqa: E402
from bt.paths import results_dir  # noqa: E402


def check(df: pd.DataFrame) -> dict:
    """Run every quality check on one asset's bars; returns one row of the report."""
    ts = df["ts"]
    step = ts.diff().dropna()
    bar = step.median()
    # Daily equity data skips weekends/holidays: only flag gaps > 4 bars there.
    gap_mult = 4.5 if bar >= pd.Timedelta("1D") else 1.5
    r = np.log(df["close"] / df["close"].shift(1)).dropna()
    z = (r - r.mean()) / r.std()
    has_hl = {"high", "low"} <= set(df.columns)
    bad_hl = int(((df["high"] < df[["open", "close"]].max(axis=1) - 1e-9) |
                  (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9)).sum()) if has_hl else 0
    return {
        "rows": len(df),
        "start": ts.iloc[0].date(),
        "end": ts.iloc[-1].date(),
        "bar": str(bar),
        "duplicate_ts": int(ts.duplicated().sum()),
        "gaps": int((step > gap_mult * bar).sum()),
        "largest_gap": str(step.max()),
        "zero_volume_bars": int((df["volume"] <= 0).sum()),
        "nonpositive_prices": int((df[["open", "close"]] <= 0).sum().sum()),
        "ohlc_inconsistent": bad_hl,
        "returns_over_8sd": int((z.abs() > 8).sum()),
        "max_abs_log_return": round(float(r.abs().max()), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["crypto", "etf"], default="crypto")
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()

    if a.synthetic:
        frames, name = synthetic_market(), "synthetic"
    else:
        files = market_files(a.market)
        if not files:
            sys.exit(f"no data for {a.market}: run data/download.py first")
        frames, name = {f.stem: read_bars(f) for f in files}, a.market

    rep = pd.DataFrame({k: check(v) for k, v in frames.items()}).T
    out = results_dir() / f"data_quality_{name}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(out)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(rep)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
