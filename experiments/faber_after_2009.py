"""Faber case study, scored 2010-2025 only: a DESCRIPTIVE check written after the
pre-registered run (2026-11-28). It changes no verdict.

The pre-registered period (2008-2025) starts just before the 2008-09 crash, the largest
fall in the sample. This scores the same main rule (monthly, fill day 1, same costs and
spreads) and buy-and-hold from 2010 on, to show how much of the result rests on that one
event.

    python experiments/faber_after_2009.py

Writes results/case_study/faber_2010_2025.csv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]

import case_study as cs  # noqa: E402
from bt.config import MA_CROSS, ExecConfig, StrategyConfig  # noqa: E402
from bt.costs import spread_for_asset  # noqa: E402
from bt.data import market_files, read_bars, to_arrays  # noqa: E402
from bt.markets import MARKETS  # noqa: E402

START = "2010-01-01"


def main():
    files = {f.stem: f for f in market_files("etf")}
    pre = pd.Timestamp(cs.TEST_START, tz="UTC")          # spreads from before 2008, as in the case study
    start = pd.Timestamp(START, tz="UTC")
    end = pd.Timestamp(cs.TEST_END, tz="UTC") + pd.Timedelta(days=1)
    rows = []
    for a in cs.ASSETS:
        if a not in files:
            print(f"{a}: no data file, skipped")
            continue
        daily = read_bars(files[a])
        hs = spread_for_asset(MARKETS["etf"], to_arrays(daily), until=int((daily.ts < pre).sum()),
                              asset=a)["half_spread_bps"]
        ex = ExecConfig(fee_bps=0.0, half_spread_bps=hs, impact_k=0.5, latency_bars=0, long_only=True)
        _, _, _, m, mb = cs.run(cs.to_monthly(daily, 1), StrategyConfig(MA_CROSS, (1, 10)), ex, 12, start, end)
        rows.append(cs.row(a, f"{cs.MAIN}, scored from {START[:4]}", hs, m, mb))
    out = pd.DataFrame(rows)
    print(f"Scored {START[:4]}-2025 (descriptive only; the pre-registered period is 2008-2025).")
    cs.save(out, "faber_2010_2025.csv")
    smaller = int((out.max_dd < out.bh_max_dd).sum())
    print(f"Smaller drawdown than buy-and-hold: {smaller} of {len(out)}; "
          f"higher Sharpe: {int((out.sharpe > out.bh_sharpe).sum())} of {len(out)}")


if __name__ == "__main__":
    main()
