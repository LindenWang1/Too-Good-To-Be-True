"""The C++ engine must reproduce the Python reference engine exactly."""
import numpy as np
import pytest

from bt import engine_cpp, engine_py
from bt.config import ExecConfig, StrategyConfig, TSMOM, MA_CROSS, ZSCORE_MR, DONCHIAN, RSI_MR
from bt.metrics import bar_returns, summarize
from bt.synthetic import make_bars

BARS = make_bars(n=1500, seed=7)
CONFIGS = [
    StrategyConfig(TSMOM, (20, 5)),
    StrategyConfig(TSMOM, (5, 1)),
    StrategyConfig(MA_CROSS, (10, 60)),
    StrategyConfig(ZSCORE_MR, (20, 1.5, 0.5)),
    StrategyConfig(ZSCORE_MR, (40, 2.0, 0.0)),
    StrategyConfig(DONCHIAN, (20, 10)),
    StrategyConfig(RSI_MR, (14, 30, 70)),
]
EXECS = [
    ExecConfig(),
    ExecConfig(fee_bps=10, half_spread_bps=2, impact_k=0.5, latency_bars=0),
    ExecConfig(fee_bps=5, half_spread_bps=1, impact_k=1.0, latency_bars=2),
    ExecConfig(fee_bps=10, half_spread_bps=1, impact_k=0.5, latency_bars=1, long_only=True),
]


@pytest.mark.parametrize("strat", CONFIGS, ids=lambda s: s.name)
@pytest.mark.parametrize("ex", EXECS, ids=["zero", "costs", "costs+latency", "long_only"])
def test_engines_match(strat, ex):
    a = engine_py.run_backtest(BARS["open"], BARS["close"], BARS["volume"], strat, ex)
    b = engine_cpp.run_backtest(BARS["open"], BARS["close"], BARS["volume"], strat, ex)
    np.testing.assert_array_equal(a.target, b.target)
    np.testing.assert_allclose(a.equity, b.equity, rtol=1e-9, atol=0)
    assert a.n_trades == b.n_trades
    assert a.turnover == pytest.approx(b.turnover, rel=1e-9)
    assert a.n_trades > 0


def test_sweep_matches_single_runs():
    ex = EXECS[1]
    metrics, rets = engine_cpp.sweep(BARS["open"], BARS["close"], BARS["volume"], CONFIGS, ex,
                                     periods_per_year=8760, return_series=True)
    for i, s in enumerate(CONFIGS):
        r = engine_py.run_backtest(BARS["open"], BARS["close"], BARS["volume"], s, ex)
        m = summarize(r.equity, r.turnover, r.n_trades, 8760)
        for j, k in enumerate(engine_cpp.METRIC_NAMES):
            assert metrics[i, j] == pytest.approx(m[k], rel=1e-9, abs=1e-12), (s.name, k)
        np.testing.assert_allclose(rets[i], bar_returns(r.equity), rtol=1e-9, atol=1e-15)
