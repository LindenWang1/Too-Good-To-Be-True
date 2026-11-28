"""Core Part 1 (realism): in-sample charts and numbers. Reads ONLY the in-sample files.

    python experiments/is_charts.py --run crypto_long_only
    python experiments/is_charts.py --run etf

Writes to figures/ (committed to git, used on slides and the website):
  <run>_cost_curves.png      median Sharpe vs fee, one line per family, break-even marked,
                             with buying and holding the same assets as a dashed reference
  <run>_heatmap_ma.png       moving-average crossover: in-sample Sharpe by (fast, slow)
  <run>_turnover.png         how much each family trades (the H1 test)
and to results/<run>/is_summary.json:
  break-even fee per family, the effect of each cost on Sharpe, turnover medians.
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
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

from bt.data import market_files, read_bars  # noqa: E402
from bt.markets import MARKETS  # noqa: E402
from bt.paths import figures_dir, results_dir  # noqa: E402
from bt.plotstyle import FAMILY_COLORS, FAMILY_LABELS, GRID, INK, QUIET, figure, save  # noqa: E402

FEES = [0, 5, 10, 20]


def break_even(fees, sharpes) -> float | None:
    """Fee (bps) where a falling Sharpe line crosses zero, by linear interpolation.
    0.0 if already negative at zero fees; None if still positive at the highest fee."""
    if sharpes[0] <= 0:
        return 0.0
    for (f0, s0), (f1, s1) in zip(zip(fees, sharpes), zip(fees[1:], sharpes[1:])):
        if s1 <= 0:
            return float(f0 + (f1 - f0) * s0 / (s0 - s1))
    return None


def cost_effects(df: pd.DataFrame) -> dict:
    """Average change in annualized Sharpe caused by each cost setting, relative to
    trading for free (fee 0, no slippage, no latency). Each (asset, config) is
    compared with itself, so strategy quality cancels out (like a fixed effect)."""
    zero = df[df.setting == "fee0_none_lat0"].set_index(["asset", "config"]).is_sharpe
    d = df.join(zero.rename("zero"), on=["asset", "config"])
    d["delta"] = d.is_sharpe - d.zero
    X = pd.DataFrame({
        "fee_5": d.fee_bps == 5, "fee_10": d.fee_bps == 10, "fee_20": d.fee_bps == 20,
        "spread": d.setting.str.contains("_spread_lat"), "spread_impact": d.setting.str.contains("spread\\+impact"),
        "latency_1": d.latency_bars == 1, "latency_2": d.latency_bars == 2,
    }).astype(float)
    coef, *_ = np.linalg.lstsq(X.to_numpy(), d.delta.to_numpy(), rcond=None)
    return {k: round(float(v), 4) for k, v in zip(X.columns, coef)}


def buy_and_hold_sharpe(market: str, assets: list[str]) -> float | None:
    """Median annualized in-sample Sharpe of simply holding each asset (no costs).
    The yardstick for the cost curves: a long-only strategy in a rising market can
    show a positive Sharpe just by being invested. Uses in-sample prices only."""
    cfg = MARKETS[market]
    cut = pd.Timestamp(cfg["oos_start"], tz="UTC")
    out = []
    for path in market_files(market):
        if path.stem not in assets:
            continue
        c = read_bars(path)
        r = c[c.ts < cut].close.pct_change().dropna().to_numpy()
        if len(r) > 1 and r.std() > 0:
            out.append(r.mean() / r.std(ddof=1) * np.sqrt(cfg["ppy"]))
    return float(np.median(out)) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="folder under results/, e.g. crypto_long_only")
    a = ap.parse_args()
    rdir = results_dir() / a.run
    info = json.loads((rdir / "run_info.json").read_text())
    df = pd.read_csv(rdir / "sweep_is.csv.gz")
    df = df[~df.asset.str.contains("__placebo")]                 # real assets only
    figs = figures_dir()

    # 1) Cost curves: fee only (no slippage, no latency), median across configs and assets.
    sub = df[df.setting.isin([f"fee{f}_none_lat0" for f in FEES])]
    curve = sub.groupby(["family", "fee_bps"]).is_sharpe.median().unstack(0).reindex(FEES)
    be = {f: break_even(FEES, curve[f].tolist()) for f in curve.columns}
    fig, ax = figure()
    ax.axhline(0, color=QUIET, lw=1)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    bh = buy_and_hold_sharpe(info["market"], sorted(df.asset.unique()))
    if bh is not None:                                               # the "just hold it" yardstick
        ax.axhline(bh, color=QUIET, lw=1.6, ls="--")
        ax.text(FEES[-1], bh, f"Buy and hold: {bh:.2f}", ha="right", va="bottom",   # right end: clear of the
                color=QUIET, fontsize=11)                                       # lines, which start high
    for f in curve.columns:
        ax.plot(FEES, curve[f], color=FAMILY_COLORS[f], lw=2.4, marker="o", ms=8, mec="#F6F5F0", mew=2)
        if be[f] not in (None, 0.0):
            ax.plot([be[f]], [0], marker="v", ms=11, color=FAMILY_COLORS[f], mec=INK, mew=0.8)
    ends = curve.iloc[-1].sort_values()
    ys = list(ends.values)
    span = (max(curve.max().max(), bh or -np.inf) - curve.min().min()) or 1
    for i in range(1, len(ys)):                                  # keep labels from overlapping
        ys[i] = max(ys[i], ys[i - 1] + 0.07 * span)
    for (f, _), y in zip(ends.items(), ys):
        tag = "" if be[f] is None else (" (negative at 0)" if be[f] == 0 else f" (break-even {be[f]:.1f})")
        ax.text(FEES[-1] + 0.6, y, FAMILY_LABELS[f] + tag, va="center", color=INK, fontsize=12)
    ax.set_xlim(-0.5, FEES[-1] + 13)
    ax.set_xticks(FEES)
    ax.set_xlabel("Fee per side (bps)")
    ax.set_ylabel("Median in-sample Sharpe")
    save(fig, figs / f"{a.run}_cost_curves.png")

    # 2) Heatmap: moving-average crossover at the headline setting.
    ma = df[(df.family == "ma_cross") & (df.setting == info["headline_setting"])].copy()
    if len(ma):
        p = ma.config.str.extract(r"\((\d+), (\d+)\)").astype(int)
        ma["fast"], ma["slow"] = p[0], p[1]
        grid = ma.groupby(["fast", "slow"]).is_sharpe.median().unstack("slow")
        fig, ax = figure(9, 6)
        vmax = np.nanmax(np.abs(grid.values)) or 1
        im = ax.imshow(grid.values, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto", origin="lower")
        ax.set_xticks(range(len(grid.columns)), grid.columns)
        ax.set_yticks(range(len(grid.index)), grid.index)
        ax.set_xlabel("Slow window (bars)")
        ax.set_ylabel("Fast window (bars)")
        r, c = np.unravel_index(np.nanargmax(grid.values), grid.shape)
        # Outline the single best cell: the "winner" a naive researcher would report.
        ax.add_patch(Rectangle((c - 0.5, r - 0.5), 1, 1, fill=False, ec=INK, lw=2.5))
        cb = fig.colorbar(im, ax=ax)
        cb.set_label("Median in-sample Sharpe (headline costs)")
        save(fig, figs / f"{a.run}_heatmap_ma.png")

    # 3) Turnover by family (at zero cost, so costs don't change behaviour).
    z = df[df.setting == info["zero_setting"]]
    fams = z.groupby("family").ann_turnover.median().sort_values().index.tolist()
    fig, ax = figure(9, 5)
    bp = ax.boxplot([z[z.family == f].ann_turnover for f in fams], orientation="horizontal", patch_artist=True,
                    widths=0.55, showfliers=False)
    for patch, f in zip(bp["boxes"], fams):
        patch.set_facecolor(FAMILY_COLORS[f])
        patch.set_alpha(0.85)
    for med in bp["medians"]:
        med.set_color(INK)
    ax.set_yticks(range(1, len(fams) + 1), [FAMILY_LABELS[f] for f in fams])
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))     # ticks at 1, 2, 5, 10, 20, 50...
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))   # plain numbers, not 10^0
    ax.xaxis.set_minor_formatter(NullFormatter())                       # no crowded minor labels
    ax.set_xlabel("Turnover per year (times the portfolio is traded, log scale)")
    save(fig, figs / f"{a.run}_turnover.png")

    summary = {"run": a.run, "headline_setting": info["headline_setting"],
               "buy_and_hold_median_is_sharpe": None if bh is None else round(bh, 3),
               "break_even_fee_bps": {f: (None if v is None else round(v, 2)) for f, v in be.items()},
               "median_is_sharpe_by_fee": curve.round(3).to_dict(),
               "sharpe_change_vs_free_trading": cost_effects(df),
               "median_turnover": z.groupby("family").ann_turnover.median().round(1).to_dict()}
    (rdir / "is_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"figures in {figs}")


if __name__ == "__main__":
    main()
