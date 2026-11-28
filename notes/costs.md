# Cost Assumptions and Sources

Every cost the study charges, where its value comes from, and why. Written on 2026-11-27, before the full sweep; per-asset spread values are added after it (bottom section).

| Cost | Crypto | ETFs | Source |
| --- | --- | --- | --- |
| Fee per side (headline) | 10 bps (0.1%: Binance regular-user spot rate, maker and taker) | 0 bps ($0 online ETF commissions) | Binance spot fee FAQ and fee schedule; Schwab and Fidelity pricing pages (checked 2026-11-27) |
| Fee levels swept | 0, 5, 10, 20 bps | same | Design: brackets the real rates, from zero-commission brokers to above Binance's regular rate |
| Half-spread | 1 bp, every pair (fixed) | Half of one cent at the ETF's median in-sample price (one tick) | Observed quoted spreads (see below); Corwin & Schultz (2012) estimate saved alongside in `results/<run>/costs_used.csv` as a cross-check, not charged |
| Market impact | impact = k × σ × √(shares traded ÷ bar volume), k = 0.5 | same | Square-root impact law: Tóth et al. (2011), *Physical Review X* 1, 021006 |
| Latency | 0, 1, 2 bars (headline: 1) | same | Design: 1 bar = 1 hour (crypto) or 1 trading day (ETFs) |

## Why these Values

- **Crypto Fee, 10 bps.** Binance charges regular users 0.1% for both maker and taker spot trades. The 25% discount for paying fees in BNB and the lower VIP tiers are not assumed: 10 bps is what a small trader actually pays. The data comes from Binance's global exchange, which does not serve US residents; Binance.US currently charges 0% maker and 0.02% taker, which is why the 0 and 5 bps fee settings matter.
- **ETF Fee, 0 bps.** Schwab and Fidelity both charge $0 commission on online trades of US-listed ETFs. Small regulatory fees on sales (a few cents per $1,000) are ignored. None of the 20 ETFs used is on Fidelity's list of ETFs with a $100 service fee.
- **Impact Coefficient, k = 0.5.** Empirical studies of the square-root law find a prefactor of order 1; 0.5 is a moderate value within that range. Orders are $1M into very liquid markets, so impact is a small cost next to fees and spreads. Running k = 0.25 and k = 1.0 as a sensitivity check is listed as a next step; this version runs k = 0.5 only.
- **Spreads: why not Corwin–Schultz (decided 2026-11-27, before any results were opened).** The first full sweep charged each asset's Corwin–Schultz estimate. It gave crypto half-spreads of 8–17 bps (BTC 8.1, ETH 10.2, SOL 16.5, AVAX 17.1), while quoted Binance spreads for these pairs are a small fraction of a basis point today and at most a few bps in earlier years. High-low estimators are known to be biased upward when volatility is large relative to the true spread (Jahan-Parvar & Zikes, 2019), and hourly crypto is the worst case. Charging those values would roughly double crypto trading costs and make "costs kill the strategies" partly an artifact of the estimator. For ETFs the same estimator was noisy in both directions (0 bps for 8 of 20 ETFs, 8.5 bps for XLU).
- **Crypto spread, 1 bp (fixed).** Recent order-book snapshots put BTC/USDT and ETH/USDT spreads on Binance at a few hundredths of a basis point or less, and one tick on smaller pairs is around 1 bp wide. A 1 bp half-spread (2 bps round trip) is generous for the large pairs and about right for the smaller ones in earlier years. Anything wider is covered by the fee grid, since each extra bp of spread costs the same as a bp of fee.
- **ETF spread, one tick.** These ETFs trade with a one-cent spread (SPY's average spread is about 0.3 bps, and sector SPDRs quote $0.01). Half a cent divided by the ETF's median in-sample price gives each ETF's half-spread, e.g. about 0.4 bps for SPY and a few bps for low-priced funds like XLF. Yahoo's prices are adjusted backwards for splits and dividends, so they sit below the prices that actually traded. The 2-for-1 splits of XLB, XLE, XLK, XLU and XLY on 2025-12-05 are undone before computing the spread (`split_factors` in `bt/markets.py`); the dividend adjustment is left in, so the spread leans slightly high.
- **Every fee level is also run with no spread and with spread but no impact,** so each cost's effect can be read separately. The Corwin–Schultz estimate is kept in `costs_used.csv` (column `cs_half_spread_bps`) so the comparison stays visible.
- **Latency.** A signal formed at a bar's close is filled at the open 1 + latency bars later. The headline setting uses 1 bar, a realistic delay for a strategy that is not co-located with the exchange.

## Spread Estimates (filled in after the sweep)

From `results/<run>/costs_used.csv` (charged = `half_spread_bps`; cross-check = `cs_half_spread_bps`):

| Market | Charged: median (range) | Corwin–Schultz cross-check: median (range) | Notes |
| --- | --- | --- | --- |
| Crypto | 1.00 bp (all pairs) | | |
| ETFs | | | |

## Sources

- Binance, "How to Calculate Binance Spot Trading Fees": https://www.binance.com/en/support/faq/detail/e85d6e703b874674840122196b89780a
- Binance.US fee schedule: https://www.binance.us/fees
- Charles Schwab pricing: https://www.schwab.com/pricing
- Fidelity commissions and fees: https://www.fidelity.com/trading/commissions
- Corwin, S. A. & Schultz, P. (2012). A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices. *Journal of Finance*, 67(2).
- State Street, notice to authorized participants on share splits for five SPDR ETFs (2025-11-21): https://www.ssga.com/library-content/products/fund-docs/etfs/us/information-schedules/ap-notice/notice-to-aps-stock-splits-11-21-25.pdf
- Jahan-Parvar, M. R. & Zikes, F. (2019). When Do Low-Frequency Measures Really Measure Transaction Costs? Federal Reserve Board, FEDS 2019-051. https://www.federalreserve.gov/econres/feds/files/2019051pap.pdf
- ETF.com, "ETFs With The Highest & Lowest Trading Spreads" (SPY average spread 0.0032%): https://www.etf.com/sections/news/etfs-highest-lowest-trading-spreads
- Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J. & Bouchaud, J.-P. (2011). Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets. *Physical Review X*, 1, 021006. https://arxiv.org/abs/1105.1694
