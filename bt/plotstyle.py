"""One chart style for every figure, matching the slides.

The five family colours were checked with a colour-vision-deficiency validator
(adjacent pairs stay distinguishable); lines also carry direct text labels, so
colour is never the only way to tell them apart.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG, INK, QUIET, GRID = "#F6F5F0", "#14213D", "#5A6478", "#DEDBD2"
BLUE, ORANGE = "#2a78d6", "#eb6834"
FAMILY_COLORS = {"ma_cross": "#2a78d6", "tsmom": "#eb6834", "donchian": "#1baf7a",
                 "rsi_mr": "#eda100", "zscore_mr": "#e87ba4"}
FAMILY_LABELS = {"ma_cross": "Moving-avg crossover", "tsmom": "Time-series momentum",
                 "donchian": "Donchian breakout", "rsi_mr": "RSI reversion",
                 "zscore_mr": "Z-score reversion"}


def figure(w: float = 10.4, h: float = 5.6):
    plt.rcParams.update({"font.size": 14, "axes.edgecolor": QUIET, "axes.labelcolor": QUIET,
                         "xtick.color": QUIET, "ytick.color": QUIET})
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return fig, ax


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
