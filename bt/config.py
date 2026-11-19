"""Shared definitions used by BOTH engines.

The Python reference engine (bt/engine_py.py) and the C++ engine (engine_cpp/)
must implement exactly the semantics documented here. Parity tests enforce it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

# Strategy family ids (must match engine_cpp/src/engine.cpp)
TSMOM, MA_CROSS, ZSCORE_MR, DONCHIAN, RSI_MR = 0, 1, 2, 3, 4
FAMILY_NAMES = {
    TSMOM: "tsmom",
    MA_CROSS: "ma_cross",
    ZSCORE_MR: "zscore_mr",
    DONCHIAN: "donchian",
    RSI_MR: "rsi_mr",
}
N_PARAMS = 4  # every config is padded to 4 numeric params

VOL_WINDOW = 20  # bars of log returns used for the impact model's sigma


@dataclass(frozen=True)
class ExecConfig:
    """Execution realism knobs.

    fee_bps          commission charged on traded notional, per side
    half_spread_bps  paid on every fill (buy above / sell below the open)
    impact_k         square-root impact coefficient:
                     impact = impact_k * sigma * sqrt(|shares traded| / bar volume)
    latency_bars     signal formed at close of bar t is filled at the OPEN of bar t+1+latency
    capital          starting equity (sets order size, which drives impact)
    long_only        map short signals (-1) to flat (0). Binance spot cannot short,
                     so this is the realistic setting for spot crypto.
    """

    fee_bps: float = 0.0
    half_spread_bps: float = 0.0
    impact_k: float = 0.0
    latency_bars: int = 0
    capital: float = 1_000_000.0
    long_only: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


ZERO_COST = ExecConfig()


@dataclass(frozen=True)
class StrategyConfig:
    family: int
    params: tuple  # length <= N_PARAMS

    def padded(self) -> list[float]:
        p = [float(x) for x in self.params]
        return p + [0.0] * (N_PARAMS - len(p))

    @property
    def name(self) -> str:
        return f"{FAMILY_NAMES[self.family]}{tuple(self.params)}"
