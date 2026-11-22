# Too Good to Be True: How much of a backtest is real?

A fast event-driven backtesting engine in C++, and a study of how many "profitable"
trading strategies survive **realistic costs**, **multiple-testing correction**, and
**data they have never seen**.

*Linden Wang · Fall 2026*

**Live demo:** https://lindenwang1.github.io/Too-Good-To-Be-True/

> **Results:** _coming after the full sweep._ This section will hold the
> headline funnel ("of N strategies that looked profitable, X survived"), the two key
> charts, and a link to the live website.

## The Question

**How much of a backtest's performance is real, and can we tell in advance which strategies will hold up?**

1. **Realism.** How much does net Sharpe fall as fees, bid-ask spread, market impact and
   latency move from zero to realistic levels, by strategy family and market?
2. **Overfitting.** After correcting for how many configurations were tried (Deflated
   Sharpe Ratio, Probability of Backtest Overfitting), what share of in-sample winners
   still beat zero out of sample?
3. **Modeling.** Can in-sample traits predict which strategies survive better than the
   in-sample Sharpe alone?

Markets: 10 large crypto pairs (Binance, hourly, 2019–2025) and 20 US ETFs (daily,
2005–2025; XLC dropped: no in-sample history). 5 strategy families, 182 configurations and 36 cost settings, run three times (crypto long-only,
crypto long-short, ETFs): about 262,000 backtests, plus about 55,000 on shuffled placebo data.

## Why it's built this way

- **Two engines that must agree.** `bt/engine_py.py` is a plain Python loop anyone can
  check by eye. `engine_cpp/src/engine.cpp` follows the same rules over 100× faster.
  Tests require identical trades and equity (within 1e-9) on every strategy and cost setting.
- **No look-ahead, by construction.** A decision made at bar *t*'s close is filled at
  the open of bar *t + 1 + latency*. A test plants a future price spike and checks
  that nothing before it changes.
- **Costs from the data.** Bid-ask spreads are estimated from each asset's own in-sample
  high/low prices (Corwin–Schultz); fees use the real fee schedule (Binance 0.1% per
  side); market impact follows the square-root law and is swept as a sensitivity.
- **Sealed out-of-sample data.** The sweep writes out-of-sample results to separate
  `SEALED_*` files, opened only after the in-sample analysis is done.
- **Honest statistics.** Near-duplicate configurations are clustered before the Deflated
  Sharpe Ratio counts "trials", and a shuffled-data placebo shows how many winners
  pure luck produces. Placebo bars are shuffled within the in-sample and out-of-sample
  periods separately, so no out-of-sample data leaks into the placebo's in-sample period.

## Quick Start

Linux, macOS, or Windows via WSL. Needs Python 3.10+, `g++`, and `make`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test      # build the C++ engine, run 63 unit tests (seconds)
make smoke     # the whole pipeline on fake data, in a temp folder (about a minute)
make bench     # Python vs C++ speed
```

## Reproduce the study

```bash
make data       # download Binance, Yahoo Finance and Ken French data
make snapshot   # freeze to Parquet + data/snapshot/MANIFEST.json (hashes)
make validate   # data-quality report
make eda        # baseline analysis (in-sample only)
make sweep      # every market, 182 configs x 36 cost settings, + placebo copies
make charts     # core part 1: cost curves, heatmaps, turnover   -> figures/
make analyze    # core part 2: unseals out-of-sample; funnel, PBO, shrinkage
make model      # modeling question: the survival-model ladder
```

`make help` lists every shortcut. Each one is a short list of commands in the `Makefile`.

## Status

| Piece | State |
| --- | --- |
| Python reference engine and C++ engine (long-short and long-only) | Done; parity-tested |
| Strategy grid (182 configs) and cost grid (36 settings) | Done |
| Corwin–Schultz spread estimates per asset | Done; tested |
| PSR, Deflated Sharpe (naive and clustered), PBO, placebo | Done; tested |
| Data download, snapshot, quality report, baseline analysis | Done; run on real data (see notes/) |
| Sweep, in-sample charts, out-of-sample analysis | Done; tested end to end on fake data |
| Survival-model ladder with experiment log | Done; to run on real data |
| Backtest Reality Check (website demo) | First version in `site/` |
| Engine v2 (running sums, multithreading) | Next |
| Scroll-story website, final slides, Medium post | Next |

Benchmark (synthetic data, 5,000 bars, all costs on): Python ~45 ms vs. C++ ~0.34 ms per
backtest (about 130×; 100–135× across runs); all 182 configurations on one asset in ~0.055 s.

## Layout

```
bt/              the library
  config.py        strategy ids and cost settings (ExecConfig) shared by both engines
  markets.py       per-market settings: out-of-sample start date, headline cost setting
  engine_py.py     Python reference engine (read this first)
  engine_cpp.py    ctypes bindings to the C++ engine
  grids.py         the 182 strategy configurations and 36 cost settings
  costs.py         Corwin-Schultz bid-ask spread estimates
  stats.py         PSR, Deflated Sharpe (naive + clustered), PBO, placebo shuffling
  pipeline.py      one asset x every config x every cost setting, split in/out of sample
  survival_model.py  the model ladder
  reality_check.py   maths behind the website demo
  data.py, paths.py, metrics.py, synthetic.py, plotstyle.py   helpers
engine_cpp/      src/engine.cpp + Makefile (plain C ABI, no extra build tools)
data/            download.py, make_snapshot.py, validate.py  (raw/ and snapshot/ are git-ignored)
experiments/     scripts you run: eda, run_sweep, is_charts, oos_analysis,
                 train_survival_model, benchmark, demo_synthetic, smoke_test
tests/           63 unit tests
notes/           data, EDA, case study, debugging log, costs, results (see notes/README.md)
figures/         charts used on the slides and website (committed)
site/            the website (published by .github/workflows/pages.yml)
```

## References

- Bailey & López de Prado (2014), *The Deflated Sharpe Ratio*, Journal of Portfolio Management.
- Bailey, Borwein, López de Prado & Zhu (2017), *The Probability of Backtest Overfitting*, Journal of Computational Finance.
- Harvey, Liu & Zhu (2016), *…and the Cross-Section of Expected Returns*, Review of Financial Studies.
- McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return Predictability?*, Journal of Finance.
- Corwin & Schultz (2012), *A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices*, Journal of Finance.

## License

MIT (see `LICENSE`).
