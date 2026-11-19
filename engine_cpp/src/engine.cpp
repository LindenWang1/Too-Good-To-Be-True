// Too Good to Be True -- Event-Driven Backtesting Engine (C++17).
//
// PURPOSE
//   The fast twin of bt/engine_py.py. It follows exactly the same rules (read the
//   Python file's docstring first: timing, costs, strategies) and produces the
//   same trades and equity; tests/test_parity.py checks that on every push.
//   It exists for speed: the study runs ~260,000 backtests, which would take
//   days in Python and takes minutes here.
//
// HOW PYTHON CALLS IT
//   This file is compiled into a shared library (libtgtb.so / .dylib) that
//   Python loads at run time with the standard `ctypes` module (bt/engine_cpp.py).
//   The functions at the bottom are wrapped in `extern "C"` so their names are
//   kept plain and ctypes can find them. Arrays arrive as raw pointers into
//   NumPy's memory, so nothing is copied.
//
// LAYOUT
//   helpers -> strategy_target (the 5 strategies) -> sigma_before (volatility)
//   -> run_core (the event loop) -> compute_metrics -> the two exported functions.
//
// Build:  make -C engine_cpp      (produces engine_cpp/build/libtgtb.so)

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace {

// Strategy family ids: must match bt/config.py.
constexpr int TSMOM = 0, MA_CROSS = 1, ZSCORE_MR = 2, DONCHIAN = 3, RSI_MR = 4;
constexpr int VOL_WINDOW = 20;
constexpr int N_PARAMS = 4;
constexpr int N_METRICS = 6;  // sharpe, total_return, max_dd, ann_turnover, n_trades, mean_ret

// Cost settings for one run (mirrors ExecConfig in bt/config.py).
struct Exec {
    double fee_bps, half_spread_bps, impact_k;
    int latency;
    double capital;
    int long_only;
};

// --- small helpers. They add numbers in the SAME order as the Python reference,
// so floating-point rounding is identical and results match to 1e-9. ---
inline double mean_range(const double* x, int a, int b) {  // [a, b)
    double s = 0.0;
    for (int i = a; i < b; ++i) s += x[i];
    return s / (b - a);
}

inline double pstd_range(const double* x, int a, int b) {
    double m = mean_range(x, a, b);
    double s = 0.0;
    for (int i = a; i < b; ++i) { double d = x[i] - m; s += d * d; }
    return std::sqrt(s / (b - a));
}

inline double sign(double v) { return v > 0 ? 1.0 : (v < 0 ? -1.0 : 0.0); }

// The position (-1, 0, +1) a strategy wants at the close of bar t, using close[0..t]
// only. `p` = the strategy's 4 parameters; `prev` = its decision on the previous bar.
// Each case is a line-for-line translation of strategy_target() in engine_py.py.
double strategy_target(int f, const double* p, const double* close, int t, double prev) {
    switch (f) {
    case TSMOM: {          // momentum: sign of the return over `lookback` bars
        int lookback = (int)p[0], rebalance = std::max(1, (int)p[1]);
        if (t < lookback) return 0.0;
        if (t % rebalance != 0) return prev;
        return sign(close[t] / close[t - lookback] - 1.0);
    }
    case MA_CROSS: {       // long when the fast moving average is above the slow one
        int fast = (int)p[0], slow = (int)p[1];
        if (t < slow - 1) return 0.0;
        double mf = mean_range(close, t - fast + 1, t + 1);
        double ms = mean_range(close, t - slow + 1, t + 1);
        return mf > ms ? 1.0 : (mf < ms ? -1.0 : 0.0);
    }
    case ZSCORE_MR: {      // fade prices that are `entry` std devs from their average
        int window = (int)p[0];
        double entry = p[1], exit_ = p[2];
        if (t < window - 1) return 0.0;
        double sd = pstd_range(close, t - window + 1, t + 1);
        if (sd == 0) return prev;
        double z = (close[t] - mean_range(close, t - window + 1, t + 1)) / sd;
        if (prev == 0.0) return z > entry ? -1.0 : (z < -entry ? 1.0 : 0.0);
        if (prev > 0 && z >= -exit_) return 0.0;
        if (prev < 0 && z <= exit_) return 0.0;
        return prev;
    }
    case DONCHIAN: {       // buy new highs, short new lows; exits checked before entries
        int ent = (int)p[0], ext = (int)p[1];
        double pos = prev;
        if (t >= ext) {
            double lo = *std::min_element(close + t - ext, close + t);
            double hi = *std::max_element(close + t - ext, close + t);
            if (pos > 0 && close[t] < lo) pos = 0.0;
            else if (pos < 0 && close[t] > hi) pos = 0.0;
        }
        if (pos == 0.0 && t >= ent) {
            double lo = *std::min_element(close + t - ent, close + t);
            double hi = *std::max_element(close + t - ent, close + t);
            if (close[t] > hi) pos = 1.0;
            else if (close[t] < lo) pos = -1.0;
        }
        return pos;
    }
    case RSI_MR: {         // buy oversold (RSI < lower), short overbought; exit at 50
        int period = (int)p[0];
        double lower = p[1], upper = p[2];
        if (t < period) return 0.0;
        double gain = 0.0, loss = 0.0;
        for (int i = t - period + 1; i <= t; ++i) {
            double d = close[i] - close[i - 1];
            if (d > 0) gain += d; else loss -= d;
        }
        double rsi = loss == 0 ? 100.0 : 100.0 - 100.0 / (1.0 + gain / loss);
        if (prev == 0.0) return rsi < lower ? 1.0 : (rsi > upper ? -1.0 : 0.0);
        if (prev > 0 && rsi >= 50) return 0.0;
        if (prev < 0 && rsi <= 50) return 0.0;
        return prev;
    }
    }
    return 0.0;
}

// Volatility for the impact model: std of the 20 log returns ending at close[t-1],
// i.e. information available before the open of bar t.
double sigma_before(const double* close, int t) {
    if (t - VOL_WINDOW < 1) return 0.0;
    double r[VOL_WINDOW];
    for (int k = 0, i = t - VOL_WINDOW; i < t; ++i, ++k) r[k] = std::log(close[i] / close[i - 1]);
    return pstd_range(r, 0, VOL_WINDOW);
}

// The event loop: one pass over the bars, in three steps per bar
// (trade at the open -> value at the close -> decide and schedule the next order).
// Writes equity[n] (and targets[n] if given); returns the number of trades.
int run_core(const double* open, const double* close, const double* volume, int n,
             int family, const double* params, const Exec& ex,
             double* equity, double* targets, double* turnover_out) {
    std::vector<double> sched(n, NAN);   // sched[t] = target to trade at bar t's open; NAN = no order
    double cash = ex.capital, units = 0.0, cur_target = 0.0, prev = 0.0, turnover = 0.0;
    int n_trades = 0;

    for (int t = 0; t < n; ++t) {
        // 1) OPEN of bar t: execute the order scheduled earlier, if it changes the position
        if (t > 0 && !std::isnan(sched[t]) && sched[t] != cur_target) {
            double eq_open = cash + units * open[t];
            double desired = sched[t] * eq_open / open[t];
            double delta = desired - units;
            if (delta != 0.0) {
                double part = volume[t] > 0 ? std::fabs(delta) / volume[t] : 0.0;
                double slip = ex.half_spread_bps * 1e-4 + ex.impact_k * sigma_before(close, t) * std::sqrt(part);
                double price = delta > 0 ? open[t] * (1.0 + slip) : open[t] * (1.0 - slip);
                double notional = std::fabs(delta) * price;
                cash -= delta * price;
                cash -= notional * ex.fee_bps * 1e-4;
                turnover += std::fabs(delta) * open[t] / eq_open;
                ++n_trades;
                units = desired;
            }
            cur_target = sched[t];
        }
        // 2) CLOSE of bar t: record the portfolio's value
        equity[t] = cash + units * close[t];
        // 3) still at the close: decide from close[0..t]; trade it at the open of t+1+latency
        prev = strategy_target(family, params, close, t, prev);  // strategy keeps its own state
        double tgt = ex.long_only ? std::max(prev, 0.0) : prev;
        if (targets) targets[t] = tgt;
        int exec_bar = t + 1 + ex.latency;
        if (exec_bar < n) sched[exec_bar] = tgt;
    }
    if (turnover_out) *turnover_out = turnover;
    return n_trades;
}

// Summary statistics of one equity curve (same definitions as bt/metrics.py):
// annualized Sharpe, total return, max drawdown, annual turnover, trades, mean bar return.
void compute_metrics(const double* eq, int n, double turnover, int n_trades,
                     double periods_per_year, double* out) {
    // out: sharpe, total_return, max_dd, ann_turnover, n_trades, mean_ret
    int m = n - 1;
    double s = 0.0;
    for (int i = 1; i < n; ++i) s += eq[i] / eq[i - 1] - 1.0;
    double mu = s / m;
    double v = 0.0;
    for (int i = 1; i < n; ++i) { double d = (eq[i] / eq[i - 1] - 1.0) - mu; v += d * d; }
    double sd = m > 1 ? std::sqrt(v / (m - 1)) : 0.0;
    double peak = eq[0], mdd = 0.0;
    for (int i = 0; i < n; ++i) { peak = std::max(peak, eq[i]); mdd = std::max(mdd, 1.0 - eq[i] / peak); }
    out[0] = sd > 0 ? mu / sd * std::sqrt(periods_per_year) : 0.0;
    out[1] = eq[n - 1] / eq[0] - 1.0;
    out[2] = mdd;
    out[3] = turnover / m * periods_per_year;
    out[4] = (double)n_trades;
    out[5] = mu;
}

}  // namespace

extern "C" {

// Version number checked by bt/engine_cpp.py, so an old compiled library is detected.
int tgtb_version() { return 2; }

// One backtest; fills equity_out[n] and target_out[n]. Returns number of trades.
int tgtb_run(const double* open, const double* close, const double* volume, int n,
             int family, const double* params,
             double fee_bps, double half_spread_bps, double impact_k, int latency, double capital,
             int long_only, double* equity_out, double* target_out, double* turnover_out) {
    Exec ex{fee_bps, half_spread_bps, impact_k, latency, capital, long_only};
    return run_core(open, close, volume, n, family, params, ex, equity_out, target_out, turnover_out);
}

// Many configs on one asset under one execution setting.
// families[n_cfg], params[n_cfg * 4]  ->  metrics_out[n_cfg * 6]
// If returns_out is non-null it receives per-bar returns [n_cfg * (n-1)] (for DSR / PBO).
void tgtb_sweep(const double* open, const double* close, const double* volume, int n,
                int n_cfg, const int* families, const double* params,
                double fee_bps, double half_spread_bps, double impact_k, int latency, double capital,
                int long_only, double periods_per_year, double* metrics_out, double* returns_out) {
    Exec ex{fee_bps, half_spread_bps, impact_k, latency, capital, long_only};
    std::vector<double> eq(n);
    for (int c = 0; c < n_cfg; ++c) {
        double turnover = 0.0;
        int trades = run_core(open, close, volume, n, families[c], params + c * N_PARAMS, ex,
                              eq.data(), nullptr, &turnover);
        compute_metrics(eq.data(), n, turnover, trades, periods_per_year, metrics_out + c * N_METRICS);
        if (returns_out) {
            double* r = returns_out + (int64_t)c * (n - 1);
            for (int i = 1; i < n; ++i) r[i - 1] = eq[i] / eq[i - 1] - 1.0;
        }
    }
}

}  // extern "C"
