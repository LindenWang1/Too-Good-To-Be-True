"""Freeze data/raw/ into data/snapshot/ (Parquet) + MANIFEST.json with SHA-256 hashes.

Every experiment reads only from data/snapshot/. Commit MANIFEST.json, not the data:
anyone can re-run download.py + this script and check the hashes match.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bt.paths import raw_dir, snapshot_dir  # noqa: E402

RAW, SNAP = raw_dir(), snapshot_dir()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by time, drop duplicate timestamps and rows with missing or non-positive prices."""
    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    price = ["open", "high", "low", "close"]
    df = df.dropna(subset=price)
    df = df[(df[price] > 0).all(axis=1)]
    return df


def sha256(path: Path) -> str:
    """Fingerprint of a file: changes completely if even one byte changes.
    Read in 1 MB chunks so big files don't need to fit in memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    """Clean every raw CSV, save it as Parquet, and record rows/date range/hash in MANIFEST.json."""
    SNAP.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for csv in sorted(RAW.rglob("*.csv")):
        rel = csv.relative_to(RAW).with_suffix(".parquet")
        dst = SNAP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(csv)
        if "ts" in df.columns:
            df = clean(df)
            span = [str(df.ts.min()), str(df.ts.max())]
        else:
            span = [str(df.iloc[0, 0]), str(df.iloc[-1, 0])]
        df.to_parquet(dst, index=False)
        manifest[str(rel)] = {"rows": len(df), "span": span, "sha256": sha256(dst)}
        print(f"{rel}: {len(df):,} rows")
    (SNAP / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {len(manifest)} files + MANIFEST.json")


if __name__ == "__main__":
    main()
