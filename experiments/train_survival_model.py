"""Modeling Question: which in-sample winners survive out of sample?

Builds the model table (bt/survival_model.build_dataset), runs the model ladder
(bt/survival_model.evaluate), prints the comparison and logs it.

    python experiments/train_survival_model.py --market crypto_long_only \
        --target fee10_spread+impact_lat1 --low fee0_none_lat0 --high fee20_spread+impact_lat1
    python experiments/train_survival_model.py --demo     # synthetic dry run

Every run appends to results/experiment_log.jsonl -- write a --notes line saying
what you changed, so the "what helped / what didn't" slide writes itself.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from bt.paths import results_dir  # noqa: E402
from bt.survival_model import build_dataset, evaluate, log_experiment  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="crypto_long_only", help="folder under results/")
    ap.add_argument("--target", default="fee10_spread+impact_lat1")
    ap.add_argument("--low", default="fee0_none_lat0")
    ap.add_argument("--high", default="fee20_spread+impact_lat1")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    if a.demo:
        sweep = pd.read_csv(results_dir() / "demo" / "sweep.csv")
        sweep_is, oos = sweep, sweep[["asset", "setting", "config", "oos_sharpe"]]
        a.target, a.low, a.high, a.market = "fee2", "fee0", "fee20", "demo"
    else:
        d = results_dir() / a.market
        sweep_is = pd.read_csv(d / "sweep_is.csv.gz")
        oos = pd.read_csv(d / "SEALED_sweep_oos.csv.gz")

    data = build_dataset(sweep_is, oos, a.target, a.low, a.high)
    rate = data.survive.mean()
    if rate in (0.0, 1.0):
        print(f"WARNING: {'none' if rate == 0 else 'all'} of the strategies survive under '{a.target}', "
              "so AUC is undefined. That is itself a finding; try a lower-cost --target to compare models.")
    res = evaluate(data)
    print(f"{len(data):,} (asset, config) rows; {data.survive.mean():.1%} survive out of sample "
          f"under '{a.target}'\n")
    with pd.option_context("display.width", 200, "display.precision", 3, "display.max_columns", 20):
        print(res)
    log_experiment(results_dir() / "experiment_log.jsonl", f"survival_{a.market}", res,
                   notes=a.notes, target=a.target, low=a.low, high=a.high)


if __name__ == "__main__":
    main()
