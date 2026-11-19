"""Multiple-Testing Statistics for Backtests.

* Probabilistic Sharpe Ratio (PSR) and Deflated Sharpe Ratio (DSR):
  Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio", J. Portfolio Management.
* Probability of Backtest Overfitting (PBO) via combinatorially symmetric
  cross-validation (CSCV): Bailey, Borwein, Lopez de Prado & Zhu (2017),
  "The Probability of Backtest Overfitting", J. Computational Finance.

All Sharpe ratios inside this module are PER PERIOD (not annualized), because
that is how the formulas are written.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy import stats as st

EULER_GAMMA = 0.5772156649015329


def sharpe_per_period(r: np.ndarray, axis: int = -1) -> np.ndarray:
    r = np.asarray(r, dtype=float)
    sd = r.std(axis=axis, ddof=1)
    mu = r.mean(axis=axis)
    return np.divide(mu, sd, out=np.zeros_like(mu, dtype=float), where=sd > 0)


def psr(sr: float, T: int, skew: float, kurt: float, sr_star: float = 0.0) -> float:
    """P(true SR > sr_star). `kurt` is ordinary (non-excess) kurtosis; normal = 3."""
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return float(st.norm.cdf((sr - sr_star) * np.sqrt(T - 1) / np.sqrt(denom)))


def expected_max_sharpe(var_sr: float, n_trials: int) -> float:
    """Expected maximum of n_trials Sharpe estimates when every true SR is 0."""
    if n_trials < 2:
        return 0.0
    z1 = st.norm.ppf(1.0 - 1.0 / n_trials)
    z2 = st.norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var_sr) * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(selected_returns: np.ndarray, trial_sharpes: np.ndarray,
                    n_trials: int | None = None) -> dict:
    """DSR of the selected strategy, given the per-period Sharpes of ALL trials tried."""
    r = np.asarray(selected_returns, dtype=float)
    trial_sharpes = np.asarray(trial_sharpes, dtype=float)
    N = int(n_trials or len(trial_sharpes))
    sr = float(sharpe_per_period(r))
    sr0 = expected_max_sharpe(float(np.var(trial_sharpes, ddof=1)), N)
    skew = float(st.skew(r))
    kurt = float(st.kurtosis(r, fisher=False))
    return {"sr": sr, "sr0": sr0, "n_trials": N,
            "dsr": psr(sr, len(r), skew, kurt, sr_star=sr0),
            "psr0": psr(sr, len(r), skew, kurt, sr_star=0.0)}


def psr_vec(sr: np.ndarray, T: int, skew: np.ndarray, kurt: np.ndarray,
            sr_star: float = 0.0) -> np.ndarray:
    """psr() for many strategies at once (arrays in, array out)."""
    sr, skew, kurt = (np.asarray(x, dtype=float) for x in (sr, skew, kurt))
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    z = np.divide((sr - sr_star) * np.sqrt(T - 1), np.sqrt(np.where(denom > 0, denom, np.nan)))
    return st.norm.cdf(z)


def effective_trials(returns: np.ndarray, max_corr_distance: float = 0.5) -> dict:
    """Group near-duplicate strategies so they count as one trial.

    returns: array (N, T), one row per strategy. Strategies are clustered by
    correlation (distance = 1 - correlation, average linkage); two strategies
    whose returns correlate above 1 - max_corr_distance (0.5 by default) end up
    together. Each cluster's Sharpe is that of its members' equal-weight average.
    Following Lopez de Prado's recommendation, the number of clusters is the
    effective number of independent trials for the Deflated Sharpe Ratio.
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    R = np.asarray(returns, dtype=float)
    N = R.shape[0]
    if N < 2:
        return {"n_eff": N, "labels": np.ones(N, dtype=int), "cluster_sharpes": sharpe_per_period(R)}
    with np.errstate(invalid="ignore", divide="ignore"):
        C = np.corrcoef(R)
    C = np.nan_to_num(C, nan=0.0)            # strategies that never trade correlate with nothing
    np.fill_diagonal(C, 1.0)
    D = np.clip(1.0 - C, 0.0, 2.0)
    labels = fcluster(linkage(squareform(D, checks=False), method="average"),
                      t=max_corr_distance, criterion="distance")
    ids = np.unique(labels)
    cluster_sr = np.array([sharpe_per_period(R[labels == k].mean(0)) for k in ids])
    return {"n_eff": len(ids), "labels": labels, "cluster_sharpes": cluster_sr}


def deflated_sharpe_clustered(returns: np.ndarray, selected: int,
                              max_corr_distance: float = 0.5) -> dict:
    """DSR of strategy `selected` (a row of `returns`), with the luck benchmark
    SR0 built from clusters rather than raw configurations."""
    R = np.asarray(returns, dtype=float)
    eff = effective_trials(R, max_corr_distance)
    var = float(np.var(eff["cluster_sharpes"], ddof=1)) if eff["n_eff"] > 1 else 0.0
    sr0 = expected_max_sharpe(var, eff["n_eff"])
    r = R[selected]
    sr = float(sharpe_per_period(r))
    sk, ku = float(st.skew(r)), float(st.kurtosis(r, fisher=False))
    return {"sr": sr, "sr0": sr0, "n_trials": R.shape[0], "n_eff": eff["n_eff"],
            "dsr": psr(sr, len(r), sk, ku, sr0), "psr0": psr(sr, len(r), sk, ku, 0.0)}


def pbo_cscv(returns: np.ndarray, n_splits: int = 16, max_combos: int | None = None,
             rng: np.random.Generator | None = None) -> dict:
    """PBO by CSCV.

    returns: array (T, N) -- per-period returns of N candidate configurations.
    The T rows are cut into n_splits contiguous blocks; every way of choosing
    half the blocks as in-sample is evaluated (C(16, 8) = 12,870 by default).
    For each, the in-sample-best config's out-of-sample relative rank w is
    turned into a logit; PBO = share of logits <= 0 (winner fell into the
    bottom half out of sample).
    """
    M = np.asarray(returns, dtype=float)
    T, N = M.shape
    if n_splits % 2:
        raise ValueError("n_splits must be even")
    blocks = np.array_split(np.arange(T), n_splits)
    combos = list(combinations(range(n_splits), n_splits // 2))
    if max_combos is not None and len(combos) > max_combos:
        rng = rng or np.random.default_rng(0)
        idx = rng.choice(len(combos), size=max_combos, replace=False)
        combos = [combos[i] for i in idx]

    # Per-block sums make each split's Sharpe cheap to assemble.
    sums = np.array([M[b].sum(0) for b in blocks])          # (S, N)
    sq = np.array([(M[b] ** 2).sum(0) for b in blocks])      # (S, N)
    cnt = np.array([len(b) for b in blocks])                 # (S,)

    def sr_from(idx):
        n = cnt[list(idx)].sum()
        s = sums[list(idx)].sum(0)
        q = sq[list(idx)].sum(0)
        mu = s / n
        var = (q - n * mu ** 2) / (n - 1)
        sd = np.sqrt(np.maximum(var, 0))
        return np.divide(mu, sd, out=np.zeros(N), where=sd > 0)

    logits, is_best, oos_of_best = [], [], []
    all_idx = set(range(n_splits))
    for c in combos:
        sr_is = sr_from(c)
        sr_oos = sr_from(tuple(sorted(all_idx - set(c))))
        best = int(np.argmax(sr_is))
        rank = st.rankdata(sr_oos)[best] / (N + 1)  # relative rank in (0, 1)
        logits.append(np.log(rank / (1 - rank)))
        is_best.append(sr_is[best])
        oos_of_best.append(sr_oos[best])
    logits = np.array(logits)
    return {"pbo": float(np.mean(logits <= 0)), "logits": logits,
            "is_sr_best": np.array(is_best), "oos_sr_best": np.array(oos_of_best),
            "n_combos": len(combos)}


def block_shuffle_bars(open_, close, volume, block: int = 24, rng=None, split: int | None = None):
    """Placebo data: shuffle blocks of bars, keeping each bar's shape.

    Each bar is stored relative to the previous close (gap = open/prev_close,
    body = close/open). Blocks of `block` bars are permuted and the price path
    is rebuilt, so volatility and intrabar structure survive but the time order
    (and any real predictability) is destroyed.

    `split` is the index of the first out-of-sample bar. When given, blocks are
    shuffled only WITHIN the in-sample part and within the out-of-sample part, so
    no out-of-sample return is ever moved into the placebo's in-sample period
    (that would leak sealed data and shift the in-sample drift).
    """
    rng = rng or np.random.default_rng()
    open_, close, volume = map(np.asarray, (open_, close, volume))
    gap = open_[1:] / close[:-1]
    body = close[1:] / open_[1:]
    n = len(gap)
    # Bar i + 1 is stored at index i, so out-of-sample bars start at index split - 1.
    cut = n if split is None else min(max(split - 1, 0), n)
    order = []
    for lo, hi in ((0, cut), (cut, n)):
        starts = np.arange(lo, hi, block)
        for s in rng.permutation(starts):
            order.append(np.arange(s, min(s + block, hi)))
    order = np.concatenate(order)
    g, b, v = gap[order], body[order], volume[1:][order]
    o, c = np.empty(n + 1), np.empty(n + 1)
    o[0], c[0] = open_[0], close[0]
    for i in range(n):
        o[i + 1] = c[i] * g[i]
        c[i + 1] = o[i + 1] * b[i]
    return o, c, np.concatenate([[volume[0]], v])
