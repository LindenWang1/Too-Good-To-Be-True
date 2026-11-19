"""The Full Study: strategy grid x realism grid for every asset in a market.

    python experiments/run_sweep.py --market crypto --long-only    # headline: spot crypto can't short
    python experiments/run_sweep.py --market crypto                # long-short comparison
    python experiments/run_sweep.py --market etf
    python experiments/run_sweep.py --market crypto --long-only --placebo 5

What it does, per asset:
  1. Splits the history at the market's out-of-sample start date.
  2. Estimates the asset's half-spread from its own IN-SAMPLE high/low prices
     (Corwin-Schultz, bt/costs.py); falls back to the market default without them.
  3. Runs all 182 configurations x 36 cost settings through the C++ engine.
  4. Optionally repeats on block-shuffled copies (placebo), on fewer settings.

Outputs in results/<market>[_long_only]/:
  sweep_is.csv.gz              in-sample results, one row per (asset, setting, config)
  asset_stats_is.csv           per (asset, setting): winner, DSR, PBO
  SEALED_sweep_oos.csv.gz      out-of-sample results -- do not open before the
  SEALED_asset_stats_oos.csv     in-sample analysis is finished
  costs_used.csv               the spread and impact used for each asset, and why
  run_info.json                arguments, settings, git commit, time: how to reproduce this run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bt.costs import half_spread_bps  # noqa: E402
from bt.data import market_files, read_bars, to_arrays  # noqa: E402
from bt.grids import realism_grid, strategy_grid  # noqa: E402
from bt.markets import MARKETS, ZERO_SETTING  # noqa: E402
from bt.paths import results_dir  # noqa: E402
from bt.pipeline import sweep_asset  # noqa: E402
from bt.stats import block_shuffle_bars  # noqa: E402



def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", choices=MARKETS, required=True)
    ap.add_argument("--long-only", action="store_true", help="no shorting (realistic for Binance spot)")
    ap.add_argument("--impact-k", type=float, default=0.5, help="square-root impact coefficient")
    ap.add_argument("--placebo", type=int, default=0, help="shuffled copies per asset")
    ap.add_argument("--min-years", type=float, default=2.0, help="skip assets with less in-sample history")
    ap.add_argument("--assets", nargs="*", help="only these assets (file names without extension)")
    ap.add_argument("--grid-step", type=int, default=1, help="keep every n-th configuration (quick tests only)")
    a = ap.parse_args()

    cfg = MARKETS[a.market]
    grid = strategy_grid(a.grid_step)
    out = results_dir() / (a.market + ("_long_only" if a.long_only else ""))
    out.mkdir(parents=True, exist_ok=True)
    cut = pd.Timestamp(cfg["oos_start"], tz="UTC")

    files = market_files(a.market)
    if a.assets:
        files = [f for f in files if f.stem in set(a.assets)]
    if not files:
        sys.exit("no data: run `make data snapshot` first")

    frames, stats, costs = [], [], []
    t_all = time.perf_counter()
    for path in files:
        asset = path.stem
        df = read_bars(path)
        bars = to_arrays(df)
        split = int((df.ts < cut).sum())                       # ts is sorted
        years_is = split / cfg["ppy"]
        years_oos = (len(df) - split) / cfg["ppy"]
        if years_is < a.min_years or years_oos < 0.25:
            why = f"{years_is:.1f} in-sample / {years_oos:.1f} out-of-sample years"
            print(f"{asset}: skipped ({why})")
            costs.append({"asset": asset, "status": f"skipped: {why}"})
            continue
        if "high" in bars and "low" in bars:
            hs, src = half_spread_bps(bars["high"], bars["low"], until=split), "corwin-schultz (in-sample)"
        else:
            hs, src = cfg["default_half_spread_bps"], "market default (no high/low)"
        costs.append({"asset": asset, "status": "ok", "half_spread_bps": round(hs, 3), "source": src,
                      "impact_k": a.impact_k, "in_sample_years": round(years_is, 2)})
        realism = realism_grid(hs, a.impact_k, long_only=a.long_only)

        t0 = time.perf_counter()
        res, st_ = sweep_asset(asset, bars, split, grid, realism, cfg["ppy"])
        frames.append(res)
        stats += list(st_.values())

        # Placebo: same grid on shuffled copies, but only the two settings the funnel uses.
        placebo_realism = [r for r in realism if r[0] in (ZERO_SETTING, cfg["headline"])]
        for k in range(a.placebo):
            o, c, v = block_shuffle_bars(bars["open"], bars["close"], bars["volume"],
                                         block=cfg["shuffle_block"], rng=np.random.default_rng(k),
                                         split=split)
            pres, pst = sweep_asset(f"{asset}__placebo{k}", {"open": o, "close": c, "volume": v},
                                    split, grid, placebo_realism, cfg["ppy"])
            frames.append(pres)
            stats += list(pst.values())
        print(f"{asset}: {len(bars['close']):,} bars, half-spread {hs:.2f} bps, "
              f"{len(res):,} backtests + {a.placebo} placebo copies, {time.perf_counter() - t0:.1f}s")

    if not frames:
        sys.exit("every asset was skipped")

    # Seal the out-of-sample results in their own files.
    sweep = pd.concat(frames)
    st_df = pd.DataFrame(stats)
    keys = ["asset", "setting", "config"]
    oos_cols = [c for c in sweep.columns if c.startswith("oos_")]
    sweep.drop(columns=oos_cols).to_csv(out / "sweep_is.csv.gz", index=False)
    sweep[keys + oos_cols].to_csv(out / "SEALED_sweep_oos.csv.gz", index=False)
    st_oos = [c for c in st_df.columns if "oos" in c]
    st_df.drop(columns=st_oos).to_csv(out / "asset_stats_is.csv", index=False)
    st_df[["asset", "setting"] + st_oos].to_csv(out / "SEALED_asset_stats_oos.csv", index=False)
    pd.DataFrame(costs).to_csv(out / "costs_used.csv", index=False)
    info = {"market": a.market, "long_only": a.long_only, "impact_k": a.impact_k, "placebo": a.placebo,
            "min_years": a.min_years, "oos_start": cfg["oos_start"], "ppy": cfg["ppy"],
            "headline_setting": cfg["headline"], "zero_setting": ZERO_SETTING,
            "n_configs": len(grid), "grid_step": a.grid_step, "assets": sorted(sweep.asset.unique().tolist()),
            "git_commit": git_commit(), "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
            "runtime_s": round(time.perf_counter() - t_all, 1)}
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    print(f"saved to {out}  (out-of-sample results sealed in SEALED_* files)")


if __name__ == "__main__":
    main()
