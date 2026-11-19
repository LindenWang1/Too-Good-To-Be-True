"""Run the WHOLE pipeline end to end on fake data, in a temporary folder.

    python experiments/smoke_test.py          (or: make smoke)

Why: unit tests check pieces; this checks that the pieces fit together --
validate -> sweep -> in-sample charts -> out-of-sample analysis -> model --
exactly as you will run them on real data. It takes about a minute, never
touches data/, results/ or figures/ in the repo (it points the scripts at a temp
folder through the TGTB_* environment variables, see bt/paths.py), and CI runs it
on every push.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bt.data import synthetic_market  # noqa: E402


def run(args: list[str], env: dict) -> None:
    """Run one pipeline script; stop with its output if it fails."""
    print("$", " ".join(args), flush=True)
    r = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        sys.exit(f"FAILED: {' '.join(args)}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        env = {**os.environ, "TGTB_DATA_DIR": str(tmp / "data"), "TGTB_RESULTS_DIR": str(tmp / "results"),
               "TGTB_FIGURES_DIR": str(tmp / "figures"), "TGTB_SITE_DATA_DIR": str(tmp / "site_data")}

        # Fake raw downloads in the same layout download.py produces.
        crypto = tmp / "data" / "raw" / "binance" / "1h"
        etf = tmp / "data" / "raw" / "yfinance"
        crypto.mkdir(parents=True)
        etf.mkdir(parents=True)
        for name, df in synthetic_market(n_assets=3, n=int(3.5 * 8760), start="2020-01-01", seed=1).items():
            df.to_csv(crypto / f"{name}USDT.csv", index=False)
        for name, df in synthetic_market(n_assets=3, n=3000, start="2008-01-01", freq="B", seed=9).items():
            df.to_csv(etf / f"{name}.csv", index=False)

        quick = ["--grid-step", "4"]                     # 46 of 182 configurations, for speed
        run(["data/validate.py", "--market", "crypto"], env)
        run(["experiments/run_sweep.py", "--market", "crypto", "--long-only", "--placebo", "1", *quick], env)
        run(["experiments/run_sweep.py", "--market", "etf", *quick], env)
        for r in ("crypto_long_only", "etf"):
            run(["experiments/is_charts.py", "--run", r], env)
            run(["experiments/oos_analysis.py", "--run", r], env)
        run(["experiments/train_survival_model.py", "--market", "crypto_long_only",
             "--target", "fee10_spread+impact_lat1", "--notes", "smoke test"], env)

        # Check the expected files exist and the headline numbers are sane.
        expect = [tmp / "results" / "crypto_long_only" / f for f in
                  ("sweep_is.csv.gz", "SEALED_sweep_oos.csv.gz", "costs_used.csv", "run_info.json",
                   "is_summary.json", "oos_summary.json")]
        expect += [tmp / "figures" / f"crypto_long_only_{f}.png" for f in
                   ("cost_curves", "heatmap_ma", "turnover", "funnel", "shrinkage")]
        missing = [str(p) for p in expect if not p.exists()]
        if missing:
            sys.exit("missing outputs:\n  " + "\n  ".join(missing))
        s = json.loads((tmp / "results" / "crypto_long_only" / "oos_summary.json").read_text())
        f = s["funnel_real"]
        assert all(a >= b for a, b in zip(f, f[1:])), f"funnel must only shrink: {f}"
        assert s["funnel_placebo"] is not None
        print(f"\nSMOKE TEST PASSED  funnel {f}  shrinkage slope {s['shrinkage_slope']}")


if __name__ == "__main__":
    main()
