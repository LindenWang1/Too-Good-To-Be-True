"""The two grids the study sweeps over.

strategy_grid(): every strategy configuration tried (182 in total), exactly the
  outline's "Strategy families and parameter grids" table. Trying many
  configurations is the point: it is how backtest overfitting happens, and the
  statistics (DSR, PBO) measure how much of the best result is luck.

realism_grid(): the 36 cost settings (4 fees x 3 slippage models x 3 latencies).
  Changing one cost at a time lets the analysis measure each cost's effect.
"""
from __future__ import annotations

from itertools import product

from .config import (DONCHIAN, MA_CROSS, RSI_MR, TSMOM, ZSCORE_MR,
                     ExecConfig, StrategyConfig)


def strategy_grid(step: int = 1) -> list[StrategyConfig]:
    """All 182 configurations. step > 1 keeps every step-th one (quick test runs only)."""
    g: list[StrategyConfig] = []
    for lb, rb in product([5, 10, 20, 40, 60, 120, 250], [1, 5, 20]):
        g.append(StrategyConfig(TSMOM, (lb, rb)))
    for fast, slow in product(range(5, 55, 5), range(20, 220, 20)):
        if fast < slow:
            g.append(StrategyConfig(MA_CROSS, (fast, slow)))
    for w, ent, ext in product([10, 20, 40, 80], [1.0, 1.5, 2.0, 2.5], [0.0, 0.5]):
        g.append(StrategyConfig(ZSCORE_MR, (w, ent, ext)))
    for ent, ext in product([10, 20, 55, 100], [5, 10, 20]):
        g.append(StrategyConfig(DONCHIAN, (ent, ext)))
    for per, lo, hi in product([7, 14, 21], [20, 25, 30], [70, 75, 80]):
        g.append(StrategyConfig(RSI_MR, (per, lo, hi)))
    return g[::step]


def realism_grid(half_spread_bps: float, impact_k: float,
                 long_only: bool = False) -> list[tuple[str, ExecConfig]]:
    """fees x slippage model x latency = 4 x 3 x 3 = 36 settings.

    half_spread_bps: the asset's half-spread from the market's spread model (bt/costs.py,
      spread_for_asset), passed in by run_sweep.py.
    impact_k: the square-root impact coefficient (run_sweep.py --impact-k, default 0.5).
    """
    out = []
    # Slippage models: none; half the bid-ask spread; spread plus square-root market impact.
    slip_models = {"none": (0.0, 0.0), "spread": (half_spread_bps, 0.0),
                   "spread+impact": (half_spread_bps, impact_k)}
    for fee, (slip_name, (hs, k)), lat in product([0, 5, 10, 20], slip_models.items(), [0, 1, 2]):
        label = f"fee{fee}_{slip_name}_lat{lat}"      # e.g. "fee10_spread+impact_lat1"
        out.append((label, ExecConfig(fee_bps=fee, half_spread_bps=hs, impact_k=k, latency_bars=lat,
                                      long_only=long_only)))
    return out
