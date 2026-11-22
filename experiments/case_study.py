"""External case study: Faber's 10-month moving-average rule, tested after publication.

Pre-registered in notes/case_study.md (2026-11-21) BEFORE this script was run.
Nothing here is tuned: the windows, assets, period, costs and pass criteria are
the ones written there.

Faber, "A Quantitative Approach to Tactical Asset Allocation" (working paper 2006,
Journal of Wealth Management 2007): at each month-end, hold the asset if its close
is above its 10-month simple moving average, otherwise hold cash (earning 0% here).

Versions (all long-only, through the C++ engine, ETF headline costs: no fee,
each ETF's own spread estimate, square-root impact):
  monthly, fill day 1   THE pre-registered rule: monthly bars, MA_CROSS(1, 10), filled at
                        the open of the next month's FIRST trading day. Pass/fail uses this.
  monthly, fill day 2   the same signal filled one trading day later (the headline setting's
                        one-bar latency read as one trading day). Robustness line only.
  daily 200-day         the pre-registered daily variant: daily bars, MA_CROSS(1, 200), one
                        day of latency. Reported alongside, never part of pass/fail.

How the fill day works: each month bar's "open" is the open of that month's n-th trading
day and its close is the month's last close. The engine fills a month-end signal at the
next bar's open, i.e. the n-th trading day of the next month (latency 0 on month bars).

--btc adds the optional second case (pre-registered too): BTC daily golden cross,
MA_CROSS(50, 200), Binance 10 bps fee + spread + impact + 1 day latency, scored
2023-01-01 to 2025-12-31.

Writes results/case_study/faber.csv (+ btc_golden_cross.csv) and one chart per asset
in figures/case_study_*.png, and prints the pre-registered criteria with pass/fail.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bt import engine_cpp  # noqa: E402
from bt import plotstyle as ps  # noqa: E402
from bt.config import MA_CROSS, ExecConfig, StrategyConfig  # noqa: E402
from bt.costs import half_spread_bps  # noqa: E402
from bt.data import market_files, read_bars  # noqa: E402
from bt.metrics import summarize  # noqa: E402
from bt.paths import figures_dir, results_dir  # noqa: E402

TEST_START, TEST_END = "2008-01-01", "2025-12-31"
ASSETS = ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD"]
MAIN = "monthly, fill day 1"
BTC_START = "2023-01-01"


def to_period_bars(df: pd.DataFrame, key, fill_day: int = 1) -> pd.DataFrame:
    """Group bars into periods (months, or days for hourly crypto).
    open = open of the period's `fill_day`-th bar; high/low/volume over the period;
    close = last close. Each bar is stamped with the period's last timestamp, so
    `ts < start` still splits cleanly. (groupby works on every pandas version.)"""
    g = df.groupby(key, sort=True)
    return pd.DataFrame({
        "ts": g.ts.last(),
        "open": g.open.agg(lambda s: s.iloc[min(fill_day, len(s)) - 1]),
        "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
        "volume": g.volume.sum(),
    }).reset_index(drop=True)


def to_monthly(df: pd.DataFrame, fill_day: int = 1) -> pd.DataFrame:
    return to_period_bars(df, [df.ts.dt.year, df.ts.dt.month], fill_day)


def to_daily(df: pd.DataFrame) -> pd.DataFrame:
    return to_period_bars(df, df.ts.dt.floor("D"))


def score(eq: np.ndarray, n_trades: int, ppy: float, years: float) -> dict:
    m = summarize(eq, 0.0, n_trades, ppy)
    r = eq[1:] / eq[:-1] - 1.0
    m["ann_return"] = float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)
    m["ann_vol"] = float(r.std(ddof=1) * np.sqrt(ppy))
    return m


def run(df: pd.DataFrame, strat: StrategyConfig, ex: ExecConfig, ppy: float,
        start: pd.Timestamp, end: pd.Timestamp):
    """Backtest on the whole series (earlier data only warms up the averages),
    then score the test period, re-based to 1, against buy-and-hold."""
    res = engine_cpp.run_backtest(df.open.to_numpy(float), df.close.to_numpy(float),
                                  df.volume.to_numpy(float), strat, ex)
    i = int((df.ts < start).sum())
    j = int((df.ts <= end).sum())
    years = (df.ts.iloc[j - 1] - df.ts.iloc[i]).days / 365.25
    eq = res.equity[i:j] / res.equity[i]
    bh = df.close.to_numpy(float)[i:j] / df.close.to_numpy(float)[i]
    n_trades = int(np.sum(np.diff(res.target[i:j]) != 0))   # position changes in the test period
    return df.ts.iloc[i:j], eq, bh, score(eq, n_trades, ppy, years), score(bh, 0, ppy, years)


def row(asset, version, hs, m, mb):
    return {"asset": asset, "version": version, "half_spread_bps": round(hs, 2),
            **{k: m[k] for k in ("ann_return", "ann_vol", "sharpe", "max_dd", "n_trades")},
            **{f"bh_{k}": mb[k] for k in ("ann_return", "ann_vol", "sharpe", "max_dd")}}


def chart(asset, title, lines, path):
    fig, ax = ps.figure()
    for ts, eq, color, label in lines:
        ax.plot(ts, eq, lw=2, color=color, label=label)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_ylabel("Growth of $1 (log scale)")
    ax.set_title(title, loc="left", color=ps.INK)
    ax.legend(frameon=False)
    ps.save(fig, path)


def faber(assets, impact_k):
    start, end = pd.Timestamp(TEST_START, tz="UTC"), pd.Timestamp(TEST_END, tz="UTC") + pd.Timedelta(days=1)
    files = {f.stem: f for f in market_files("etf")}
    rows = []
    for asset in assets:
        if asset not in files:
            print(f"{asset}: no data file, skipped")
            continue
        daily = read_bars(files[asset])
        # Spread from the years BEFORE the test period only, like the main study.
        hs = half_spread_bps(daily.high.to_numpy(float), daily.low.to_numpy(float),
                             until=int((daily.ts < start).sum()))
        versions = {
            MAIN: (to_monthly(daily, 1), StrategyConfig(MA_CROSS, (1, 10)), 12, 0, ps.BLUE),
            "monthly, fill day 2": (to_monthly(daily, 2), StrategyConfig(MA_CROSS, (1, 10)), 12, 0, ps.INK),
            "daily 200-day": (daily, StrategyConfig(MA_CROSS, (1, 200)), 252, 1, ps.ORANGE),
        }
        lines = []
        for name, (df, strat, ppy, lat, color) in versions.items():
            ex = ExecConfig(fee_bps=0.0, half_spread_bps=hs, impact_k=impact_k,
                            latency_bars=lat, long_only=True)
            ts, eq, bh, m, mb = run(df, strat, ex, ppy, start, end)
            rows.append(row(asset, name, hs, m, mb))
            if name != "monthly, fill day 2":            # near-identical to fill day 1 on a chart
                lines.append((ts, eq, color, f"Faber rule, {name}"))
            if name == MAIN:
                lines.append((ts, bh, ps.QUIET, "Buy and hold"))
        chart(asset, f"{asset}: Faber's 10-month rule after publication (2008-2025)", lines,
              figures_dir() / f"case_study_faber_{asset}.png")
    out = pd.DataFrame(rows)
    if out.empty:
        sys.exit("no ETF data: run `make data snapshot` first")
    save(out, "faber.csv")

    # Pre-registered criteria (notes/case_study.md), on the main version only.
    main = out[out.version == MAIN].set_index("asset")
    print("\n=== Pre-registered criteria (main rule: monthly, fill day 1) ===")
    c1 = c2 = None
    if "SPY" in main.index:
        s = main.loc["SPY"]
        c1 = s.max_dd <= 0.5 * s.bh_max_dd
        c2 = s.sharpe >= s.bh_sharpe - 0.1
        print(f"1. SPY drawdown at most half of buy-and-hold's: {s.max_dd:.1%} vs {s.bh_max_dd:.1%} "
              f"(limit {0.5 * s.bh_max_dd:.1%}) -> {'PASS' if c1 else 'FAIL'}")
        print(f"2. SPY Sharpe no more than 0.1 below buy-and-hold's: {s.sharpe:.2f} vs {s.bh_sharpe:.2f} "
              f"-> {'PASS' if c2 else 'FAIL'}")
    smaller = int((main.max_dd < main.bh_max_dd).sum())
    c3 = smaller >= 4 and len(main) == 6
    print(f"3. Smaller drawdown than buy-and-hold on at least 4 of 6 ETFs: {smaller} of {len(main)} "
          f"-> {'PASS' if c3 else 'FAIL'}")
    if c1 is not None:
        verdict = ("Holds up" if c1 and c2 and c3 else
                   "Partly holds up" if c1 and c3 else "Doesn't hold up")
        print(f"Verdict by the pre-registered table: {verdict}. Check it by hand against "
              f"notes/case_study.md before writing it down.")


def btc(impact_k):
    from bt.markets import MARKETS
    files = {f.stem: f for f in market_files("crypto")}
    if "BTCUSDT" not in files:
        print("BTCUSDT: no data file, skipped")
        return
    start = pd.Timestamp(BTC_START, tz="UTC")
    end = pd.Timestamp(TEST_END, tz="UTC") + pd.Timedelta(days=1)
    hourly = read_bars(files["BTCUSDT"])
    # Same spread estimate as the main study: hourly prices, in-sample (before 2023) only.
    hs = half_spread_bps(hourly.high.to_numpy(float), hourly.low.to_numpy(float),
                         until=int((hourly.ts < start).sum()))
    daily = to_daily(hourly)
    fee = 10.0 if MARKETS["crypto"]["headline"].startswith("fee10") else 0.0
    ex = ExecConfig(fee_bps=fee, half_spread_bps=hs, impact_k=impact_k, latency_bars=1, long_only=True)
    ts, eq, bh, m, mb = run(daily, StrategyConfig(MA_CROSS, (50, 200)), ex, 365, start, end)
    out = pd.DataFrame([row("BTCUSDT", "daily golden cross (50/200)", hs, m, mb)])
    save(out, "btc_golden_cross.csv")
    ok_dd, ok_sr = m["max_dd"] <= 0.5 * mb["max_dd"], m["sharpe"] >= mb["sharpe"] - 0.1
    print("\n=== Pre-registered criteria (BTC golden cross) ===")
    print(f"Drawdown at most half of buy-and-hold's: {m['max_dd']:.1%} vs {mb['max_dd']:.1%} "
          f"-> {'PASS' if ok_dd else 'FAIL'}")
    print(f"Sharpe no more than 0.1 below buy-and-hold's: {m['sharpe']:.2f} vs {mb['sharpe']:.2f} "
          f"-> {'PASS' if ok_sr else 'FAIL'}")
    chart("BTCUSDT", "BTC: daily golden cross (50/200), 2023-2025",
          [(ts, eq, ps.BLUE, "Golden cross"), (ts, bh, ps.QUIET, "Buy and hold")],
          figures_dir() / "case_study_btc_golden_cross.png")


def save(df: pd.DataFrame, name: str):
    path = results_dir() / "case_study" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(df.round(3).to_string(index=False))
    print(f"saved {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", nargs="*", default=ASSETS)
    ap.add_argument("--impact-k", type=float, default=0.5)
    ap.add_argument("--btc", action="store_true", help="also run the optional BTC golden-cross case")
    a = ap.parse_args()
    faber(a.assets, a.impact_k)
    if a.btc:
        btc(a.impact_k)


if __name__ == "__main__":
    main()
