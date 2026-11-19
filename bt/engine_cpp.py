"""Python bindings for the C++ engine.

PURPOSE
  Let Python code call the compiled C++ engine (engine_cpp/build/libtgtb.so on
  Linux/WSL, .dylib on Mac) as if it were a Python function. Uses `ctypes`, which
  ships with Python, so no extra build tools (pybind11 etc.) are needed.

HOW IT WORKS
  1. lib() opens the compiled library once and declares each C function's
     argument types (argtypes) and return type (restype). ctypes needs these
     to convert Python values into the C types the function expects.
  2. NumPy arrays are passed with np.ctypeslib.ndpointer, which hands C a
     pointer straight into the array's memory -- no copying. That is why
     arrays are first made "C-contiguous float64" by _f64().
  3. Output arrays (equity, metrics, returns) are allocated here in Python and
     filled in place by the C++ code.

run_backtest() mirrors bt.engine_py.run_backtest exactly (same inputs, same
BacktestResult), which is what makes the parity tests possible.
"""
from __future__ import annotations

import ctypes as C
import sys
from pathlib import Path

import numpy as np

from .config import N_PARAMS, ExecConfig, StrategyConfig

# Order of the numbers compute_metrics() writes for each configuration in a sweep.
METRIC_NAMES = ["sharpe", "total_return", "max_dd", "ann_turnover", "n_trades", "mean_ret"]

_ROOT = Path(__file__).resolve().parents[1]
_LIBNAME = "libtgtb.dylib" if sys.platform == "darwin" else "libtgtb.so"
_LIB_PATH = _ROOT / "engine_cpp" / "build" / _LIBNAME

# Type descriptions ctypes uses to pass NumPy arrays as C pointers.
_dp = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")   # double*
_ip = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")     # int*
_lib = None                                                             # loaded on first use


def lib():
    """Load the compiled engine (once) and declare its function signatures."""
    global _lib
    if _lib is None:
        if not _LIB_PATH.exists():
            raise FileNotFoundError(f"{_LIB_PATH} not found -- run `make build` first")
        L = C.CDLL(str(_LIB_PATH))
        if L.tgtb_version() != 2:      # compiled from an older engine.cpp
            raise RuntimeError("stale C++ library -- run `make -C engine_cpp clean` then `make build`")
        # tgtb_run(open, close, volume, n, family, params, fee, half_spread, impact_k,
        #          latency, capital, long_only, equity_out, target_out, turnover_out) -> n_trades
        L.tgtb_run.restype = C.c_int
        L.tgtb_run.argtypes = [_dp, _dp, _dp, C.c_int, C.c_int, _dp,
                               C.c_double, C.c_double, C.c_double, C.c_int, C.c_double,
                               C.c_int, _dp, _dp, C.POINTER(C.c_double)]
        # tgtb_sweep(open, close, volume, n, n_cfg, families, params, fee, half_spread, impact_k,
        #            latency, capital, long_only, periods_per_year, metrics_out, returns_out)
        L.tgtb_sweep.restype = None
        L.tgtb_sweep.argtypes = [_dp, _dp, _dp, C.c_int, C.c_int, _ip, _dp,
                                 C.c_double, C.c_double, C.c_double, C.c_int, C.c_double,
                                 C.c_int, C.c_double, _dp, C.c_void_p]
        _lib = L
    return _lib


def _f64(x):
    """Make an array C-contiguous float64, the memory layout the C++ code expects."""
    return np.ascontiguousarray(x, dtype=np.float64)


def run_backtest(open_, close, volume, strat: StrategyConfig, ex: ExecConfig):
    """One backtest in C++. Same signature and outputs as bt.engine_py.run_backtest."""
    from .engine_py import BacktestResult

    o, c, v = _f64(open_), _f64(close), _f64(volume)
    n = len(c)
    eq, tg = np.empty(n), np.empty(n)          # filled in place by C++
    turnover = C.c_double(0.0)                 # C++ writes into this through a pointer
    trades = lib().tgtb_run(o, c, v, n, strat.family, _f64(strat.padded()),
                            ex.fee_bps, ex.half_spread_bps, ex.impact_k, ex.latency_bars, ex.capital,
                            int(ex.long_only), eq, tg, C.byref(turnover))
    return BacktestResult(eq, tg, turnover.value, trades)


def sweep(open_, close, volume, configs: list[StrategyConfig], ex: ExecConfig,
          periods_per_year: float, return_series: bool = False):
    """Run many configurations on one asset in a single C++ call (the fast path).

    Returns (metrics, returns):
      metrics  array (n_configs, 6), columns in METRIC_NAMES order
      returns  array (n_configs, n_bars - 1) of per-bar returns if return_series,
               else None. The statistics (DSR, PBO) need the full return series.
    """
    o, c, v = _f64(open_), _f64(close), _f64(volume)
    n, k = len(c), len(configs)
    fam = np.array([s.family for s in configs], dtype=np.int32)
    par = _f64(np.array([s.padded() for s in configs]).reshape(k * N_PARAMS))   # flat: 4 per config
    metrics = np.empty(k * len(METRIC_NAMES))
    rets = np.empty(k * (n - 1)) if return_series else None
    lib().tgtb_sweep(o, c, v, n, k, fam, par,
                     ex.fee_bps, ex.half_spread_bps, ex.impact_k, ex.latency_bars, ex.capital,
                     int(ex.long_only), periods_per_year, metrics,
                     rets.ctypes.data_as(C.c_void_p) if rets is not None else None)   # NULL = skip
    metrics = metrics.reshape(k, len(METRIC_NAMES))
    return metrics, (rets.reshape(k, n - 1) if rets is not None else None)
