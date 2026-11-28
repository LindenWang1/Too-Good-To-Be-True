# Debugging Log

Problems found while building and running the project: the symptom, the cause, the fix and how it was checked. Bugs that change data or results are the ones reviewers ask about, so each entry names the commit that fixed it.

## Fixed

### 1. Yahoo end date is exclusive: the last trading day was missing (Nov 20)

- **Symptom:** after the first download, the ETF files ended on 2025-12-30, one trading day short of the study's end date.
- **Cause:** `yfinance` treats `end=` as *exclusive*: `end="2025-12-31"` returns data up to 2025-12-30.
- **Fix:** corrected the end date in `data/download.py` so 2025-12-31 is included, then re-downloaded and re-snapshotted. Commit `d69e83b`.
- **Check:** `make validate` shows every kept ETF ending 2025-12-31. The stale XLC file from before the fix still ended 2025-12-30, which is the bug's fingerprint.
- **Why it matters:** an off-by-one at the end of the data silently shortens the out-of-sample period. Easy to miss, because nothing errors.

### 2. `make eda` crashed with `IndexError` (Nov 20)

- **Symptom:** `make eda` stopped with `IndexError: single positional indexer is out-of-bounds`, raised at `experiments/eda.py` line 89: `curves[asset]["buy_and_hold"] = df.close.to_numpy() / df.close.iloc[0] * 1e6`.
- **Cause:** the EDA uses in-sample data only. XLC starts 2018-06-19, after the ETF out-of-sample start (2018-01-01), so its in-sample table was empty, and `.iloc[0]` (the first row) doesn't exist. The sweep already skipped such assets (`--min-years 2`); the EDA didn't.
- **Fix:** the EDA now skips assets with less than 2 in-sample years, the same rule as the sweep, so the two scripts can't disagree about which assets count. Commit `4f0c029`.
- **Check:** `make eda` runs to the end and lists 20 ETFs.

### 3. XLC dropped from the snapshot but still in the download list (Nov 20–21)

- **Symptom:** XLC was removed from the snapshot, but `data/download.py` still listed it, so any re-download would bring it back.
- **Fix:** removed it from the `ETFS` list. Commit `4f0c029`.
- **Check:** `grep -n XLC data/download.py` returns nothing, and `make validate` (re-run Nov 21) lists 20 ETFs with no XLC.

### 6. Short positions could lose more than the whole account (Nov 27)

- **Symptom:** the first full sweep printed `RuntimeWarning: invalid value encountered in subtract` three times, only in the crypto long-short run (from numpy, scipy and `bt/stats.py:146`).
- **Cause:** neither engine handled ruin. A short held through a big rally (e.g. DOGE) can lose more than 100%; equity went negative, and because position size is equity / price, negative equity flipped the position and the numbers could blow up to infinity. Those values reached the Sharpe, DSR and PBO calculations as NaN. Long-only runs can't be affected (a long loses at most 100%).
- **Fix:** limited liability in both engines. If equity reaches zero at an open or a close, the position is liquidated, equity is set to 0 and the strategy stops trading; that bar's return is −100% and later bars return 0. Bar returns are computed the same way in Python (`bt/metrics.py`) and C++.
- **Check:** three new tests in `tests/test_engine_rules.py`: a short wiped out by a 2.5× jump is liquidated and stays at zero (the old engine ended at −$266,187); Python, C++ and the C++ sweep agree bar for bar; the same path is never ruined long-only. On a synthetic coin with 25 hourly pumps, the old code produced 1,226 result rows with NaN/infinite values and 3,364 rows with drawdowns above 100%; the fixed code produced none. All three runs are re-run with the fix; each run_info.json records the commit that produced it.

### 7. The spread estimator overstated crypto costs about tenfold or more (Nov 27)

- **Symptom:** the first full sweep's Corwin–Schultz half-spreads were 8–17 bps for every coin, far above quoted Binance spreads.
- **Cause:** not a code bug: high-low estimators are biased upward when volatility is large relative to the true spread (Jahan-Parvar & Zikes, 2019).
- **Fix:** spreads now come from a per-market model in `bt/markets.py` (crypto: fixed 1 bp; ETFs: one tick at the median in-sample price). Corwin–Schultz is kept as a cross-check column. Decided before any results were opened; details and sources in `notes/costs.md`.
- **Check:** new tests in `tests/test_costs_and_clusters.py`; `costs_used.csv` shows both values for every asset.

### 8. Five ETFs were charged double spreads because of a 2025 share split (Nov 27)

- **Symptom:** in the re-run sweep, five sector ETFs had the highest one-tick spreads: XLK 4.71, XLU 4.70, XLB 3.65, XLY 3.10 and XLE 2.39 bps, far above SPY (0.49) and above what a one-cent spread on those funds' actual prices implies.
- **Cause:** exactly these five split 2-for-1 on 2025-12-05. Yahoo divides every earlier price by the split, so their 2005–2017 prices in the data are half what actually traded, and half a cent looks twice as wide in bps.
- **Fix:** `split_factors` in `bt/markets.py` multiplies those five funds' prices by 2 before the tick spread is computed (source: State Street's notice to authorized participants, 2025-11-21). The ETF run was re-swept; the crypto runs don't use this model and were unchanged.
- **Check:** a new assertion in `tests/test_costs_and_clusters.py`; in `costs_used.csv` the five funds' spreads halve (about 1.2–2.4 bps) and their source says "x2 for a later split".

## Checked: no bug

### 4. Could a zero-volume bar break the market-impact formula? (Nov 21)

- **Concern:** impact uses √(shares traded ÷ bar volume), and the data has a few bars with zero volume (`notes/data.md`).
- **Finding:** both engines guard against it: our share of the bar's volume is set to 0 when volume is 0 (`bt/engine_py.py:205`, `engine_cpp/src/engine.cpp:153`). No division by zero; such bars are charged the fee and half-spread but no impact. At most 5 bars per asset, so the effect on results is negligible.

### 5. Do the data gaps mean missing files? (Nov 21)

- **Finding:** no. Crypto gaps fall on the same hours for every coin (exchange-wide Binance outages). The two ETF gaps are real market closures (Jan 2, 2007; Oct 29–30, 2012). Both are kept; details in `notes/data.md`.

## Safeguards already in the code

Earlier pitfalls that the pipeline now handles automatically, each covered by a test:

- **Binance timestamp units:** spot files from January 2025 on use microsecond timestamps instead of milliseconds. The parser handles both (`tests/test_data_parsing.py`). The crypto data correctly ends 2025-12-31 23:00 UTC.
- **Look-ahead bias:** a signal formed at bar t's close fills at bar t + 1 + latency's open, and tests check that the engine never reads a future bar (`tests/test_engine_rules.py`).
- **Two engines, one answer:** the Python and C++ engines must produce identical trades and P&L (`tests/test_parity.py`).
- **Python/C++ rounding:** helpers add numbers in a fixed order so both engines round identically.