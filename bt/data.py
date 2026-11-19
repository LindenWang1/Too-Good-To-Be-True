"""Loading bars from the snapshot (Parquet) or raw downloads (CSV)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .paths import raw_dir, snapshot_dir

MARKET_GLOBS = {"crypto": "binance/1h/*", "etf": "yfinance/*"}


def read_bars(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.sort_values("ts").reset_index(drop=True)


def market_files(market: str) -> list[Path]:
    """The market's snapshot Parquet files if a snapshot exists, else its raw CSVs."""
    g = MARKET_GLOBS[market]
    snap = sorted(snapshot_dir().glob(g + ".parquet"))
    return snap if snap else sorted(raw_dir().glob(g + ".csv"))


def to_arrays(df: pd.DataFrame) -> dict:
    """The columns the engines use (plus high/low when present, for spread estimates)."""
    out = {k: df[k].to_numpy(dtype=float) for k in ("open", "close", "volume")}
    for k in ("high", "low"):
        if k in df.columns:
            out[k] = df[k].to_numpy(dtype=float)
    return out


def synthetic_market(n_assets: int = 4, n: int = 3 * 8760, seed: int = 0,
                     start: str = "2020-01-01", freq: str = "h") -> dict[str, pd.DataFrame]:
    """Stand-in for a market folder, for running scripts before real data exists.
    Odd-numbered assets get a weak momentum effect; even-numbered ones are pure noise."""
    from .synthetic import make_bars

    out = {}
    rng = np.random.default_rng(seed)
    for i in range(n_assets):
        b = make_bars(n=n, seed=seed + i, ar1=0.02 * (i % 2))
        ts = pd.date_range(start, periods=n, freq=freq, tz="UTC")
        df = pd.DataFrame({"ts": ts, "open": b["open"], "close": b["close"], "volume": b["volume"]})
        # Intrabar range: a little beyond the open/close, so a spread estimate has something to see.
        wiggle = np.abs(rng.normal(0, 0.002, n))
        df["high"] = np.maximum(df.open, df.close) * (1 + wiggle)
        df["low"] = np.minimum(df.open, df.close) * (1 - wiggle)
        out[f"SYN{i}"] = df
    return out
