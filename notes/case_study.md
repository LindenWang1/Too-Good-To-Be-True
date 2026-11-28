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

*Added after the run:* pass or fail on each criterion, one sentence on monthly vs. daily, and one sentence on what it means.