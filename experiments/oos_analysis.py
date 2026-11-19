"""Core Part 2 (overfitting): open the sealed out-of-sample results and measure
how much of the in-sample performance survives.

    python experiments/oos_analysis.py --run crypto_long_only
    python experiments/oos_analysis.py --run etf

Run this only AFTER the in-sample analysis (is_charts.py) is finished: it is
the step that unseals the SEALED_* files.

Produces
  figures/<run>_funnel.png        the headline funnel, real vs placebo
  figures/<run>_shrinkage.png     in-sample vs out-of-sample Sharpe, with the fitted slope
  results/<run>/oos_summary.json  every number quoted in the talk
  site/data/<run>.json            funnel counts for every cost setting (website sliders)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bt.paths import figures_dir, results_dir, site_data_dir  # noqa: E402
from bt.plotstyle import BLUE, GRID, INK, ORANGE, QUIET, figure, save  # noqa: E402

SIG = 0.95   # "significant" = probability above 95% that the true Sharpe beats the bar

STAGES = ["Tested", "Significant in-sample, no costs", "Still significant at realistic costs",
          "Passes the Deflated Sharpe test", "Positive out of sample"]


def funnel(df: pd.DataFrame, zero: str, setting: str) -> list[int]:
    """Count (asset, config) pairs left at each stage.

    Each stage is a filter on the previous one:
      1. every pair tested
      2. PSR > 95% with no costs              (what a naive backtest would claim)
      3. PSR > 95% at `setting`               (after realistic costs)
      4. passes the clustered DSR at `setting` (after correcting for the number of tries)
      5. out-of-sample Sharpe > 0 at `setting`
    """
    key = ["asset", "config"]
    z = df[df.setting == zero].set_index(key)
    r = df[df.setting == setting].set_index(key).reindex(z.index)
    s2 = z.is_psr0 > SIG
    s3 = s2 & (r.is_psr0 > SIG)
    s4 = s3 & (r.is_dsr > SIG)
    s5 = s4 & (r.oos_sharpe > 0)
    return [len(z), int(s2.sum()), int(s3.sum()), int(s4.sum()), int(s5.sum())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="folder under results/, e.g. crypto_long_only")
    a = ap.parse_args()
    rdir = results_dir() / a.run
    info = json.loads((rdir / "run_info.json").read_text())
    zero, head = info["zero_setting"], info["headline_setting"]

    # Unseal: join in-sample rows with their out-of-sample results.
    keys = ["asset", "setting", "config"]
    df = pd.read_csv(rdir / "sweep_is.csv.gz").merge(pd.read_csv(rdir / "SEALED_sweep_oos.csv.gz"), on=keys)
    stats = pd.read_csv(rdir / "asset_stats_is.csv").merge(
        pd.read_csv(rdir / "SEALED_asset_stats_oos.csv"), on=["asset", "setting"])
    is_placebo = df.asset.str.contains("__placebo")
    real, plc = df[~is_placebo], df[is_placebo]

    # 1) The headline funnel, real vs placebo, at the headline setting.
    f_real = funnel(real, zero, head)
    f_plc = funnel(plc, zero, head) if len(plc) else None
    fig, ax = figure(11, 5.4)
    y = np.arange(len(STAGES))[::-1]
    h = 0.38 if f_plc else 0.6
    ax.barh(y + (h / 2 if f_plc else 0), f_real, height=h, color=BLUE, label="Real data")
    if f_plc:
        ax.barh(y - h / 2, f_plc, height=h, color=ORANGE, label="Placebo (shuffled, no real signal)")
    for yi, v in zip(y, f_real):
        ax.text(v, yi + (h / 2 if f_plc else 0), f"  {v:,}", va="center", color=INK, fontsize=13)
    if f_plc:
        for yi, v in zip(y, f_plc):
            ax.text(v, yi - h / 2, f"  {v:,}", va="center", color=INK, fontsize=13)
        ax.legend(frameon=False, loc="lower right")
    ax.set_yticks(y, STAGES)
    ax.set_xscale("symlog", linthresh=10)          # keeps both 6,000 and 6 readable
    ax.set_xlabel("Strategy–asset pairs (log scale)")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    save(fig, figures_dir() / f"{a.run}_funnel.png")

    # 2) Shrinkage: how much in-sample Sharpe carries over, at the headline setting.
    hd = real[real.setting == head]
    slope, intercept = np.polyfit(hd.is_sharpe, hd.oos_sharpe, 1)
    corr = float(np.corrcoef(hd.is_sharpe, hd.oos_sharpe)[0, 1])
    fig, ax = figure(8.4, 6.6)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    lo = float(min(hd.is_sharpe.min(), hd.oos_sharpe.min())) - 0.3
    hi = float(max(hd.is_sharpe.max(), hd.oos_sharpe.max())) + 0.3
    ax.plot([lo, hi], [lo, hi], color=QUIET, ls="--", lw=1.4)
    ax.scatter(hd.is_sharpe, hd.oos_sharpe, s=18, color=BLUE, alpha=0.4, edgecolors="none")
    xs = np.linspace(lo, hi, 50)
    ax.plot(xs, slope * xs + intercept, color=ORANGE, lw=2.6)
    ax.text(0.03, 0.95, f"fitted slope {slope:.2f}   (dashed line: out-of-sample = in-sample)",
            transform=ax.transAxes, color=INK, fontsize=12, va="top")
    ax.set_xlabel("In-sample Sharpe (headline costs)")
    ax.set_ylabel("Out-of-sample Sharpe")
    save(fig, figures_dir() / f"{a.run}_shrinkage.png")

    # 3) PBO and the in-sample winners, per cost setting (median across real assets).
    rs = stats[~stats.asset.str.contains("__placebo")]
    by_setting = rs.groupby("setting").agg(pbo=("pbo", "median"), dsr_best=("dsr_best", "median"),
                                           n_eff=("n_eff", "median"),
                                           best_is_sharpe=("best_is_sharpe", "median"),
                                           best_oos_sharpe=("best_oos_sharpe", "median"))

    # 4) Website data: the real-data funnel for EVERY cost setting, so sliders can switch.
    site = {"run": a.run, "stages": STAGES, "headline_setting": head, "settings": []}
    for setting, g in real.groupby("setting"):
        row = g.iloc[0]
        site["settings"].append({"setting": setting, "fee_bps": float(row.fee_bps),
                                 "half_spread_bps": float(row.half_spread_bps),
                                 "impact_k": float(row.impact_k), "latency_bars": int(row.latency_bars),
                                 "funnel": funnel(real, zero, setting)})
    sdir = site_data_dir()
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / f"{a.run}.json").write_text(json.dumps(site, indent=1))

    summary = {"run": a.run, "headline_setting": head, "stages": STAGES,
               "funnel_real": f_real, "funnel_placebo": f_plc,
               "shrinkage_slope": round(float(slope), 3), "is_oos_correlation": round(corr, 3),
               "median_pbo_headline": round(float(by_setting.loc[head, "pbo"]), 3),
               "median_pbo_zero_cost": round(float(by_setting.loc[zero, "pbo"]), 3),
               "by_setting": by_setting.round(3).reset_index().to_dict(orient="records")}
    (rdir / "oos_summary.json").write_text(json.dumps(summary, indent=2))

    # A paste-ready block for notes/results.md
    print(f"## {a.run} (headline setting: {head})\n")
    for s, r_, p_ in zip(STAGES, f_real, f_plc or [None] * 5):
        print(f"- {s}: {r_:,}" + ("" if p_ is None else f"   (placebo: {p_:,})"))
    print(f"- Shrinkage slope: {slope:.2f}; IS-OOS correlation {corr:.2f}")
    print(f"- Median PBO: {summary['median_pbo_headline']} at headline costs, "
          f"{summary['median_pbo_zero_cost']} with no costs")


if __name__ == "__main__":
    main()
