"""Download raw data into data/raw/. Run once at the start, then freeze with make_snapshot.py.

    python data/download.py binance --interval 1h --start 2019-01 --end 2025-12
    python data/download.py yfinance --start 2005-01-01 --end 2025-12-31
    python data/download.py french
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bt.paths import raw_dir  # noqa: E402

RAW = raw_dir()

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
          "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
ETFS = ["SPY", "QQQ", "IWM", "DIA", "TLT", "IEF", "GLD", "SLV", "EFA", "EEM",
        "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

BINANCE_URL = "https://data.binance.vision/data/spot/monthly/klines/{s}/{i}/{s}-{i}-{y}-{m:02d}.zip"
BINANCE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
                "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
FRENCH_URLS = {
    "ff3_daily": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip",
    "mom_daily": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip",
}


def _get(url: str) -> bytes | None:
    """Download a URL; return None (and print why) if it fails, e.g. a month before listing."""
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except Exception as e:  # missing months (pre-listing) return 404
        print(f"  skip {url.rsplit('/', 1)[-1]}: {e}")
        return None


def parse_binance_csv(f) -> pd.DataFrame:
    """Parse one monthly Binance kline CSV (file-like) into ts/open/high/low/close/volume/trades.

    Handles the optional header row and the 2025 switch from millisecond to
    microsecond timestamps (binance-public-data README).
    """
    df = pd.read_csv(f, header=None, names=BINANCE_COLS)
    if not str(df.iloc[0, 0]).strip().isdigit():   # some files ship a header row
        df = df.iloc[1:]
    ot = df["open_time"].astype("int64")
    ms = ot.where(ot < 10**14, ot // 1000)
    out = pd.DataFrame({"ts": pd.to_datetime(ms, unit="ms", utc=True)})
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = df[c].astype("float64").to_numpy()
    out["trades"] = df["trades"].astype("int64").to_numpy()
    return out.reset_index(drop=True)


def parse_french_csv(text: str) -> pd.DataFrame:
    """Parse a Ken French daily CSV (text). Keeps only the daily block (YYYYMMDD rows),
    converts percent to decimal."""
    lines = text.splitlines()
    # The column header is the first line whose first field is empty, e.g. ",Mkt-RF,SMB,HML,RF"
    hi = next(i for i, l in enumerate(lines) if "," in l and not l.split(",")[0].strip())
    cols = ["date"] + [c.strip() for c in lines[hi].split(",")[1:]]
    rows = []
    for l in lines[hi + 1:]:
        first = l.split(",")[0].strip()
        if len(first) == 8 and first.isdigit():
            rows.append(l)
        elif rows and not first.isdigit():
            break   # end of the daily block (annual tables follow in some files)
    df = pd.read_csv(io.StringIO("\n".join(rows)), header=None, names=cols)
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    for c in cols[1:]:
        v = df[c].astype(float)
        df[c] = v.where(v > -99.0) / 100.0   # -99.99 / -999 mark missing data
    return df


def binance(interval: str, start: str, end: str):
    """Download monthly kline zips for every coin in CRYPTO, parse them, and save one CSV per coin."""
    out = RAW / "binance" / interval
    out.mkdir(parents=True, exist_ok=True)
    months = pd.period_range(start, end, freq="M")
    for sym in CRYPTO:
        frames = []
        for p in months:
            blob = _get(BINANCE_URL.format(s=sym, i=interval, y=p.year, m=p.month))
            if blob is None:
                continue
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                with z.open(z.namelist()[0]) as f:
                    frames.append(parse_binance_csv(f))
        if not frames:
            continue
        df = pd.concat(frames, ignore_index=True)
        df.to_csv(out / f"{sym}.csv", index=False)
        print(f"{sym}: {len(df):,} bars {df.ts.min()} -> {df.ts.max()}")


def yfinance(start: str, end: str):
    """Daily bars for every ETF in ETFS, adjusted for dividends and splits (auto_adjust=True)."""
    import yfinance as yf

    out = RAW / "yfinance"
    out.mkdir(parents=True, exist_ok=True)
    for t in ETFS:
        df = yf.download(t, start=start, end=(pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), auto_adjust=True, progress=False)
        if df.empty:
            print(f"{t}: no data")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower).reset_index().rename(columns={"Date": "ts"})
        df[["ts", "open", "high", "low", "close", "volume"]].to_csv(out / f"{t}.csv", index=False)
        print(f"{t}: {len(df):,} bars")


def french():
    """Ken French's daily factor returns (market, size, value; and momentum)."""
    out = RAW / "french"
    out.mkdir(parents=True, exist_ok=True)
    for name, url in FRENCH_URLS.items():
        blob = _get(url)
        if blob is None:
            continue
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            text = z.read(z.namelist()[0]).decode("latin-1")
        df = parse_french_csv(text)
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name}: {len(df):,} rows {df.date.min().date()} -> {df.date.max().date()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="src", required=True)
    b = sub.add_parser("binance")
    b.add_argument("--interval", default="1h")
    b.add_argument("--start", default="2019-01")
    b.add_argument("--end", default="2025-12")
    y = sub.add_parser("yfinance")
    y.add_argument("--start", default="2005-01-01")
    y.add_argument("--end", default="2025-12-31")
    sub.add_parser("french")
    a = ap.parse_args()
    if a.src == "binance":
        binance(a.interval, a.start, a.end)
    elif a.src == "yfinance":
        yfinance(a.start, a.end)
    else:
        french()
