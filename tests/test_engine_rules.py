"""Behavioural rules every engine must obey (run against both)."""
import numpy as np
import pytest

from bt import engine_cpp, engine_py
from bt.config import ExecConfig, StrategyConfig, TSMOM, DONCHIAN
from bt.synthetic import make_bars

ENGINES = [engine_py, engine_cpp]
BARS = make_bars(n=800, seed=3)
STRAT = StrategyConfig(TSMOM, (10, 1))


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_no_lookahead(eng):
    """Changing the future must not change any earlier signal or equity."""
    o, c, v = (BARS[k].copy() for k in ("open", "close", "volume"))
    base = eng.run_backtest(o, c, v, StrategyConfig(DONCHIAN, (20, 10)), ExecConfig())
    k = 500
    c2, o2 = c.copy(), o.copy()
    c2[k:] *= 3.0   # a huge future spike
    o2[k:] *= 3.0
    alt = eng.run_backtest(o2, c2, v, StrategyConfig(DONCHIAN, (20, 10)), ExecConfig())
    np.testing.assert_array_equal(base.target[:k], alt.target[:k])
    np.testing.assert_allclose(base.equity[:k], alt.equity[:k], rtol=1e-12)


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_costs_never_help(eng):
    """Adding fees / spread / impact can only lower final equity (same trades)."""
    args = (BARS["open"], BARS["close"], BARS["volume"], STRAT)
    free = eng.run_backtest(*args, ExecConfig())
    for ex in [ExecConfig(fee_bps=5), ExecConfig(half_spread_bps=3), ExecConfig(impact_k=1.0)]:
        paid = eng.run_backtest(*args, ex)
        assert paid.n_trades == free.n_trades
        assert paid.equity[-1] < free.equity[-1]


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_fee_arithmetic(eng):
    """With no slippage, total fees paid = fee_bps * total traded notional."""
    args = (BARS["open"], BARS["close"], BARS["volume"], STRAT)
    free = eng.run_backtest(*args, ExecConfig())
    paid = eng.run_backtest(*args, ExecConfig(fee_bps=10))
    # First trade happens at the same price and size in both runs, so the
    # very first equity gap equals exactly the first fee.
    first = int(np.argmax(np.abs(free.equity - paid.equity) > 0))
    gap = free.equity[first] - paid.equity[first]
    assert gap == pytest.approx(1e6 * 10e-4, rel=1e-9)  # full 1x position from flat


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_latency_shifts_trades(eng):
    args = (BARS["open"], BARS["close"], BARS["volume"], STRAT)
    a = eng.run_backtest(*args, ExecConfig(latency_bars=0))
    b = eng.run_backtest(*args, ExecConfig(latency_bars=3))
    first_a = int(np.argmax(a.equity != 1e6))
    first_b = int(np.argmax(b.equity != 1e6))
    assert first_b == first_a + 3


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_long_only_never_short(eng):
    args = (BARS["open"], BARS["close"], BARS["volume"], STRAT)
    ls = eng.run_backtest(*args, ExecConfig())
    lo = eng.run_backtest(*args, ExecConfig(long_only=True))
    assert (ls.target < 0).any()            # the strategy does want to short...
    assert (lo.target >= 0).all()           # ...but long-only never does
    np.testing.assert_array_equal(lo.target, np.maximum(ls.target, 0))


def _ruin_path(n=80):
    """Prices fall (so momentum goes short), then jump to 2.5x in one bar: the short loses
    more than the whole account."""
    close = np.full(n, 100.0)
    close[20:35] = np.linspace(100.0, 90.0, 15)
    close[35:] = 225.0
    open_ = np.r_[close[0], close[:-1]]           # each bar opens at the previous close...
    open_[35] = 225.0                             # ...except the jump, which gaps at the open
    return open_, close, np.full(n, 1e9)


@pytest.mark.parametrize("eng", ENGINES, ids=["py", "cpp"])
def test_ruin_liquidates_and_stops(eng):
    """A short wiped out by a jump is closed at zero equity and never trades again."""
    o, c, v = _ruin_path()
    r = eng.run_backtest(o, c, v, StrategyConfig(TSMOM, (10, 1)), ExecConfig())
    first_zero = int(np.argmax(r.equity <= 0))
    assert 0 < first_zero <= 36                   # ruined at the jump
    assert np.all(r.equity[first_zero:] == 0.0)   # never negative, never revived
    assert np.all(r.target[first_zero:] == 0.0)   # no positions after ruin
    from bt.metrics import bar_returns, summarize
    ret = bar_returns(r.equity)
    assert np.all(np.isfinite(ret))
    assert ret[first_zero - 1] == -1.0 and np.all(ret[first_zero:] == 0.0)
    m = summarize(r.equity, r.turnover, r.n_trades, 252)
    assert m["max_dd"] == 1.0 and m["total_return"] == -1.0


def test_ruin_same_in_both_engines_and_sweep():
    """Python, C++ and the C++ sweep agree bar by bar on a ruined strategy."""
    from bt.metrics import bar_returns
    o, c, v = _ruin_path()
    strat = StrategyConfig(TSMOM, (10, 1))
    a = engine_py.run_backtest(o, c, v, strat, ExecConfig(fee_bps=10))
    b = engine_cpp.run_backtest(o, c, v, strat, ExecConfig(fee_bps=10))
    np.testing.assert_allclose(a.equity, b.equity, rtol=1e-12, atol=0)
    m, R = engine_cpp.sweep(o, c, v, [strat], ExecConfig(fee_bps=10), 252, return_series=True)
    assert np.all(np.isfinite(R)) and np.all(np.isfinite(m))
    np.testing.assert_allclose(R[0], bar_returns(a.equity), rtol=1e-9, atol=1e-15)


def test_long_only_is_never_ruined():
    """The same path with long-only: a long can't lose more than everything."""
    o, c, v = _ruin_path()
    for eng in ENGINES:
        r = eng.run_backtest(o, c, v, StrategyConfig(TSMOM, (10, 1)), ExecConfig(long_only=True))
        assert np.all(r.equity > 0)
