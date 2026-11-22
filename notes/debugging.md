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