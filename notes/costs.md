# Cost Assumptions and Sources

Every cost the study charges, where its value comes from, and why. Written on 2026-11-27, before the full sweep; per-asset spread values are added after it (bottom section).

| Cost | Crypto | ETFs | Source |
| --- | --- | --- | --- |
| Fee per side (headline) | 10 bps (0.1%: Binance regular-user spot rate, maker and taker) | 0 bps ($0 online ETF commissions) | Binance spot fee FAQ and fee schedule; Schwab and Fidelity pricing pages (checked 2026-11-27) |
| Fee levels swept | 0, 5, 10, 20 bps | same | Design: brackets the real rates, from zero-commission brokers to above Binance's regular rate |
| Half-spread | Per asset, estimated from in-sample high/low prices | same | Corwin & Schultz (2012), *Journal of Finance*; values saved to `results/<run>/costs_used.csv` |
| Market impact | impact = k × σ × √(shares traded ÷ bar volume), k = 0.5 | same | Square-root impact law: Tóth et al. (2011), *Physical Review X* 1, 021006 |
| Latency | 0, 1, 2 bars (headline: 1) | same | Design: 1 bar = 1 hour (crypto) or 1 trading day (ETFs) |

## Why these Values

- **Crypto Fee, 10 bps.** Binance charges regular users 0.1% for both maker and taker spot trades. The 25% discount for paying fees in BNB and the lower VIP tiers are not assumed: 10 bps is what a small trader actually pays. The data comes from Binance's global exchange, which does not serve US residents; Binance.US currently charges 0% maker and 0.02% taker, which is why the 0 and 5 bps fee settings matter.
- **ETF Fee, 0 bps.** Schwab and Fidelity both charge $0 commission on online trades of US-listed ETFs. Small regulatory fees on sales (a few cents per $1,000) are ignored. None of the 20 ETFs used is on Fidelity's list of ETFs with a $100 service fee.
- **Impact Coefficient, k = 0.5.** Empirical studies of the square-root law find a prefactor of order 1; 0.5 is a moderate value within that range. Orders are $1M into very liquid markets, so impact is a small cost next to fees and spreads. Running k = 0.25 and k = 1.0 as a sensitivity check is listed as a next step; this version runs k = 0.5 only.
- **Spreads from the data.** Corwin–Schultz reads the bid-ask spread out of each bar's high-low range. It was designed for daily bars, so on hourly crypto it is a rough guide; negative estimates are set to zero, and each asset uses the median over its in-sample period only, so out-of-sample data never sets a cost. Every fee level is also run with no spread and with spread but no impact, so each cost's effect can be read separately.
- **Latency.** A signal formed at a bar's close is filled at the open 1 + latency bars later. The headline setting uses 1 bar, a realistic delay for a strategy that is not co-located with the exchange.

## Spread Estimates (filled in after the sweep)

From `results/<run>/costs_used.csv`:

| Market | Median half-spread | Range across assets | Notes |
| --- | --- | --- | --- |
| Crypto | | | |
| ETFs | | | |

## Sources

- Binance, "How to Calculate Binance Spot Trading Fees": https://www.binance.com/en/support/faq/detail/e85d6e703b874674840122196b89780a
- Binance.US fee schedule: https://www.binance.us/fees
- Charles Schwab pricing: https://www.schwab.com/pricing
- Fidelity commissions and fees: https://www.fidelity.com/trading/commissions
- Corwin, S. A. & Schultz, P. (2012). A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices. *Journal of Finance*, 67(2).
- Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J. & Bouchaud, J.-P. (2011). Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets. *Physical Review X*, 1, 021006. https://arxiv.org/abs/1105.1694
