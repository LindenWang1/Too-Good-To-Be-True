# Cost assumptions and sources

Every cost the study uses, where it came from, and why. Fill in before the full sweep (guide Step 7.1).

| Cost | Crypto | ETFs | Source |
| --- | --- | --- | --- |
| Fee per side | 10 bps (Binance regular tier, 0.1%) | | Binance fee schedule (via CompareEdge, checked July 2026) |
| Half-spread | per asset, see `results/<run>/costs_used.csv` | per asset | Corwin & Schultz (2012) estimator on in-sample high/low prices |
| Impact coefficient `impact_k` | 0.5 (swept 0.25 / 0.5 / 1.0) | same | Square-root impact law; cite a source here |
| Latency | 0, 1, 2 bars | same | Design choice: 1 bar = 1 hour (crypto) / 1 day (ETFs) |

## Notes

- Corwin–Schultz was designed for daily bars; on hourly crypto it is a rough guide.
