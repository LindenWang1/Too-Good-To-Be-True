# External Case Study: Faber's 10-Month Moving-Average Rule (pre-registered)

**Written on 2026-11-21, before any case-study code was run.** The commit date of this file is the proof. Nothing above the Verdict section changes after results are seen.

## Why this Test

The main study asks whether strategies chosen on past data survive new data. This case study asks the same question about someone else's idea. Mebane Faber published a simple trend rule in 2006–2007 that is still widely cited, so every year since then is data he could not have fitted. Writing the rule and the pass/fail criteria down first makes it an honest test: the result can't be reinterpreted after the fact.

## The Rule

Source: Mebane Faber, *A Quantitative Approach to Tactical Asset Allocation* (working paper 2006; *Journal of Wealth Management*, 2007).

1. At each month-end, compare the ETF's close with the average of its last 10 month-end closes (10-month simple moving average).
2. Close above the average: hold the ETF for the next month. Close below: hold cash.
3. Trade at the open of the next month's first trading day.

Implementation Choices:
- Long-only, and each ETF is tested on its own (no portfolio weighting).
- Adjusted prices, so dividends are included (total return, as in the paper).
- Cash earns 0%. Faber credited T-bill interest to cash, so this slightly understates the rule. The verdict will mention it, but it won't be "corrected" afterwards.

## The Claim being Tested

Faber reported returns close to buy-and-hold, with lower volatility and much smaller drawdowns.

## Test Design

| | |
| --- | --- |
| Period scored | 2008-01-01 to 2025-12-31, all after publication. Earlier data is used only to warm up the 10-month average. |
| Assets | SPY (main case); EFA (foreign stocks), EEM (emerging markets), TLT and IEF (bonds), GLD (gold) |
| Costs | ETF headline setting `fee0_spread+impact_lat1`, with each ETF's own spread estimate |
| Benchmark | Buy-and-hold of the same ETF over the same period |
| Metrics | Annualized return, annualized volatility, Sharpe ratio, maximum drawdown, number of trades |
| Variant | A daily version: hold when the close is above its 200-day moving average. Reported alongside the main rule, not part of pass/fail. |

**Clarification (2026-11-22, before any case-study code was run).** The rule trades at the open of the next month's first trading day. From the headline cost setting `fee0_spread+impact_lat1`, the main result uses the fee, spread and impact only: its one-bar latency would be a full month on month bars. A one-day delay (filling on the month's second trading day) is reported as a robustness line, not part of pass/fail.

**Clarification (2026-11-27, before any case-study code was run).** The main study's spread model changed (see `notes/costs.md`): each ETF's spread is now one price tick at its median price before 2008, instead of the Corwin–Schultz estimate. "Each ETF's own spread estimate" above means this. The BTC case uses the crypto model (1 bp).

**Clarification (2026-11-28, before any case-study code was run).** The scored period starts 2008-01-01, so returns are measured from the last close of 2007. A code review found that the script started from the first bar of 2008, which on month bars would have dropped January 2008; this was fixed before the first run.

## Pass Criteria (Decided Now)

1. **Drawdown, SPY:** the rule's maximum drawdown is at most half of buy-and-hold's.
2. **Risk-adjusted return, SPY:** the rule's Sharpe ratio is no more than 0.1 below buy-and-hold's.
3. **Breadth, all 6 ETFs:** the rule has a smaller maximum drawdown than buy-and-hold on at least 4 of the 6.

| Verdict | Condition |
| --- | --- |
| Holds up | 1, 2 and 3 all pass |
| Partly holds up | 1 and 3 pass, 2 fails (safer, but at a cost in return per unit of risk) |
| Doesn't hold up | 1 or 3 fails |

## What I Will Not Do

- Change the 10-month window, the month-end timing, the cash rule, or the cost setting.
- Add or drop assets, or change the test period.
- Promote the daily variant to the main result if it looks better.
- Add or change criteria after seeing results.

## Optional Second Case: BTC Golden Cross

| | |
| --- | --- |
| Rule | Daily BTC closes (from the hourly data). Hold BTC when the 50-day moving average is above the 200-day; otherwise hold cash. Long-only. `StrategyConfig(MA_CROSS, (50, 200))` |
| Costs | Binance 10 bps fee (crypto headline setting `fee10_spread+impact_lat1`) |
| Period scored | 2023-01-01 to 2025-12-31 (the crypto out-of-sample period) |
| Pass | Maximum drawdown at most half of buy-and-hold's, and Sharpe no more than 0.1 below buy-and-hold's |
| Fixed | No changes to the 50/200 windows or the period after seeing results |

## Verdict

*Written 2026-11-28, after the run (`python experiments/case_study.py --btc`). Results in `results/case_study/`;
charts in `figures/case_study_*.png`.*

**Faber's rule holds up, by the pre-registered criteria** (main rule: monthly, fill day 1).

| Criterion | Rule | Buy-and-hold | Result |
| --- | --- | --- | --- |
| 1. SPY maximum drawdown at most half of buy-and-hold's | 23.1% | 48.2% (limit 24.1%) | Pass, narrowly |
| 2. SPY Sharpe no more than 0.1 below buy-and-hold's | 0.76 | 0.75 | Pass |
| 3. Smaller drawdown than buy-and-hold on at least 4 of 6 ETFs | 6 of 6 | | Pass |

| ETF | Return a year (rule / hold) | Sharpe (rule / hold) | Maximum drawdown (rule / hold) | Trades |
| --- | --- | --- | --- | --- |
| SPY | 8.1% / 11.0% | 0.76 / 0.75 | 23.1% / 48.2% | 29 |
| EFA | 3.7% / 4.2% | 0.38 / 0.32 | 30.6% / 54.4% | 33 |
| EEM | 2.9% / 2.7% | 0.28 / 0.23 | 42.1% / 56.8% | 38 |
| TLT | 1.9% / 2.7% | 0.22 / 0.25 | 26.4% / 47.6% | 40 |
| IEF | 2.1% / 3.0% | 0.41 / 0.47 | 15.9% / 23.2% | 38 |
| GLD | 6.4% / 9.1% | 0.53 / 0.60 | 38.4% / 42.9% | 34 |

**Monthly vs. daily.** The daily 200-day version and the fill one day later tell the same story (SPY drawdown
22.5% vs. 52.3% on daily closes; 23.8% with the later fill), so the verdict doesn't depend on timing details.

**What it means.** The rule did what Faber said about risk: it roughly halved SPY's worst loss and reduced
drawdowns on all six ETFs. It did not deliver returns close to buy-and-hold: it earned less on five of six
(SPY 8.1% vs. 11.0% a year, so $1 grew to about $4.1 instead of $6.5), and its Sharpe was higher on three ETFs
and lower on three.

**Descriptive check, after the run: without 2008–09 the result reverses.** The scored period starts just before
the 2008–09 crash. Scored from 2010 instead (`experiments/faber_after_2009.py`), the rule's SPY drawdown is
about the same as buy-and-hold's (23.1% vs. 23.9%), its Sharpe is lower (0.72 vs. 0.99) and it earns about half
the return (7.8% vs. 14.0% a year); its Sharpe is lower on five of six ETFs and equal on TLT. On that period
criteria 1 and 2 would fail (3 would still pass, 4 of 6), so by the same table the rule would not hold up.
The pass rests on one event. This does not change the pre-registered verdict,
but it is the honest reading: the rule works like insurance against a long crash, and it costs return in the
years without one.

**Notes.** Cash earns 0%; crediting T-bill interest would narrow the return gap only a little, since rates were
near zero for much of the period. Spreads use Yahoo's adjusted prices from before 2008, which sit below the
prices actually traded (dividends, and EEM's 3-for-1 split in 2008), so they lean high; with 29–40 trades in 18
years this costs the rule about 0.05% a year at most.

**BTC golden cross (optional second case): doesn't hold up.** From 2023 to 2025 its maximum drawdown was 38.5%
vs. 32.0% for buy-and-hold (needed at most 16.0%), and its Sharpe 0.64 vs. 1.42 (needed at least 1.32): both
fail. It earned 19.9% a year vs. 74.3%. It started the period in cash, missed the early-2023 rebound, and was
whipsawed in and out in 2024–25 (8 trades).
