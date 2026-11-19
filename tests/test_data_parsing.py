"""Offline tests for the download parsers, using small inline fixtures shaped
like the real files."""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
from download import parse_binance_csv, parse_french_csv  # noqa: E402

# 2024 rows are in milliseconds, 2025 rows in microseconds.
BINANCE_MS = (
    "1704067200000,42283.58,42554.57,42261.02,42475.23,1271.68108,1704070799999,53957248.97,47134,682.57,28957416.82,0\n"
    "1704070800000,42475.23,42775.00,42431.65,42613.56,1196.37856,1704074399999,50984893.57,43781,630.35,26862828.51,0\n"
)
BINANCE_US = (
    "1735689600000000,93576.00,94509.42,93489.03,94401.14,755.99010,1735693199999999,71129808.69,99050,402.34,37862143.12,0\n"
)
BINANCE_HEADER = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
                  "taker_buy_volume,taker_buy_quote_volume,ignore\n") + BINANCE_US

FRENCH = """This file was created by CMPT_ME_BEME_RETS_DAILY using the 202509 CRSP database.
The 1-month TBill return is from Ibbotson and Associates Inc.

,Mkt-RF,SMB,HML,RF
19260701,    0.09,   -0.25,   -0.27,    0.01
19260702,    0.45,   -0.33,   -0.06,    0.01
19260706,  -99.99,    0.30,   -0.39,    0.01

Copyright 2025 Eugene F. Fama and Kenneth R. French
"""


def test_binance_ms_and_us_timestamps_agree():
    a = parse_binance_csv(io.StringIO(BINANCE_MS))
    b = parse_binance_csv(io.StringIO(BINANCE_US))
    assert a.ts.iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")
    assert a.ts.iloc[1] == pd.Timestamp("2024-01-01 01:00", tz="UTC")
    assert b.ts.iloc[0] == pd.Timestamp("2025-01-01 00:00", tz="UTC")
    assert list(a.columns) == ["ts", "open", "high", "low", "close", "volume", "trades"]
    assert a.close.iloc[0] == 42475.23 and a.trades.iloc[1] == 43781


def test_binance_header_row_is_skipped():
    df = parse_binance_csv(io.StringIO(BINANCE_HEADER))
    assert len(df) == 1 and df.ts.iloc[0].year == 2025


def test_french_daily_block():
    df = parse_french_csv(FRENCH)
    assert list(df.columns) == ["date", "Mkt-RF", "SMB", "HML", "RF"]
    assert len(df) == 3
    assert df["Mkt-RF"].iloc[0] == 0.0009
    assert np.isnan(df["Mkt-RF"].iloc[2])          # -99.99 -> missing
