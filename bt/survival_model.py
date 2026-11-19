"""Modeling Question: predict which in-sample 'winners' survive out of sample.

One row per (asset, config). Features come ONLY from in-sample results (across
all realism settings); the label comes from the sealed out-of-sample file.

    survive = 1  if out-of-sample net Sharpe > 0 under the target setting

Model ladder (each rung must beat the one before to earn its place):
    0. naive          score = in-sample Sharpe (what most people do)
    1. logistic       standardized features, L2
    2. boosted trees  sklearn HistGradientBoosting
(3. a 1D CNN over the in-sample return path is a later, optional rung.)

Validation: GroupKFold by asset, so a model never sees the test asset at all.
Reported: AUC, Spearman(score, OOS Sharpe), train-test AUC gap, and the
"filter test": in each held-out asset, trade the top 10% by score and report
their average OOS Sharpe vs. the top 10% by in-sample Sharpe.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

NUMERIC = ["is_sharpe", "is_psr0", "is_dsr", "log_turnover", "log_trades", "max_dd",
           "cost_slope", "neighbor_sharpe", "neighbor_gap"]


def _params(config: str) -> np.ndarray:
    """Parse a config name like 'ma_cross(20, 100)' into its numbers [20, 100]."""
    inside = config[config.index("(") + 1: config.rindex(")")]
    return np.array([float(x) for x in inside.split(",") if x.strip()])


def neighbor_stats(df: pd.DataFrame, k: int = 4) -> pd.DataFrame:
    """For each config, the mean in-sample Sharpe of its k nearest neighbours in
    parameter space (same asset, same family, params scaled to [0, 1]).
    An isolated peak (high Sharpe, weak neighbours) is a classic overfitting sign."""
    out = []
    for (_, _), g in df.groupby(["asset", "family"]):
        P = np.vstack([_params(c) for c in g.config])
        rng = P.max(0) - P.min(0)
        P = (P - P.min(0)) / np.where(rng > 0, rng, 1)
        D = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)
        np.fill_diagonal(D, np.inf)
        idx = np.argsort(D, axis=1)[:, : min(k, len(g) - 1)]
        s = g.is_sharpe.to_numpy()
        nb = s[idx].mean(1) if idx.shape[1] else np.full(len(g), np.nan)
        out.append(pd.DataFrame({"asset": g.asset.values, "config": g.config.values,
                                 "neighbor_sharpe": nb, "neighbor_gap": s - nb}))
    return pd.concat(out)


def build_dataset(sweep_is: pd.DataFrame, oos: pd.DataFrame, target_setting: str,
                  low_cost_setting: str, high_cost_setting: str) -> pd.DataFrame:
    """Build the model's table: one row per (asset, config).

    sweep_is          in-sample rows from run_sweep.py (any oos_ columns are dropped)
    oos               asset, setting, config, oos_sharpe (from the SEALED file)
    target_setting    the cost setting whose out-of-sample result defines "survived"
    low/high_setting  two cost settings; the Sharpe difference between them is the
                      "cost slope" feature (how badly costs hurt this strategy)
    """
    key = ["asset", "config"]
    sweep_is = sweep_is[~sweep_is.asset.str.contains("__placebo")]   # placebo copies are not real assets
    base = sweep_is[sweep_is.setting == target_setting].copy()
    base = base.drop(columns=[c for c in base.columns if c.startswith("oos_")])  # never as features
    lo = sweep_is[sweep_is.setting == low_cost_setting].set_index(key).is_sharpe
    hi = sweep_is[sweep_is.setting == high_cost_setting].set_index(key).is_sharpe
    slope = (hi - lo).rename("cost_slope").reset_index()
    base = base.merge(slope, on=key).merge(neighbor_stats(base), on=key)
    base["log_turnover"] = np.log1p(base.ann_turnover)
    base["log_trades"] = np.log1p(base.n_trades)
    y = oos[oos.setting == target_setting][key + ["oos_sharpe"]]
    base = base.merge(y, on=key)
    base["survive"] = (base.oos_sharpe > 0).astype(int)
    return base


def _X(df: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix: the numeric features plus one 0/1 column per strategy family."""
    X = df[NUMERIC].copy()
    for f in sorted(df.family.unique()):
        X[f"fam_{f}"] = (df.family == f).astype(float)
    return X.fillna(0.0)


# The ladder. None = no training: the score is simply the in-sample Sharpe.
MODELS = {
    "naive_is_sharpe": None,
    "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)),
    "boosted_trees": lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
                                                            max_iter=200, l2_regularization=1.0),
}


def evaluate(data: pd.DataFrame, n_splits: int | None = None, top_frac: float = 0.1) -> pd.DataFrame:
    """Score every model with grouped cross-validation and return one row per model.

    GroupKFold by asset: each fold holds out whole assets, so a model is always
    tested on markets it never saw (no leakage between configs of one asset).
    Every row gets an out-of-fold score; the metrics are computed on those scores.
    """
    X, y, groups = _X(data), data.survive.to_numpy(), data.asset.to_numpy()
    n_splits = n_splits or min(5, len(np.unique(groups)))
    rows = []
    for name, make in MODELS.items():
        score = np.empty(len(data))
        train_auc = []
        for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
            if make is None:
                score[te] = data.is_sharpe.to_numpy()[te]
                continue
            if len(np.unique(y[tr])) < 2:
                # Every training row has the same label (e.g. nothing survived), so there is
                # nothing to learn: predict the training base rate and move on.
                score[te] = y[tr].mean()
                continue
            m = make().fit(X.iloc[tr], y[tr])
            score[te] = m.predict_proba(X.iloc[te])[:, 1]
            if len(np.unique(y[tr])) > 1:
                train_auc.append(roc_auc_score(y[tr], m.predict_proba(X.iloc[tr])[:, 1]))
        d = data.assign(score=score)
        picks = pd.concat([g.nlargest(max(1, int(len(g) * top_frac)), "score")
                           for _, g in d.groupby("asset")])
        test_auc = roc_auc_score(y, score) if len(np.unique(y)) > 1 else np.nan
        rows.append({
            "model": name,
            "test_auc": test_auc,
            "train_auc": float(np.mean(train_auc)) if train_auc else np.nan,
            "spearman_vs_oos": spearmanr(score, data.oos_sharpe).statistic,
            f"top{int(top_frac * 100)}pct_hit_rate": picks.survive.mean(),
            f"top{int(top_frac * 100)}pct_oos_sharpe": picks.oos_sharpe.mean(),
        })
    out = pd.DataFrame(rows).set_index("model")
    out["train_test_gap"] = out.train_auc - out.test_auc
    return out


def log_experiment(path: Path, name: str, results: pd.DataFrame, notes: str = "", **params):
    """Append one line per run, so the deck's 'what helped / what didn't' slide writes itself."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"time": time.strftime("%Y-%m-%d %H:%M"), "name": name, "notes": notes, "params": params,
           "results": json.loads(results.round(4).to_json(orient="index"))}
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
