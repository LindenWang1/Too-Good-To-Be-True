"""Python Reference Backtester: the source of "truth" for the project.

PURPOSE
  Simulate trading one strategy on one asset, bar by bar, the way it would have
  happened live, including fees, slippage and delays. It is deliberately simple
  (one plain loop, no clever tricks) so every line can be checked by eye. The
  fast C++ engine (engine_cpp/src/engine.cpp) must reproduce its results exactly;
  tests/test_parity.py enforces that.

TIMING RULES (how look-ahead bias is prevented)
  * At the CLOSE of bar t the strategy sees prices close[0..t] -- never later
    ones -- and picks a target position: +1 (long), 0 (flat) or -1 (short).
  * That target is scheduled for the OPEN of bar t + 1 + latency. So a decision
    is always traded at a later price than the one it was based on.
  * At an open with a scheduled target that differs from the current one, we
    trade to   units = target * equity_at_open / open   (fully invested, 1x).
  * Equity (cash + holdings) is recorded at every close.

RUIN (limited liability)
  * A losing short can lose more than the whole account (a long can't: prices
    stay above zero). If equity reaches zero or below -- at an open, before
    trading, or at a close -- the position is liquidated, equity is set to 0 and
    the strategy stops trading for good, as a broker would close the account.
    Its return is -100% on that bar and 0 on every bar after.

COSTS ON EACH TRADE
  * fill price  = open * (1 +/- slippage)  -- buyers pay more, sellers get less
  * slippage    = half_spread + impact_k * sigma * sqrt(shares traded / bar volume)
                  (sigma = recent volatility; the square-root law of market impact)
  * fee         = fee_bps of the traded amount
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import (
    DONCHIAN, MA_CROSS, RSI_MR, TSMOM, ZSCORE_MR, VOL_WINDOW,
    ExecConfig, StrategyConfig,
)


@dataclass
class BacktestResult:
    """Everything one backtest produces."""
    equity: np.ndarray       # portfolio value at each close; equity[0] = starting capital
    target: np.ndarray       # the position the strategy chose at each close (-1, 0, +1)
    turnover: float          # total traded value / equity at the time, summed over all trades
    n_trades: int            # number of trades executed


# --------------------------------------------------------------------------
# Small maths helpers. Written as plain loops ON PURPOSE: the C++ engine adds
# numbers in exactly the same order, so both engines round identically and
# their results can be compared to 1e-9.
# --------------------------------------------------------------------------

def _mean(x):
    """Average of a window of prices."""
    return sum(x) / len(x)


def _pstd(x):
    """Population standard deviation (divides by n, not n-1) of a window."""
    m = _mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


# --------------------------------------------------------------------------
# Strategies. Each is a small "state machine": given the prices up to bar t and
# the position it chose last bar (`prev`), return the position it wants now.
# Parameters arrive padded to 4 numbers (see StrategyConfig.padded).
# --------------------------------------------------------------------------

def strategy_target(cfg: StrategyConfig, close: np.ndarray, t: int, prev: float) -> float:
    """Target position (-1, 0, +1) chosen at the close of bar t. Uses close[0..t] only."""
    f, p = cfg.family, cfg.padded()

    if f == TSMOM:
        # Time-series momentum: long if the price rose over the last `lookback` bars,
        # short if it fell. Only re-decides every `rebalance` bars.
        lookback, rebalance = int(p[0]), max(1, int(p[1]))
        if t < lookback:
            return 0.0                                   # not enough history yet
        if t % rebalance != 0:
            return prev                                  # between rebalances: hold
        r = close[t] / close[t - lookback] - 1.0
        return 1.0 if r > 0 else (-1.0 if r < 0 else 0.0)

    if f == MA_CROSS:
        # Moving-average crossover: long when the fast average is above the slow one.
        fast, slow = int(p[0]), int(p[1])
        if t < slow - 1:
            return 0.0
        mf = _mean(close[t - fast + 1: t + 1])           # last `fast` closes, including t
        ms = _mean(close[t - slow + 1: t + 1])
        return 1.0 if mf > ms else (-1.0 if mf < ms else 0.0)

    if f == ZSCORE_MR:
        # Z-score mean reversion: bet that an unusually high (low) price falls (rises)
        # back toward its recent average. z = how many std devs from the average.
        window, entry, exit_ = int(p[0]), p[1], p[2]
        if t < window - 1:
            return 0.0
        w = close[t - window + 1: t + 1]
        sd = _pstd(w)
        if sd == 0:
            return prev                                  # flat prices: z undefined, hold
        z = (close[t] - _mean(w)) / sd
        if prev == 0.0:                                  # flat: look for an entry
            if z > entry:
                return -1.0                              # too high -> short
            if z < -entry:
                return 1.0                               # too low -> long
            return 0.0
        if prev > 0 and z >= -exit_:                     # long and back near average: exit
            return 0.0
        if prev < 0 and z <= exit_:                      # short and back near average: exit
            return 0.0
        return prev

    if f == DONCHIAN:
        # Donchian breakout: buy a new `ent`-bar high, sell short a new low.
        # Exit when the price breaks the opposite `ext`-bar extreme.
        ent, ext = int(p[0]), int(p[1])
        pos = prev
        if t >= ext:                                     # exits first...
            lo_x, hi_x = min(close[t - ext: t]), max(close[t - ext: t])   # bars before t only
            if pos > 0 and close[t] < lo_x:
                pos = 0.0
            elif pos < 0 and close[t] > hi_x:
                pos = 0.0
        if pos == 0.0 and t >= ent:                      # ...then entries, if flat
            lo_e, hi_e = min(close[t - ent: t]), max(close[t - ent: t])
            if close[t] > hi_e:
                pos = 1.0
            elif close[t] < lo_e:
                pos = -1.0
        return pos

    if f == RSI_MR:
        # RSI reversion: RSI (0-100) compares recent gains with recent losses.
        # Below `lower` = oversold -> buy; above `upper` = overbought -> short.
        # Exit when RSI crosses back through 50.
        period, lower, upper = int(p[0]), p[1], p[2]
        if t < period:
            return 0.0
        gain = loss = 0.0
        for i in range(t - period + 1, t + 1):
            d = close[i] - close[i - 1]
            if d > 0:
                gain += d
            else:
                loss -= d
        rsi = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
        if prev == 0.0:
            if rsi < lower:
                return 1.0
            if rsi > upper:
                return -1.0
            return 0.0
        if prev > 0 and rsi >= 50:
            return 0.0
        if prev < 0 and rsi <= 50:
            return 0.0
        return prev

    raise ValueError(f"unknown family {f}")


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def _sigma_before(close: np.ndarray, t: int) -> float:
    """Volatility for the impact model: population std of the VOL_WINDOW (20) log
    returns ending at close[t-1] -- i.e. known before the open of bar t."""
    if t - VOL_WINDOW < 1:
        return 0.0
    r = [math.log(close[i] / close[i - 1]) for i in range(t - VOL_WINDOW, t)]
    return _pstd(r)


def run_backtest(
    open_: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    strat: StrategyConfig,
    ex: ExecConfig,
) -> BacktestResult:
    """Simulate one strategy on one asset. See the module docstring for the rules."""
    n = len(close)
    equity = np.empty(n)
    targets = np.zeros(n)
    sched = [None] * n            # sched[t] = target to trade at the open of bar t (None = no order)

    cash, units = ex.capital, 0.0  # start all in cash, holding nothing
    cur_target = 0.0               # the position we currently hold (-1, 0, +1)
    turnover, n_trades = 0.0, 0
    equity[0] = cash
    prev = 0.0                     # the strategy's last decision (its internal state)
    ruined = False                 # True once equity has hit zero (see RUIN above)

    for t in range(n):
        if ruined:                                            # account closed: nothing left to trade
            equity[t] = 0.0
            targets[t] = 0.0
            continue

        # 0) At the OPEN of bar t: a price gap can wipe out a short before any trade.
        if t > 0 and units != 0.0 and cash + units * open_[t] <= 0.0:
            ruined = True                                     # liquidated at the open
            equity[t] = 0.0
            targets[t] = 0.0
            continue

        # 1) At the OPEN of bar t: execute an order scheduled earlier, if it changes the position.
        if t > 0 and sched[t] is not None and sched[t] != cur_target:
            eq_open = cash + units * open_[t]                 # portfolio value right now
            desired = sched[t] * eq_open / open_[t]           # shares (or coins) we want to hold
            delta = desired - units                           # >0 buy, <0 sell
            if delta != 0.0:
                part = abs(delta) / volume[t] if volume[t] > 0 else 0.0     # our share of the bar's volume
                slip = ex.half_spread_bps * 1e-4 + ex.impact_k * _sigma_before(close, t) * math.sqrt(part)
                price = open_[t] * (1.0 + slip) if delta > 0 else open_[t] * (1.0 - slip)
                notional = abs(delta) * price                 # value traded
                cash -= delta * price                         # pay for buys / receive for sells
                cash -= notional * ex.fee_bps * 1e-4          # the fee
                turnover += abs(delta) * open_[t] / eq_open
                n_trades += 1
                units = desired
            cur_target = sched[t]

        # 2) At the CLOSE of bar t: record what the portfolio is worth.
        equity[t] = cash + units * close[t]
        if equity[t] <= 0.0:                                  # ruin: liquidate and stop for good
            ruined = True
            equity[t] = 0.0
            targets[t] = 0.0
            continue

        # 3) Still at the close: decide the next position from prices up to close[t],
        #    and schedule it for a LATER open (t + 1 + latency).
        prev = strategy_target(strat, close, t, prev)    # the strategy keeps its own state...
        tgt = max(prev, 0.0) if ex.long_only else prev   # ...but long-only never goes short
        targets[t] = tgt
        exec_bar = t + 1 + ex.latency_bars
        if exec_bar < n:
            sched[exec_bar] = tgt

    return BacktestResult(equity, targets, turnover, n_trades)
