// Backtest Reality Check -- browser version of bt/reality_check.py (same formulas).
// Kept dependency-free so the GitHub Pages site needs no build step.

const EULER_GAMMA = 0.5772156649015329;

// Standard normal CDF (Abramowitz-Stegun 7.1.26 via erf), |error| < 1.5e-7
function normCdf(x) {
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
    * Math.exp(-(x * x) / 2);
  return x >= 0 ? 0.5 * (1 + y) : 0.5 * (1 - y);
}

// Inverse normal CDF (Acklam's algorithm), relative error < 1.2e-9
function normPpf(p) {
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const lo = 0.02425, hi = 1 - lo;
  let q, r;
  if (p < lo) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p > hi) {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  q = p - 0.5; r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

function psr(sr, T, skew, kurt, srStar) {
  const denom = 1 - skew * sr + (kurt - 1) / 4 * sr * sr;
  if (denom <= 0) return NaN;
  return normCdf((sr - srStar) * Math.sqrt(T - 1) / Math.sqrt(denom));
}

function expectedMaxSharpe(varSr, n) {
  if (n < 2) return 0;
  return Math.sqrt(varSr) * ((1 - EULER_GAMMA) * normPpf(1 - 1 / n) + EULER_GAMMA * normPpf(1 - 1 / (n * Math.E)));
}

function realityCheck({ sharpeAnn, years, periodsPerYear, nTrials = 1, annVol = null, annTurnover = null,
                        skew = 0, kurt = 3, trialSharpeSdAnn = null }) {
  const T = Math.round(years * periodsPerYear);
  const sr = sharpeAnn / Math.sqrt(periodsPerYear);
  const varSr = trialSharpeSdAnn == null ? 1 / T : (trialSharpeSdAnn / Math.sqrt(periodsPerYear)) ** 2;
  const sr0 = nTrials > 1 ? expectedMaxSharpe(varSr, nTrials) : 0;
  const out = {
    psr: psr(sr, T, skew, kurt, 0),
    dsr: psr(sr, T, skew, kurt, sr0),
    luckSharpeAnn: sr0 * Math.sqrt(periodsPerYear),
    nObs: T,
  };
  if (annVol != null && annTurnover) out.breakEvenFeeBps = sharpeAnn * annVol / annTurnover * 1e4;
  return out;
}

if (typeof module !== "undefined") module.exports = { realityCheck, normCdf, normPpf };
