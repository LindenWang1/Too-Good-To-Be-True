# Data Notes

Decisions about the data, one line each, from make validate. Bugs found along the way are in debugging.md.

## Snapshot

- Downloaded on: 2026-11-20
- MANIFEST.json commit: d69e83b (data/snapshot/MANIFEST.json; Re-snapshot after the end-date fix and dropping XLC. First snapshot: 89d6ccb)
- Contents: 30 Files (10 coins, 20 ETFs, 2 Ken French factor files), each with row count, date range and SHA-256 hash
- Sources: Binance public data archive (hourly spot, USDT pairs, UTC); Yahoo Finance via yfinance (daily, adjusted, so dividends are included); Ken French Data Library (3 factors + momentum, daily)
- Ranges: Crypto 2019-01-01 -> 2025-12-31; ETFs 2005-01-03 -> 2025-12-31
- Out-of-Sample Starts (fixed, never moved): Crypto 2023-01-01; ETFs 2018-01-01
- Backup: Tarball of data/snapshot/ on my laptop and on Google Drive. The Parquet files are not in git, and Yahoo revises adjusted prices, so a fresh download will not match the hashes; the tarball is the only exact copy.


## Data Funnel

| Market | Assets Downloaded | Assets Kept | Bars Kept |
| --- | --- | --- | --- |
| Crypto (hourly) | 10 | 10 | 579,120 (316,090 in-sample returns) |
| ETFs (daily) | 21 | 20 | 102,618 (62,398 in-sample returns) |

- In-sample Returns: bar-to-bar returns before the out-of-sample start; these are what strategies are fitted on.
- Completeness: coins with the full 2019-2025 history have 61,309 of 61,368 possible hours (99.9%); ETFs have every trading day.
- Hard checks, all 30 series: 0 duplicate timestamps, 0 non-positive prices, 0 bars where the high or low contradicts the open or close.


## Flags from the Quality Report

| Asset | Problem | Decision |
| --- | --- | --- |
| XLC | Starts 2018: No in-sample history | Dropped (sweep skips it automatically: `--min-years 2`). Also removed from the download list and the EDA (`4f0c029`) and the snapshot (`d69e83b`); `make validate` no longer lists it |
| All ETFs | `yfinance` treats `end` as exclusive, so 2025-12-31 was missing | Fixed in `data/download.py` before the snapshot; all ETFs now end 2025-12-31 |
| All Coins | Binance files from Jan 2025 use microsecond timestamps (earlier: milliseconds) | Handled by the parser (`tests/test_data_parsing.py`); all coins end 2025-12-31 23:00 UTC |
| XLRE | Starts 2015-10-08: ≈ 2.2 years in-sample (562 returns), the shortest | Kept (passes the 2-year rule); its in-sample statistics are noisy (noise band ±0.083) |
| AVAX | Starts 2020-09-22: ≈ 2.3 years in-sample; biggest move is on its listing day | Kept; less data behind its in-sample winners |
| SOL | Starts 2020-08-11: ≈ 2.4 years in-sample | Kept; same caveat |
| DOGE, LINK | Start 2019-07-05 and 2019-01-16, later than the other coins | Kept; more than 3 years in-sample each |
| SLV | Starts 2006-04-28, a year after the other ETFs | Kept |
| All Coins | 10-20 gaps over 1.5 h, the same hours on every coin; longest 11 h (2019-05-15) | Kept: exchange-wide Binance outages, none longer than a day |
| All ETFs | 2 gaps of 5 days: 2006-12-29 -> 2007-01-03 and 2012-10-26 -> 2012-10-31 | Kept: real market closures (President Ford's day of mourning; Hurricane Sandy) |
| All Coins, XLRE | Zero-volume bars: 3-5 per coin at the same outage hours; XLRE 5 days in its first four months | Kept: prices valid. Both engines set participation to 0 when volume is 0 (`engine_py.py:205`, `engine.cpp:153`), so no division by zero, just no impact charged |
| All Assets | Moves beyond 8 sd: crypto 28-93 bars per coin (DOGE 93); ETFs 0-7 days | Kept: real market events (dates below); removing them would make strategies look safer than they are |
| Ken French factors | Run to Sep 2026, past the study's end | Downloaded, not used yet (optional factor check, 7B.5) |


## Extreme Moves: Main Dates

Largest one-bar moves (absolute log return; 0.20 ≈ 20%). Event labels are from public news.

| Date | Assets | Largest | Event | Period |
| --- | --- | --- | --- | --- |
| Sep 2008 - Mar 2009 | Most equity ETFs, GLD, SLV | 0.21 (EEM, 2008-10-13) | Global financial crisis | In-sample |
| 2020-03-12/13 | 7 of 10 coins | 0.23 (ETH, BNB) | COVID crash | In-sample |
| 2021-01-28/29 | DOGE | 0.53 (largest in the data) | DOGE pump | In-sample |
| 2021-05-19 | All 10 coins | 0.30 (LTC) | May 2021 crash | In-sample |
| 2022-05-11 | AVAX, SOL, ETH, LTC | 0.30 (AVAX) | Terra/LUNA collapse | In-sample |
| 2022-11-08/14 | BNB, SOL | 0.15 (SOL) | FTX collapse | In-sample |
| 2020-03-09 - 03-24 | Most ETFs | 0.22 (XLE) | COVID crash; oil price war | Out-of-sample |
| 2023-07-13 | XRP | 0.22 | SEC v. Ripple ruling | Out-of-sample |
| 2025-03-02 | ADA | 0.29 | U.S. crypto-reserve announcement | Out-of-sample |
| 2025-04-09 | QQQ, SPY, XLK | 0.13 (XLK) | Tariff-pause rally | Out-of-sample |
| 2025-10-10 | ADA, LTC | 0.20 (LTC) | Market-wide liquidation crash | Out-of-sample |