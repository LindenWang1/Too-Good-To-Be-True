"""Out-of-sample details behind the funnel. DESCRIPTIVE ONLY: it adds no stage, changes
no threshold and changes no number that oos_analysis.py reports.

    python experiments/oos_details.py                 # every run in results/
    python experiments/oos_details.py --run etf

Added 2026-11-28, after unsealing, because no strategy passed the Deflated Sharpe test
in any run, which leaves the funnel's last stages empty. These numbers show what the
test rejected and whether rejecting it was right:

1. The candidates the Deflated Sharpe test rejected: everything still significant at
   realistic costs. How did they do out of sample? How many beat simply holding the
   same asset? (Real data, and the placebo per copy.)
2. The naive researcher: on each asset, pick the configuration with the best
   in-sample Sharpe. How did that pick do out of sample, vs. buy-and-hold? Also the
   luck benchmark SR0 the Deflated Sharpe test compared it with.
3. Persistence with and without costs: the in-sample vs. out-of-sample slope and
   correlation at headline costs AND with free trading. Costs differ between strategies
   in the same way in both periods, so they can make rankings persist even when skill
   doesn't.

Writes results/<run>/oos_details.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from bt.paths import results_dir  # noqa: E402
from oos_analysis import SIG, oos_buy_and_hold  # noqa: E402


def _r(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 3)


def rejected_candidates(df: pd.DataFrame, zero: str, head: str, bh: dict) -> dict:
    """Pairs significant with no costs AND at headline costs (funnel stage 3), at headline costs."""
    key = ["asset", "config"]
    z = df[df.setting == zero].set_index(key)
    h = df[df.setting == head].set_index(key).reindex(z.index)
    c = h[(z.is_psr0 > SIG) & (h.is_psr0 > SIG)].reset_index()
    if c.empty:
        return {"n": 0}
    c["bh"] = c.asset.str.replace(r"__placebo\d+$", "", regex=True).map(bh).astype(float)
    oos = c.oos_sharpe.astype(float)
    return {"n": len(c), "positive_oos": int((oos > 0).sum()), "beat_buy_and_hold_oos": int((oos > c.bh).sum()),
            "median_is_sharpe": _r(c.is_sharpe.median()), "median_oos_sharpe": _r(oos.median()),
            "families": c.family.value_counts().to_dict()}


def naive_winners(stats: pd.DataFrame, setting: str, bh: dict) -> dict:
    """Each real asset's in-sample winner at `setting`."""
    s = stats[(stats.setting == setting) & ~stats.asset.str.contains("__placebo")].copy()
    s["bh"] = s.asset.map(bh).astype(float)
    return {"assets": len(s),
            "median_is_sharpe": _r(s.best_is_sharpe.median()),
            "median_oos_sharpe": _r(s.best_oos_sharpe.median()),
            "positive_oos": int((s.best_oos_sharpe > 0).sum()),
            "beat_buy_and_hold_oos": int((s.best_oos_sharpe > s.bh).sum()),
            "median_luck_benchmark_sr0": _r(s.sr0_ann.median()),
            "median_effective_trials": _r(s.n_eff.median()),
            "median_dsr_of_winner": _r(s.dsr_best.median())}


def persistence(real: pd.DataFrame, setting: str) -> dict:
    d = real[real.setting == setting]
    slope = float(np.polyfit(d.is_sharpe, d.oos_sharpe, 1)[0])
    return {"slope": _r(slope), "correlation": _r(np.corrcoef(d.is_sharpe, d.oos_sharpe)[0, 1])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", nargs="*", default=["crypto_long_only", "crypto", "etf"])
    a = ap.parse_args()
    for run in a.run:
        rdir = results_dir() / run
        if not (rdir / "SEALED_sweep_oos.csv.gz").exists():
            continue
        info = json.loads((rdir / "run_info.json").read_text())
        zero, head = info["zero_setting"], info["headline_setting"]
        keys = ["asset", "setting", "config"]
        df = pd.read_csv(rdir / "sweep_is.csv.gz").merge(pd.read_csv(rdir / "SEALED_sweep_oos.csv.gz"), on=keys)
        stats = pd.read_csv(rdir / "asset_stats_is.csv").merge(
            pd.read_csv(rdir / "SEALED_asset_stats_oos.csv"), on=["asset", "setting"])
        plc_mask = df.asset.str.contains("__placebo")
        real, plc = df[~plc_mask], df[plc_mask]
        bh = oos_buy_and_hold(info["market"], sorted(real.asset.unique()))
        n_copies = int(plc.asset.str.extract(r"__placebo(\d+)$")[0].nunique()) if len(plc) else 0

        out = {"run": run, "headline_setting": head,
               "buy_and_hold_median_oos_sharpe": _r(np.median(list(bh.values()))) if bh else None,
               "rejected_candidates_real": rejected_candidates(real, zero, head, bh),
               "rejected_candidates_placebo_total": rejected_candidates(plc, zero, head, bh) if n_copies else None,
               "placebo_copies": n_copies,
               "naive_winner_headline": naive_winners(stats, head, bh),
               "naive_winner_free_trading": naive_winners(stats, zero, bh),
               "persistence_headline": persistence(real, head),
               "persistence_free_trading": persistence(real, zero)}
        (rdir / "oos_details.json").write_text(json.dumps(out, indent=2))

        rc, nw, nz = out["rejected_candidates_real"], out["naive_winner_headline"], out["naive_winner_free_trading"]
        print(f"\n=== {run} (headline {head}; buy-and-hold median OOS Sharpe {out['buy_and_hold_median_oos_sharpe']}) ===")
        if rc["n"]:
            print(f"Rejected by the Deflated Sharpe test (significant at realistic costs): {rc['n']}. Out of sample: "
                  f"{rc['positive_oos']} positive, {rc['beat_buy_and_hold_oos']} beat buy-and-hold; median Sharpe "
                  f"{rc['median_is_sharpe']} in-sample -> {rc['median_oos_sharpe']} out of sample. Families: {rc['families']}")
        else:
            print("Rejected by the Deflated Sharpe test: none were significant at realistic costs.")
        pc = out["rejected_candidates_placebo_total"]
        if pc and pc["n"]:
            print(f"  Placebo, same stage (per copy): {pc['n'] / n_copies:.1f} candidates, "
                  f"{pc['positive_oos'] / n_copies:.1f} positive out of sample")
        for name, w in [("headline costs", nw), ("free trading", nz)]:
            print(f"Naive pick (each asset's in-sample winner), {name}: in-sample {w['median_is_sharpe']} -> "
                  f"out of sample {w['median_oos_sharpe']}; {w['positive_oos']} of {w['assets']} positive, "
                  f"{w['beat_buy_and_hold_oos']} beat buy-and-hold; luck benchmark SR0 {w['median_luck_benchmark_sr0']} "
                  f"from {w['median_effective_trials']} effective trials; winner's DSR {w['median_dsr_of_winner']}")
        ph, pz = out["persistence_headline"], out["persistence_free_trading"]
        print(f"Persistence (in-sample -> out-of-sample Sharpe): headline slope {ph['slope']}, corr {ph['correlation']}; "
              f"free trading slope {pz['slope']}, corr {pz['correlation']}")
        print(f"saved {rdir / 'oos_details.json'}")


if __name__ == "__main__":
    main()
