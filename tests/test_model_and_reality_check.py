import numpy as np
import pandas as pd
import pytest

from bt import engine_cpp
from bt.config import ExecConfig, StrategyConfig, TSMOM
from bt.metrics import summarize
from bt.reality_check import reality_check
from bt.survival_model import build_dataset, evaluate, neighbor_stats
from bt.synthetic import make_bars


def test_break_even_fee_roughly_zeroes_the_sharpe():
    b = make_bars(n=20000, seed=11, ar1=0.05)
    s = StrategyConfig(TSMOM, (5, 1))
    free = engine_cpp.run_backtest(b["open"], b["close"], b["volume"], s, ExecConfig())
    m = summarize(free.equity, free.turnover, free.n_trades, 8760)
    r = free.equity[1:] / free.equity[:-1] - 1
    vol = r.std(ddof=1) * np.sqrt(8760)
    rc = reality_check(m["sharpe"], years=len(r) / 8760, periods_per_year=8760,
                       ann_vol=vol, ann_turnover=m["ann_turnover"])
    assert m["sharpe"] > 1.0
    paid = engine_cpp.run_backtest(b["open"], b["close"], b["volume"], s,
                                   ExecConfig(fee_bps=rc["break_even_fee_bps"]))
    m2 = summarize(paid.equity, paid.turnover, paid.n_trades, 8760)
    assert abs(m2["sharpe"]) < 0.25 * m["sharpe"]


def test_more_trials_lower_dsr():
    a = reality_check(1.5, years=3, periods_per_year=252, n_trials=1)
    b = reality_check(1.5, years=3, periods_per_year=252, n_trials=1000)
    assert a["dsr"] == pytest.approx(a["psr"])
    assert b["dsr"] < a["dsr"] and b["luck_sharpe_ann"] > 1.0


def _fake_sweep(n_assets=4, seed=0):
    rng = np.random.default_rng(seed)
    rows, oos = [], []
    for a in range(n_assets):
        for fam, k in [("tsmom", 20), ("ma_cross", 20)]:
            for i in range(k):
                cfg = f"{fam}({i}, {i % 5})"
                true = rng.normal(0, 0.5)
                for setting, cost in [("lo", 0.0), ("mid", 0.5), ("hi", 1.0)]:
                    turn = 10 + i
                    rows.append({"asset": f"A{a}", "setting": setting, "family": fam, "config": cfg,
                                 "is_sharpe": true + rng.normal(0, 0.5) - cost * turn / 20,
                                 "is_psr0": 0.5, "is_dsr": 0.1, "ann_turnover": turn,
                                 "n_trades": 100, "max_dd": 0.2})
                    oos.append({"asset": f"A{a}", "setting": setting, "config": cfg,
                                "oos_sharpe": true + rng.normal(0, 0.5) - cost * turn / 20})
    return pd.DataFrame(rows), pd.DataFrame(oos)


def test_survival_model_pipeline_runs_and_is_grouped():
    sw, oos = _fake_sweep()
    data = build_dataset(sw, oos, "mid", "lo", "hi")
    assert len(data) == 4 * 40 and data.survive.isin([0, 1]).all()
    res = evaluate(data)
    assert set(res.index) == {"naive_is_sharpe", "logistic", "boosted_trees"}
    assert res.loc["naive_is_sharpe", "test_auc"] > 0.55   # IS Sharpe carries real signal here


def test_neighbors_flag_isolated_peaks():
    df = pd.DataFrame({"asset": "A", "family": "f",
                       "config": [f"f({i}, 0)" for i in range(6)],
                       "is_sharpe": [0, 0, 0, 3.0, 0, 0]})
    nb = neighbor_stats(df).set_index("config")
    assert nb.loc["f(3, 0)", "neighbor_gap"] > 2.5


def test_js_matches_python():
    """site/reality_check.js must give the same numbers as bt/reality_check.py."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    js = Path(__file__).resolve().parents[1] / "site" / "reality_check.js"
    cases = [[1.5, 3, 252, 1, 0.2, 4], [1.5, 3, 252, 1000, 0.2, 4], [2.2, 2, 8760, 182, 0.6, 40]]
    script = (f"const {{realityCheck}} = require({json.dumps(str(js))});"
              f"console.log(JSON.stringify({json.dumps(cases)}.map(c => realityCheck({{sharpeAnn:c[0], years:c[1],"
              f" periodsPerYear:c[2], nTrials:c[3], annVol:c[4], annTurnover:c[5]}}))));")
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    for c, j in zip(cases, out):
        p = reality_check(c[0], c[1], c[2], n_trials=c[3], ann_vol=c[4], ann_turnover=c[5])
        assert j["psr"] == pytest.approx(p["psr"], abs=1e-6)
        assert j["dsr"] == pytest.approx(p["dsr"], abs=1e-6)
        assert j["luckSharpeAnn"] == pytest.approx(p["luck_sharpe_ann"], rel=1e-6)
