import numpy as np
import pytest
from scipy import stats as st

from bt.stats import (EULER_GAMMA, block_shuffle_bars, deflated_sharpe,
                      expected_max_sharpe, pbo_cscv, psr)
from bt.synthetic import make_bars


def test_psr_normal_case_matches_hand_formula():
    # skew 0, kurt 3 -> denominator = 1 + SR^2 / 2
    sr, T = 0.1, 252
    expected = st.norm.cdf(sr * np.sqrt(T - 1) / np.sqrt(1 + 0.5 * sr ** 2))
    assert psr(sr, T, 0.0, 3.0) == pytest.approx(expected)


def test_expected_max_sharpe_grows_with_trials():
    vals = [expected_max_sharpe(0.01, n) for n in (2, 10, 100, 1000)]
    assert all(a < b for a, b in zip(vals, vals[1:]))
    n = 1000
    hand = 0.1 * ((1 - EULER_GAMMA) * st.norm.ppf(1 - 1 / n) + EULER_GAMMA * st.norm.ppf(1 - 1 / (n * np.e)))
    assert vals[-1] == pytest.approx(hand)


def test_expected_max_matches_simulation():
    """E[max of N noise Sharpes] should be close to the formula."""
    rng = np.random.default_rng(1)
    T, N, reps = 500, 200, 200
    maxes = []
    for _ in range(reps):
        r = rng.normal(0, 1, (N, T))
        srs = r.mean(1) / r.std(1, ddof=1)
        maxes.append(srs.max())
    formula = expected_max_sharpe(1.0 / T, N)
    assert np.mean(maxes) == pytest.approx(formula, rel=0.05)


def test_dsr_kills_best_of_noise():
    rng = np.random.default_rng(2)
    r = rng.normal(0, 0.01, (300, 1000))  # 300 noise strategies
    srs = r.mean(1) / r.std(1, ddof=1)
    best = r[np.argmax(srs)]
    out = deflated_sharpe(best, srs)
    assert out["psr0"] > 0.95       # looks "significant" naively
    assert out["dsr"] < 0.95        # but not after deflation


def test_pbo_noise_near_half_and_signal_low():
    rng = np.random.default_rng(3)
    noise = rng.normal(0, 1, (1600, 50))
    assert 0.3 < pbo_cscv(noise, n_splits=10)["pbo"] < 0.7
    sig = noise.copy()
    sig[:, 0] += 0.25  # one config with a real, stable edge
    assert pbo_cscv(sig, n_splits=10)["pbo"] < 0.05


def test_block_shuffle_keeps_bar_shapes():
    b = make_bars(n=1000, seed=5)
    o, c, v = block_shuffle_bars(b["open"], b["close"], b["volume"], block=24, rng=np.random.default_rng(0))
    body_a = np.sort(b["close"][1:] / b["open"][1:])
    body_b = np.sort(c[1:] / o[1:])
    np.testing.assert_allclose(body_a, body_b, rtol=1e-12)
    np.testing.assert_allclose(np.sort(v), np.sort(b["volume"]))


def test_block_shuffle_never_moves_bars_across_the_split():
    # Placebo copies must not leak out-of-sample returns into the in-sample period.
    b = make_bars(n=1000, seed=6)
    split = 600
    o, c, _ = block_shuffle_bars(b["open"], b["close"], b["volume"], block=24,
                                 rng=np.random.default_rng(1), split=split)
    body = b["close"][1:] / b["open"][1:]
    body_p = c[1:] / o[1:]
    np.testing.assert_allclose(np.sort(body[:split - 1]), np.sort(body_p[:split - 1]), rtol=1e-12)
    np.testing.assert_allclose(np.sort(body[split - 1:]), np.sort(body_p[split - 1:]), rtol=1e-12)
    # the in-sample total return is unchanged (same bars, different order)
    assert np.isclose(c[split - 1] / c[0], b["close"][split - 1] / b["close"][0], rtol=1e-9)
