# Results

Every number quoted in the talk, the website and the README comes from here. In-sample numbers come from
`results/<run>/is_summary.json` and `experiments/is_tables.py`; out-of-sample numbers come from
`oos_analysis.py` and `oos_details.py`. Frozen at tag: `results-v1`.

## Core Part 1: What Costs Take Away (in-sample)

Source: `make charts` (experiments/is_charts.py) and `python experiments/is_tables.py`, run 2026-11-27.
Sweep results from commits 7e9a47f (crypto) and ba11397 (ETFs). In-sample data only: crypto 2019–2022
(hourly), ETFs 2005–2017 (daily). Sharpe ratios are annualized and, unless stated otherwise, are medians
across every configuration and asset in a strategy family.

### Key Findings

1. **Almost nothing beats simply holding.** Buy-and-hold has a median Sharpe of 1.04 in crypto and 0.53 in
   ETFs. After realistic costs, no strategy family comes close: the best is the moving-average crossover at
   0.53 (crypto long-only) and 0.23 (ETFs).
2. **In crypto, costs remove most of the edge.** The moving-average crossover falls from 1.22 with free
   trading to 0.53 at realistic costs. Every other family turns negative.
3. **Market impact is the largest crypto cost**, about −0.72 Sharpe on its own, twice the 10 bps fee (−0.34).
   Spread (−0.04) and a one-bar delay (−0.04) are small.
4. **H1 holds in crypto:** the most-traded families lose the most (rank correlation +0.90). In ETFs costs
   are too small to separate the families (+0.10).
5. **In ETFs there was little edge to lose.** Every family trails buy-and-hold even when trading is free.

### Compared with Buy-and-Hold

| | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Buy and hold (median asset, no costs) | 1.04 | 1.04 | 0.53 |
| Best family, free trading | 1.22 (moving average) | 0.92 (moving average) | 0.25 (moving average) |
| Best family, headline costs | 0.53 (moving average) | 0.10 (moving average) | 0.23 (moving average) |
| Best single moving-average setting, headline costs | 0.87 (30 / 200) | 0.50 (30 / 200) | 0.39 (45 / 160) |

Headline costs: crypto `fee10_spread+impact_lat1` (10 bps fee per side, 1 bp half-spread, square-root impact,
one bar of delay); ETFs `fee0_spread+impact_lat1` (no fee, one-tick spread, impact, one day of delay).
"Best single setting" is the moving-average cell with the highest median Sharpe across assets, chosen with
hindsight; it still stays below buy-and-hold in every market. Buy-and-hold is shown without costs; it trades
once, so costs would barely change it.

In crypto long-only, the moving-average crossover beats buy-and-hold only while fees stay at or below about
10 bps and there is no spread, impact or delay (1.22, 1.13 and 1.06 at 0, 5 and 10 bps; 0.91 at 20 bps).

### Break-Even Fee (bps per side; fee only, median configuration)

| Family | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Moving-average crossover | > 20 | > 20 | > 20 |
| Time-series momentum | > 20 | 13.4 | 11.1 |
| Donchian breakout | 15.7 | 7.7 | negative at 0 |
| RSI reversion | 8.6 | negative at 0 | 8.1 |
| Z-score reversion | 6.4 | negative at 0 | 9.4 |

"> 20" = still positive at 20 bps; "negative at 0" = loses even with free trading. For reference, Binance's
regular fee is 10 bps; US ETF commissions are 0. Breaking even means a Sharpe above zero, not above buy-and-hold.

### Sharpe Lost to Each Cost

Average change in annualized Sharpe from adding one cost, each strategy compared with itself trading for free.

| Cost | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Fee 5 / 10 / 20 bps | −0.18 / −0.34 / −0.68 | −0.24 / −0.47 / −0.94 | −0.05 / −0.09 / −0.18 |
| Spread | −0.04 | −0.06 | −0.01 |
| Spread + impact | −0.77 | −0.75 | −0.08 |
| Market impact alone (difference of the two rows above) | −0.72 | −0.69 | −0.07 |
| Latency 1 / 2 bars | −0.04 / −0.08 | −0.06 / −0.09 | −0.01 / −0.02 |

Why impact dominates in crypto: each trade is $1M, which is large next to the hourly volume of the smaller
coins, and the square-root law charges for that. Impact grows with the square root of order size, so a $100k
account would pay about a third as much. In ETFs every cost is small: zero commission, one-cent spreads and
very deep markets. The fee's cost grows in proportion to the fee (−0.34 at 10 bps, −0.68 at 20 bps), as
expected when strategies trade at a steady rate.

### H1: Do the Most-Traded Families Lose the Most?

Turnover = times the portfolio is traded per year (median). Sharpe lost = free-trading Sharpe minus headline Sharpe.

Crypto long-only:

| Family | Turnover / yr | Sharpe (free) | Sharpe (headline) | Sharpe lost |
| --- | --- | --- | --- | --- |
| Donchian breakout | 281 | 0.76 | −0.62 | 1.39 |
| Time-series momentum | 242 | 1.14 | −0.11 | 1.27 |
| Z-score reversion | 239 | 0.28 | −1.10 | 1.36 |
| RSI reversion | 199 | 0.48 | −0.90 | 1.24 |
| Moving-average crossover | 106 | 1.22 | 0.53 | 0.71 |

Crypto long-short:

| Family | Turnover / yr | Sharpe (free) | Sharpe (headline) | Sharpe lost |
| --- | --- | --- | --- | --- |
| Donchian breakout | 564 | 0.45 | −1.06 | 1.56 |
| Time-series momentum | 486 | 0.82 | −0.65 | 1.46 |
| Z-score reversion | 391 | −0.09 | −1.57 | 1.21 |
| RSI reversion | 342 | −0.02 | −1.59 | 1.36 |
| Moving-average crossover | 213 | 0.92 | 0.10 | 0.90 |

ETFs:

| Family | Turnover / yr | Sharpe (free) | Sharpe (headline) | Sharpe lost |
| --- | --- | --- | --- | --- |
| Donchian breakout | 16.1 | −0.02 | −0.05 | 0.04 |
| Z-score reversion | 14.5 | 0.12 | 0.01 | 0.08 |
| Time-series momentum | 13.8 | 0.13 | 0.07 | 0.07 |
| RSI reversion | 12.3 | 0.11 | −0.02 | 0.11 |
| Moving-average crossover | 5.7 | 0.25 | 0.23 | 0.02 |

Rank correlation, turnover vs. Sharpe lost: crypto long-only +0.90, crypto long-short +0.90, ETFs +0.10.

**Verdict: H1 holds in crypto and not in ETFs.** In crypto the moving-average crossover trades about half as
often as the other families and is the only one still positive at headline costs. In ETFs strategies trade
roughly 20 times less than in crypto (daily bars, fewer signals), and costs per trade are tiny, so turnover
barely matters.

### Long-Only vs. Long-Short (crypto)

Allowing shorts made every family worse in-sample, even with free trading (moving average 1.22 → 0.92;
momentum 1.14 → 0.82; both mean-reversion families turn negative). It also raised turnover 1.6–2×, because each
signal flip becomes a full reversal from long to short, so costs bite much harder. This is consistent with shorting a
market that rose overall (buy-and-hold Sharpe 1.04); the study did not separate long and short trades. Binance spot can't short anyway, which is why long-only is the headline run.

### Is the Best Configuration an Isolated Peak?

| Run | Best moving-average cell (fast / slow) | Sharpe (headline) | Neighbours' average | Cells within 0.1 of best |
| --- | --- | --- | --- | --- |
| Crypto long-only | 30 / 200 | 0.87 | 0.74 (5 neighbours) | 7 of 90 |
| Crypto long-short | 30 / 200 | 0.50 | 0.37 (5 neighbours) | 6 of 90 |
| ETFs | 45 / 160 | 0.39 | 0.30 (8 neighbours) | 29 of 90 |

Values are medians across assets for each (fast, slow) pair. ETFs show a broad plateau: many settings do
about as well as the best, the more believable pattern. In crypto, long slow windows are consistently better
than short ones (short windows trade the most and lose heavily to costs), but the single best cell sits on the
edge of the grid (200 bars is the longest slow window tested), so the true optimum may lie outside the range
searched. The gap between the best cell and its neighbours (0.09–0.13) is the kind of small, selected
advantage the overfitting tests are designed to discount.

### What This Means for the Out-of-Sample Test

Costs are the first filter, and in crypto they remove most of the in-sample edge: only slow, low-turnover
moving-average rules stay clearly positive. Even those trail buy-and-hold. In ETFs no family had much edge to
begin with. (One interpretation, not a measured result: 2009–2017 was a long bull market, in which a rule that
steps out of the market spends time in cash while prices rise.) So the out-of-sample test starts from a thin
set of candidates. If anything survives, expect slow trend rules. And because even the best in-sample settings
don't beat holding, a strategy that stays positive out of sample still has to be compared with buy-and-hold
before it counts as useful.

### Caveats

- **In-sample only.** These numbers describe the data the strategies were chosen on, so they are optimistic.
  Out-of-sample results, the Deflated Sharpe and PBO come next.
- **Medians, not winners.** Each family's number is its median configuration and asset. Individual
  configurations and assets do better or worse; the overfitting tests deal with the best ones.
- **Buy-and-hold has no costs** and is a median across assets, the same way the strategy numbers are.
- **Order size matters.** All backtests trade $1M; impact would be about a third as large for $100k.
- **Grid edge.** In crypto the best moving-average setting is on the boundary of the tested range.
- **Costs are modeled, not observed.** Fees are real schedules; spreads use a fixed 1 bp (crypto) and one
  price tick (ETFs); impact follows the square-root law with k = 0.5 (see `notes/costs.md`).

## Core Part 2: Overfitting

Source: `make analyze` (experiments/oos_analysis.py), committed before unsealing and run 2026-11-28 after tag
`analysis-plan`; and `make details` (experiments/oos_details.py), written after unsealing and descriptive only
(it adds no stage and changes no threshold). Out-of-sample periods: crypto 2023–2025 (hourly), ETFs
2018–2025 (daily). "Significant" means a probability above 95% that the true Sharpe is above zero (PSR).
The placebo is the same data with prices shuffled in blocks (24 hours / 5 days) inside each period, which
destroys any real signal; its counts are averages per copy (5 copies).

### Key Findings

1. **No strategy survives.** In all three runs, no strategy–asset pair passes the Deflated Sharpe test, so
   the pre-registered funnel ends at zero.
2. **In ETFs, real data looks like noise.** Real prices produce about as many "significant" strategies as
   shuffled ones (406 vs. 332 per copy with free trading; 249 vs. 214 at realistic costs).
3. **Rejecting them was right.** None of the crypto strategies the test rejected (158 long-only, 13
   long-short) beat buy-and-hold out of sample. In ETFs, 15 of 249 did, and the real candidates were positive less often than the placebo's
   (57% vs. 77%).
4. **Crypto trend is real before costs and gone after.** With free trading, each crypto asset's in-sample
   winner kept a median out-of-sample Sharpe of 0.90 (all 10 positive; 5 beat buy-and-hold). At realistic
   costs the same choice falls to 0.07, and none beat buy-and-hold.
5. **Costs make rankings look more persistent than skill does.** The crypto in-sample vs. out-of-sample
   correlation is 0.71 at realistic costs but 0.40 with free trading: expensive strategies lose in both
   periods. ETFs show almost no persistence either way (0.15 and 0.10).

### The Funnel (headline costs)

| Stage | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Tested | 1,820 (placebo 1,820) | 1,820 | 3,640 (placebo 3,640) |
| Significant in-sample, no costs | 986 (placebo 715) | 670 | 406 (placebo 332.2) |
| Still significant at realistic costs | 158 (placebo 19) | 13 | 249 (placebo 213.8) |
| Passes the Deflated Sharpe test | 0 (placebo 0) | 0 | 0 (placebo 0.8) |
| Positive out of sample | 0 (placebo 0) | 0 | 0 (placebo 0.8) |

The long-short run has no placebo. Charts: `figures/<run>_funnel.png`. The ETF placebo's 0.8 per copy means
4 false passes across 5 copies: luck occasionally gets through, which is what the test allows for.

Out of sample, the median configuration at headline costs had a Sharpe of −0.15 (crypto long-only), −0.40
(crypto long-short) and 0.01 (ETFs), against buy-and-hold at 0.77, 0.77 and 0.56 (median asset, no costs).

### What the Deflated Sharpe Test Rejected (descriptive, after unsealing)

Because nothing passed, the last funnel stages are empty. This table shows how the strategies that reached
the test (significant with free trading and at realistic costs) did out of sample.

| | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Candidates rejected by the test | 158 | 13 | 249 |
| Positive out of sample | 103 (65%) | 11 (85%) | 143 (57%) |
| Beat buy-and-hold out of sample | 0 | 0 | 15 (6%) |
| Median Sharpe, in-sample → out of sample | 1.04 → 0.17 | 0.95 → 0.15 | 0.55 → 0.04 |
| Placebo at the same stage: positive out of sample | 10.8 of 19 (57%) | — | 165 of 213.8 (77%) |
| Buy-and-hold, out of sample | 0.77 | 0.77 | 0.56 |

Almost all candidates are slow trend rules: moving-average crossovers (144 of 158; 11 of 13; 202 of 249)
and time-series momentum.

### The Naive Researcher: Pick Each Asset's In-Sample Winner

Medians across assets (10 crypto, 20 ETFs). The luck benchmark is the best Sharpe expected from luck alone,
given the number of effective (de-duplicated) trials; the Deflated Sharpe test passes above 0.95.

| | In-sample → out of sample | Positive | Beat buy-and-hold | Luck benchmark (effective trials) | Deflated Sharpe |
| --- | --- | --- | --- | --- | --- |
| Crypto long-only, free trading | 1.77 → 0.90 | 10 of 10 | 5 of 10 | 0.37 (3) | 0.993 |
| Crypto long-only, headline costs | 1.03 → 0.07 | 5 of 10 | 0 of 10 | 0.88 (4) | 0.553 |
| Crypto long-short, free trading | 1.67 → 0.72 | 9 of 10 | 6 of 10 | 1.14 (10.5) | 0.834 |
| Crypto long-short, headline costs | 0.68 → −0.25 | 4 of 10 | 0 of 10 | 2.55 (11) | 0.000 |
| ETFs, free trading | 0.69 → −0.02 | 9 of 20 | 2 of 20 | 0.48 (11) | 0.745 |
| ETFs, headline costs | 0.60 → 0.03 | 11 of 20 | 3 of 20 | 0.54 (10) | 0.650 |

With free trading, the crypto long-only winners would pass the test (0.993) and they did hold up out of
sample. At realistic costs the same rule of thumb picks strategies that barely break even.

### Does In-Sample Rank Carry Over?

| | Crypto long-only | Crypto long-short | ETFs |
| --- | --- | --- | --- |
| Slope, out-of-sample on in-sample Sharpe (headline / free trading) | 0.57 / 0.33 | 0.74 / 0.38 | 0.14 / 0.12 |
| Correlation (headline / free trading) | 0.71 / 0.40 | 0.74 / 0.52 | 0.15 / 0.10 |
| Probability of backtest overfitting, PBO (headline / free trading) | 0.16 / 0.43 | 0.23 / 0.30 | 0.47 / 0.52 |

A slope of 1 would mean in-sample Sharpe carries over in full; 0 means it predicts nothing. PBO is the
chance that the in-sample best ranks in the bottom half on unseen data (CSCV within the in-sample period);
0.5 is a coin flip. In crypto, costs raise both persistence and the apparent reliability of the in-sample
ranking, because a high-turnover strategy pays the most in both periods. Some persistence remains with free
trading (correlation 0.40), consistent with the trend found above. ETFs are close to a coin flip either way.
Charts: `figures/<run>_shrinkage.png`.

The long-short chart has a flat row at an out-of-sample Sharpe of exactly 0: 150 of 1,820 pairs at headline
costs (101 z-score, 48 RSI, 1 moving average) lost everything in-sample (maximum drawdown 100%). Under the
limited-liability rule they stop trading, so their out-of-sample Sharpe is 0 by construction.

### What This Means

The answer to "how many profitable-looking strategies survive?" is none, and the descriptive checks show this
is not just a strict test: nothing the test rejected in crypto beat buy-and-hold, and in ETFs the real
candidates did no better than ones found in shuffled prices. Crypto has a real trend signal, visible with free
trading, but realistic costs consume it. For an investor in these markets, buying and holding beat every
rule-based strategy tested here.

### Caveats

- **At realistic costs the test's bar rises partly because of the costs.** The luck benchmark grows with how
  spread out the strategies' Sharpes are, and costs spread them out (crypto long-short: 2.55 at headline costs
  vs. 1.14 free). So "0 passed" overstates how strict luck alone would make the test. The descriptive checks
  above are what show the rejections were right.
- **The descriptive checks were written after unsealing.** They add no stage or threshold and leave every
  pre-registered number unchanged; the commit history shows the order.
- **One out-of-sample period per market.** Crypto 2023–2025 and ETFs 2018–2025 are single windows; the
  walk-forward and bootstrap checks test how much the answer depends on them.
- **Buy-and-hold has no costs**, and all comparisons are medians across assets.
- **Five placebo copies.** The placebo averages are rough (for example, 0.8 is 4 passes in 5 copies).

## Modeling Question

- Test AUC by rung:
- Filter test (top 10% picks, out-of-sample Sharpe): model ___ vs. in-sample Sharpe ___

## Engine

- Benchmark on my laptop (5,000 bars, all costs on): Python 118.6 ms vs. C++ 1.04 ms per backtest, 114× faster;
  all 182 configurations on one asset in 0.133 s. Engine v2: ___
- Full study: 262,080 backtests (182 configurations × 36 cost settings × 40 asset-runs) plus 54,600 on placebo
  data, in about 42 minutes on my laptop.
