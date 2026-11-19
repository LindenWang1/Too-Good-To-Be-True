# Data notes

Decisions about the data, one line each. Fill in after `make validate` (Step 5 of the guide).
These become the "data funnel" slide and your answers in Q&A.

## Snapshot

- Downloaded on: YYYY-MM-DD
- MANIFEST.json commit: <git hash>

## Data funnel

| Market | Assets downloaded | Assets kept | Bars kept |
| --- | --- | --- | --- |
| Crypto (hourly) | 10 | | |
| ETFs (daily) | 21 | | |

## Flags from the quality report

| Asset | Problem | Decision |
| --- | --- | --- |
| XLC | Starts 2018: no in-sample history | Dropped (sweep skips it automatically: `--min-years 2`) |
| | | |
