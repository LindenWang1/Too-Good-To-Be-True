"""Tests for the spread estimator (bt/costs.py), the clustered Deflated Sharpe
(bt/stats.py), the paths module, and the in-sample break-even helper."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

from bt.costs import corwin_schultz, half_spread_bps, spread_for_asset, tick_half_spread_bps
from bt.markets import MARKETS
from bt.stats import deflated_sharpe, deflated_sharpe_clustered, effective_trials, psr, psr_vec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from is_charts import break_even  # noqa: E402


# --- Corwin-Schultz -------------------------------------------------------

def test_no_range_means_no_spread():
    p = np.full(100, 50.0)
    assert np.all(corwin_schultz(p, p) == 0)


def test_bid_ask_bounce_is_detected():
    """A price that never moves but trades at bid 99.9 / ask 100.1 has a 0.2% spread.
    Every bar's high is the ask and low the bid, so the estimate should be about 20 bps."""
    high, low = np.full(200, 100.1), np.full(200, 99.9)
    s = corwin_schultz(high, low)
    assert np.median(s) == pytest.approx(0.002, rel=0.05)
    assert half_spread_bps(high, low) == pytest.approx(10, rel=0.05)


def test_half_spread_uses_only_bars_before_split():
    high = np.r_[np.full(100, 100.1), np.full(100, 101.0)]      # spread widens after bar 100
    low = np.r_[np.full(100, 99.9), np.full(100, 99.0)]
    assert half_spread_bps(high, low, until=100) == pytest.approx(10, rel=0.05)


# --- spread models (what the sweep actually charges) ---------------------

def test_tick_spread_is_half_a_cent_over_price():
    """A one-cent spread on a $100 ETF is 1 bp wide: half-spread 0.5 bps.
    Only prices before `until` count (here the price doubles afterwards)."""
    close = np.r_[np.full(50, 100.0), np.full(50, 200.0)]
    assert tick_half_spread_bps(close, 0.01, until=50) == pytest.approx(0.5)
    assert tick_half_spread_bps(close, 0.01) == pytest.approx(0.5 * 100 / 150)


def test_market_spread_models():
    """Crypto charges a fixed 1 bp, ETFs one tick; Corwin-Schultz is only reported."""
    high, low = np.full(200, 100.1), np.full(200, 99.9)          # CS sees a 10 bp half-spread
    bars = {"close": np.full(200, 100.0), "high": high, "low": low}
    c = spread_for_asset(MARKETS["crypto"], bars, until=100)
    assert c["half_spread_bps"] == 1.0 and c["cs_half_spread_bps"] == pytest.approx(10, rel=0.05)
    e = spread_for_asset(MARKETS["etf"], bars, until=100)
    assert e["half_spread_bps"] == pytest.approx(0.5) and "tick" in e["spread_source"]
    cs = spread_for_asset({"spread_model": "cs", "default_half_spread_bps": 1.0}, bars)
    assert cs["half_spread_bps"] == pytest.approx(10, rel=0.05)
    split = spread_for_asset(MARKETS["etf"], bars, until=100, asset="XLK")      # XLK split 2:1 in 2025
    assert split["half_spread_bps"] == pytest.approx(0.25)                     # prices x2 -> half the bps
    no_hl = spread_for_asset({"spread_model": "cs", "default_half_spread_bps": 1.0}, {"close": bars["close"]})
    assert no_hl["half_spread_bps"] == 1.0 and np.isnan(no_hl["cs_half_spread_bps"])


# --- clustered Deflated Sharpe -------------------------------------------

def test_near_copies_count_as_one_trial():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (1, 3000))
    copies = base + rng.normal(0, 0.1, (50, 3000))
    assert effective_trials(copies)["n_eff"] == 1


def test_independent_strategies_each_count():
    rng = np.random.default_rng(1)
    assert effective_trials(rng.normal(0, 1, (30, 3000)))["n_eff"] == 30


def test_clustering_lowers_the_luck_bar_for_duplicates():
    """200 near-identical variants of one noise strategy: the naive DSR treats them as
    200 independent tries; the clustered DSR knows it was essentially one."""
    rng = np.random.default_rng(2)
    base = rng.normal(0.0005, 0.01, (1, 2000))
    R = base + rng.normal(0, 0.001, (200, 2000))
    srs = R.mean(1) / R.std(1, ddof=1)
    best = int(np.argmax(srs))
    naive = deflated_sharpe(R[best], srs)
    clus = deflated_sharpe_clustered(R, best)
    assert clus["n_eff"] < 5
    assert clus["sr0"] < naive["sr0"] or naive["sr0"] == 0


def test_psr_vec_matches_scalar():
    sr, sk, ku = np.array([0.02, 0.05, -0.01]), np.array([0.0, -0.5, 0.3]), np.array([3.0, 6.0, 4.0])
    v = psr_vec(sr, 1000, sk, ku, 0.01)
    for i in range(3):
        assert v[i] == pytest.approx(psr(sr[i], 1000, sk[i], ku[i], 0.01))


# --- misc -----------------------------------------------------------------

def test_break_even_interpolates():
    assert break_even([0, 5, 10, 20], [1.0, 0.5, 0.0, -1.0]) == pytest.approx(10)
    assert break_even([0, 5, 10, 20], [-0.1, -0.5, -1, -2]) == 0.0
    assert break_even([0, 5, 10, 20], [2.0, 1.5, 1.2, 0.5]) is None


def test_paths_follow_environment(monkeypatch, tmp_path):
    import bt.paths as paths
    monkeypatch.setenv("TGTB_RESULTS_DIR", str(tmp_path / "r"))
    importlib.reload(paths)
    assert paths.results_dir() == tmp_path / "r"
    monkeypatch.delenv("TGTB_RESULTS_DIR")
    assert paths.results_dir() == paths.ROOT / "results"
