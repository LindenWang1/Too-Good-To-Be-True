"""End-to-end dry run of the whole study on SYNTHETIC data (no downloads needed).

Purpose: prove the pipeline works before real data arrives, and show what the
final charts will look like. The numbers here describe fake markets and must
NOT be quoted as findings.

    python experiments/demo_synthetic.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bt.config import ExecConfig  # noqa: E402
from bt.paths import results_dir  # noqa: E402
from bt.grids import strategy_grid  # noqa: E402
from bt.pipeline import sweep_asset  # noqa: E402
from bt.stats import block_shuffle_bars  # noqa: E402
from bt.synthetic import make_bars  # noqa: E402

PPY = 8760                      # hourly bars
N_BARS = 3 * 8760               # 3 "years": 2 in-sample, 1 out-of-sample
SPLIT = 2 * 8760
OUT = results_dir() / "demo"

# Four fake markets: two pure noise, two with a weak momentum effect.
MARKETS = {"NOISE_A": 0.0, "NOISE_B": 0.0, "MOM_WEAK": 0.02, "MOM_STRONGER": 0.04}

ZERO = ("zero", ExecConfig())
REAL = ("realistic", ExecConfig(fee_bps=10, half_spread_bps=2, impact_k=0.5, latency_bars=1))
FEE_CURVE = [(f"fee{f}", ExecConfig(fee_bps=f)) for f in (0, 2, 5, 10, 20)]


def funnel(df: pd.DataFrame) -> pd.Series:
    z = df[df.setting == "zero"].set_index(["asset", "config"])
    r = df[df.setting == "realistic"].set_index(["asset", "config"])
    naive = z.is_psr0 > 0.95
    costs = naive & (r.is_psr0 > 0.95)
    dsr = costs & (r.is_dsr > 0.95)
    oos = dsr & (r.oos_sharpe > 0)
    return pd.Series({"tested": len(z), "significant in-sample (no costs)": naive.sum(),
                      "still significant after costs": costs.sum(),
                      "passes Deflated Sharpe": dsr.sum(),
                      "positive out-of-sample": oos.sum()})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    grid = strategy_grid()
    t0 = time.perf_counter()
    frames, stats, placebo = [], [], []
    for i, (name, ar1) in enumerate(MARKETS.items()):
        bars = make_bars(n=N_BARS, seed=100 + i, ar1=ar1)
        df, st_ = sweep_asset(name, bars, SPLIT, grid, [ZERO, REAL] + FEE_CURVE, PPY)
        frames.append(df)
        stats += list(st_.values())
        o, c, v = block_shuffle_bars(bars["open"], bars["close"], bars["volume"], block=24,
                                     rng=np.random.default_rng(i), split=SPLIT)
        pdf, _ = sweep_asset(name + "_placebo", {"open": o, "close": c, "volume": v}, SPLIT, grid,
                             [ZERO, REAL], PPY)
        placebo.append(pdf)
    elapsed = time.perf_counter() - t0
    df, pl = pd.concat(frames), pd.concat(placebo)
    st_df = pd.DataFrame(stats)
    df.to_csv(OUT / "sweep.csv", index=False)
    st_df.to_csv(OUT / "asset_stats.csv", index=False)

    n_bt = len(df) + len(pl)
    print(f"{n_bt:,} backtests of {N_BARS:,} bars in {elapsed:.1f}s\n")

    f_real, f_plc = funnel(df), funnel(pl)
    fun = pd.DataFrame({"real (synthetic) markets": f_real, "placebo (shuffled)": f_plc})
    fun.to_csv(OUT / "funnel.csv")
    print("FUNNEL (strategy x market pairs)\n", fun.to_string(), "\n")
    print("PER-MARKET (realistic costs)\n",
          st_df[st_df.setting == "realistic"][["asset", "best", "best_is_sharpe", "sr0_ann",
                                               "dsr_best", "pbo", "best_oos_sharpe"]]
          .round(3).to_string(index=False), "\n")

    # --- Figure 1: cost-sensitivity curves -------------------------------
    fees = [0, 2, 5, 10, 20]
    curve = (df[df.setting.str.startswith("fee")]
             .assign(fee=lambda d: d.fee_bps)
             .groupby(["family", "fee"]).is_sharpe.median().unstack(0))
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for fam in curve.columns:
        ax.plot(curve.index, curve[fam], marker="o", label=fam)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.set_xticks(fees)
    ax.set_xlabel("Fee per side (bps)")
    ax.set_ylabel("Median in-sample Sharpe (annualized)")
    ax.set_title("Synthetic demo: high-turnover families lose the most to fees")
    ax.legend(frameon=False, fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "cost_sensitivity.png", dpi=150)

    # --- Figure 2: in-sample vs out-of-sample Sharpe ---------------------
    r = df[df.setting == "realistic"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.scatter(r.is_sharpe, r.oos_sharpe, s=6, alpha=0.35)
    lim = [min(r.is_sharpe.min(), r.oos_sharpe.min()), max(r.is_sharpe.max(), r.oos_sharpe.max())]
    ax.plot(lim, lim, color="0.5", lw=0.8, ls="--", label="OOS = IS")
    b = np.polyfit(r.is_sharpe, r.oos_sharpe, 1)
    xs = np.linspace(*lim, 50)
    ax.plot(xs, np.polyval(b, xs), color="C3", lw=1.5, label=f"fit: slope {b[0]:.2f}")
    ax.set_xlabel("In-sample Sharpe (net of costs)")
    ax.set_ylabel("Out-of-sample Sharpe (net of costs)")
    ax.set_title("Synthetic demo: in-sample Sharpe shrinks out of sample")
    ax.legend(frameon=False, fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "is_vs_oos.png", dpi=150)
    print(f"wrote {OUT}/sweep.csv, funnel.csv, asset_stats.csv, cost_sensitivity.png, is_vs_oos.png")


if __name__ == "__main__":
    main()
