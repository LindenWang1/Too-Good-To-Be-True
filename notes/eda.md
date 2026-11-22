# Baseline Analysis (In-Sample Only)

What the data looks like before any strategy is tuned, and what that predicts for the rest of the study. Everything here uses **in-sample data only** (Crypto: hourly, 2019-2022; ETFs: daily, 2005-2017), so the out-of-sample period stays untouched.

Source: `make eda` -> `experiments/eda.py`, run 2026-11-21. Outputs per market in `results/eda/<market>/`: `return_stats.csv`, `return_autocorrelation.png`, `zero_cost_equity.png`.

## Key Findings

| # | Question | Answer | Why it Matters Later |
| --- | --- | --- | --- |
| 1 | How fat-tailed are returns? | Very. Extreme moves happen far more often than a bell curve allows, especially in crypto, and big moves are more often down than up. | Raw Sharpe ratios overstate how sure we can be, so the study uses the probabilistic and deflated Sharpe ratios, which correct for skew and fat tails. |
| 2 | Is volatility clustered? | Yes, strongly, in every asset: a big move today makes another big move tomorrow much more likely. | Supports the volatility-scaled impact model, and means resampling must use blocks of time (block bootstrap, block-shuffled placebo), not single bars. |
| 3 | Momentum or mean reversion? | Almost neither. Next-bar returns lean very slightly toward reversal; no lag shows reliable momentum. | Before any backtest, we should expect little real edge. Most in-sample "winners" will likely be luck, which is exactly what the later steps test. |
| 4 | How good do strategies look with zero costs? | Mostly worse than buy-and-hold, but a few curves look excellent (ADA: moving-average cross ≈ 8× vs. ≈ 6×, with a much smaller crash). | These attractive curves are the starting point of the story: the cost, multiple-testing and out-of-sample steps check whether they are real. |

## How to Read the Numbers

- **Excess Kurtosis** measures fat tails. A normal (bell-curve) distribution has 0; BTC's 46 means extreme hours are vastly more common than a bell curve predicts.
- **Skew** measures asymmetry. Negative means the largest moves tend to be crashes rather than spikes.
- **Autocorrelation at Lag k** is the correlation between a return and the return k bars later. Above 0 suggests momentum; below 0, mean reversion.
- **Noise Band:** with N bars, pure noise produces autocorrelations within about ±1.96/√N 95% of the time. That's ±0.010 for crypto (35,000 bars), ±0.014 for AVAX and SOL, ±0.034 for ETFs (3,272 bars) and ±0.083 for XLRE. Values inside the band are indistinguishable from zero.

## Q1. How Fat-Tailed are Returns?

| | Crypto (10 coins, hourly) | ETFs (20, daily) |
| --- | --- | --- |
| Annualized volatility | 73% (BTC) to 159% (AVAX) | 7% (IEF) to 33% (SLV) |
| Skew | −1.02 (ETH) to +2.49 (DOGE); 6 of 10 negative | −1.01 (SLV) to +0.30 (DIA); 15 of 20 negative |
| Excess kurtosis | 14 (SOL) to 107 (DOGE) | 1.9 (TLT) to 17.5 (DIA) |

- Every asset is fat-tailed. Crypto is the more extreme market on every measure, with volatility roughly 5× that of stock ETFs.
- DOGE is the outlier: positive skew and the most extreme tails, driven by a few huge pumps (see `notes/data.md`, Extreme Moves).
- Bonds (TLT, IEF) are closest to normal.

## Q2. Is Volatility Clustered?

Autocorrelation of the *size* of returns (|return|), all far outside the noise band:

| | Lag 1 | Longer lag | Strongest / weakest |
| --- | --- | --- | --- |
| Crypto | 0.26 – 0.45 | still 0.17 – 0.35 at 6 hours | DOGE 0.45 / ETH 0.26 |
| ETFs | 0.12 – 0.43 | still 0.08 – 0.44 at 5 days | XLF 0.43 / GLD 0.12 |

Calm and volatile periods persist. For stock ETFs, clustering is often *stronger* at 2 days than at 1 (SPY 0.30 → 0.41, DIA 0.33 → 0.43). Gold and bonds cluster least.

**What this means for the placebo.** The placebo (`block_shuffle_bars` in `bt/stats.py`) cuts each price series into blocks of 24 hours (crypto) or 5 days (ETFs) and shuffles the blocks. It does this separately within the in-sample and out-of-sample periods, and keeps each bar's overnight gap and intraday move together.
- **Kept:** volatility clustering and any pattern shorter than a block.
- **Removed:** anything longer, including the 24-hour crypto reversal (Q3) and all multi-day trends.

So the placebo shows how good strategies look on data with the same short-term texture but no longer-term structure: a fair luck baseline for trend-following rules. Short-horizon mean-reversion rules could still find some real structure inside the blocks.

## Q3. Momentum or Mean Reversion?

| | Lag 1 | Longer lags |
| --- | --- | --- |
| ETFs (daily) | Negative in 18 of 20, beyond the noise band for 15. Largest: EEM, EFA, XLF −0.11, DIA −0.09. Inside the band: GLD, SLV, XLB, XLY, XLRE. | 5, 21 and 63 days: mostly small and negative. |
| Crypto (hourly) | Negative in all 10, beyond the band for 9 (not ETH). Range −0.007 to −0.05. | 24 hours: negative in all 10 (−0.03 to −0.09, DOGE strongest), the clearest pattern in the data. 168 hours (1 week): about zero. |

- **The pattern is real but tiny.** An autocorrelation of −0.05 means the previous bar explains about 0.25% of the next bar's variation (−0.05² = 0.0025). That is far too little to profit from once costs apply.
- **Caveat:** single-lag autocorrelation can miss slow trends. A 10-month moving-average rule, for example, works mainly by stepping aside during long declines, which a lag-1 number can't show. So this is a prior, not a verdict; the Faber case study (`notes/case_study.md`) tests a slow trend rule directly.

## Q4. How Good do Strategies Look with Zero Costs?

`zero_cost_equity.png` compares one default configuration per strategy family with buy-and-hold, for the first asset in each market (ADA, DIA), in-sample and with no costs. Values are read off log-scale charts, so they are approximate.

| Strategy (default parameters) | ADA (crypto, 2019–2022) | DIA (ETF, 2005–2017) |
| --- | --- | --- |
| Buy-and-hold | ≈ 6× (peaked near 70×, then fell about 90%) | ≈ 3.1× (fell about 50% in 2008–09) |
| tsmom(120, 5): time-series momentum | ≈ 3.3× | ≈ 2.4× (rose during the 2008 crash) |
| ma_cross(20, 100): moving-average cross | ≈ 8× | ≈ 1.4× |
| donchian(55, 20): channel breakout | ≈ 1.0× | ≈ 0.9× |
| zscore_mr(40, 2.0, 0.5): z-score mean reversion | ≈ 0.02× | ≈ 1.25× |
| rsi_mr(14, 30, 70): RSI mean reversion | ≈ 0.01× | ≈ 0.9× |

- **Trend-following looks best.** Its main appeal is avoiding crashes rather than higher returns: tsmom rose while DIA fell in 2008. ma_cross on ADA is the one curve that beats buy-and-hold outright, and it is the "too good to be true" hook.
- **Mean reversion fails even before costs on ADA (−98% to −99%).** Betting on reversals through crypto's strong 2020–21 trends was costly. The small negative autocorrelations in Q3 are not enough to rescue it.
- **On DIA, nothing beats buy-and-hold** over 2005–2017.
- **These are default parameters, not the best of each grid.** The sweep will find configurations that look far better in-sample. How much of that improvement is just selection luck is what the deflated Sharpe ratio, PBO and the placebo measure.
- **One asset per market.** These charts illustrate; the full sweep covers every asset.

## Next

Baseline questions 5 (turnover by family, the direct test of H1) and 6 (is the best configuration an isolated peak?) come from the first in-sample sweep and go in `notes/results.md`.