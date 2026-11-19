"""Engineering Target: how much faster is the C++ engine than the Python reference?

Runs the same randomly chosen configurations through both engines on the same
synthetic bars, with all costs switched on, and prints time per backtest.

    python experiments/benchmark.py --bars 5000 --configs 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from bt import engine_cpp, engine_py  # noqa: E402
from bt.config import ExecConfig  # noqa: E402
from bt.grids import strategy_grid  # noqa: E402
from bt.synthetic import make_bars  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=5000)
    ap.add_argument("--configs", type=int, default=20, help="configs timed in Python (slow)")
    a = ap.parse_args()

    b = make_bars(n=a.bars, seed=0)
    grid = strategy_grid()
    rng = np.random.default_rng(0)
    sample = [grid[i] for i in rng.choice(len(grid), size=a.configs, replace=False)]
    ex = ExecConfig(fee_bps=10, half_spread_bps=2, impact_k=0.5, latency_bars=1)

    t0 = time.perf_counter()
    for s in sample:
        engine_py.run_backtest(b["open"], b["close"], b["volume"], s, ex)
    py = (time.perf_counter() - t0) / len(sample)

    t0 = time.perf_counter()
    engine_cpp.sweep(b["open"], b["close"], b["volume"], sample, ex, periods_per_year=8760)
    cpp_same = (time.perf_counter() - t0) / len(sample)

    t0 = time.perf_counter()
    engine_cpp.sweep(b["open"], b["close"], b["volume"], grid, ex, periods_per_year=8760)
    cpp_full = time.perf_counter() - t0

    print(f"bars per backtest:           {a.bars:,}")
    print(f"Python reference:            {py * 1e3:9.1f} ms / backtest")
    print(f"C++ engine:                  {cpp_same * 1e3:9.3f} ms / backtest")
    print(f"speed-up:                    {py / cpp_same:9.0f}x")
    print(f"C++ full grid ({len(grid)} configs): {cpp_full:9.3f} s")


if __name__ == "__main__":
    main()
