"""Where data, results and figures live.

Defaults are folders inside the repo. Two environment variables move them,
which is how the smoke test (experiments/smoke_test.py) runs the whole
pipeline in a temporary folder without touching your real data:

    TGTB_DATA_DIR     replaces <repo>/data      (raw/ and snapshot/ inside it)
    TGTB_RESULTS_DIR  replaces <repo>/results
    TGTB_FIGURES_DIR  replaces <repo>/figures
    TGTB_SITE_DATA_DIR replaces <repo>/site/data   (numbers the website loads)
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    return Path(os.environ.get("TGTB_DATA_DIR", ROOT / "data"))


def raw_dir() -> Path:
    return data_dir() / "raw"


def snapshot_dir() -> Path:
    return data_dir() / "snapshot"


def results_dir() -> Path:
    return Path(os.environ.get("TGTB_RESULTS_DIR", ROOT / "results"))


def figures_dir() -> Path:
    return Path(os.environ.get("TGTB_FIGURES_DIR", ROOT / "figures"))


def site_data_dir() -> Path:
    return Path(os.environ.get("TGTB_SITE_DATA_DIR", ROOT / "site" / "data"))
