# Shortcuts for every step of the project. Run `make <name>` from the repo folder.
# Each target lists the commands it runs, so you can always run them by hand instead.
# `make help` prints this list.

PY ?= python3

.PHONY: help build test smoke bench demo data snapshot validate eda sweep charts analyze casestudy walkforward model clean

help:             ## list the shortcuts
	@grep -E '^[a-z]+:.*##' Makefile | sed 's/:.*##/\t/'

build:            ## compile the C++ engine into engine_cpp/build/
	$(MAKE) -C engine_cpp

test: build       ## run the unit tests (fast: a few seconds)
	$(PY) -m pytest -q

smoke: build      ## run the WHOLE pipeline on fake data in a temp folder (about a minute)
	$(PY) experiments/smoke_test.py

bench: build      ## time the Python engine against the C++ engine
	$(PY) experiments/benchmark.py

demo: build       ## the study on four synthetic markets -> results/demo/
	$(PY) experiments/demo_synthetic.py

data:             ## download raw data into data/raw/ (needs internet; 10-20 minutes)
	$(PY) data/download.py binance --interval 1h --start 2019-01 --end 2025-12
	$(PY) data/download.py yfinance --start 2005-01-01 --end 2025-12-31
	$(PY) data/download.py french

snapshot:         ## freeze data/raw/ into Parquet + MANIFEST.json (commit the manifest)
	$(PY) data/make_snapshot.py

validate:         ## data-quality report for both markets -> results/data_quality_*.csv
	$(PY) data/validate.py --market crypto
	$(PY) data/validate.py --market etf

eda: build        ## baseline analysis, in-sample only -> results/eda/
	$(PY) experiments/eda.py --market crypto
	$(PY) experiments/eda.py --market etf

sweep: build      ## the full study: every market, with 5 placebo copies (can take an hour or more)
	$(PY) experiments/run_sweep.py --market crypto --long-only --placebo 5
	$(PY) experiments/run_sweep.py --market crypto
	$(PY) experiments/run_sweep.py --market etf --placebo 5

charts:           ## core part 1: in-sample charts -> figures/ (reads in-sample files only)
	$(PY) experiments/is_charts.py --run crypto_long_only
	$(PY) experiments/is_charts.py --run crypto
	$(PY) experiments/is_charts.py --run etf

analyze:          ## core part 2: UNSEALS out-of-sample results -> funnel, PBO, shrinkage
	$(PY) experiments/oos_analysis.py --run crypto_long_only
	$(PY) experiments/oos_analysis.py --run crypto
	$(PY) experiments/oos_analysis.py --run etf

casestudy: build  ## external case study: Faber's 10-month rule after publication
	$(PY) experiments/case_study.py

walkforward: build  ## validation: walk-forward + bootstrap ranges (after make analyze)
	$(PY) experiments/validation.py --market crypto --long-only
	$(PY) experiments/validation.py --market etf

model:            ## modeling question: the survival-model ladder (logs every run)
	$(PY) experiments/train_survival_model.py --market crypto_long_only --notes "make model"

clean:            ## delete compiled files and results (not data or figures)
	$(MAKE) -C engine_cpp clean
	rm -rf results .pytest_cache
