#!/usr/bin/env python3
"""
Gold Fear & Greed Index — Backtest Framework

Standalone tool to test model variants against historical data.
Downloads Yahoo (GLD, GC=F, SPY, DX=F, ^VIX) and FRED (DFII10) data,
caches locally, and computes the index with configurable parameters.

Usage:
    python backtest_gold.py                          # Default model
    python backtest_gold.py --weights 0.30,0.25,0.20,0.15,0.10
    python backtest_gold.py --gld-mult 7
    python backtest_gold.py --refresh --years 3
"""

import argparse
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ─── Constants ───────────────────────────────────────────────────────────────

FRED_API_KEY = "6f92656f50613f5438ddc820ff3ee3d8"
CACHE_DIR = Path("data/backtest-cache")
CACHE_MAX_AGE_HOURS = 24

YAHOO_TICKERS = ["GLD", "GC=F", "SPY", "DX=F", "^VIX"]

DEFAULT_WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]
COMPONENT_NAMES = [
    "GLD Price",
    "RSI/MA Momentum",
    "Dollar Index",
    "Real Rates",
    "VIX",
]

KEY_DATES = [
    ("2024-10-30", "Gold ATH run-up"),
    ("2023-10-06", "Gold local low"),
    ("2024-03-08", "Gold breakout above 2100"),
    ("2022-09-28", "Gold bottom (strong dollar)"),
    ("2022-03-08", "Gold spike (Ukraine)"),
    ("2023-03-13", "SVB crisis (gold safe haven)"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATA LAYER
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_fred_series(series_id: str, start: str, end: str) -> pd.Series:
    """Fetch a FRED time series and return as pandas Series."""
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
        f"&observation_start={start}&observation_end={end}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    obs = resp.json()["observations"]

    dates, values = [], []
    for o in obs:
        if o["value"] == ".":
            continue
        dates.append(pd.Timestamp(o["date"]))
        values.append(float(o["value"]))

    return pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id)


def fetch_yahoo(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch Yahoo Finance OHLCV data."""
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df


def _cache_path(name: str) -> Path:
    safe_name = name.replace("^", "_").replace("=", "_").replace(".", "_")
    return CACHE_DIR / f"{safe_name}.csv"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_HOURS * 3600


def load_or_fetch_data(years: int = 5, refresh: bool = False) -> dict:
    """
    Load all data sources, using CSV cache when available.
    Returns dict with keys: GLD, GC=F, SPY, DX=F, ^VIX (DataFrames), DFII10 (Series).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=years * 365 + 250)).strftime("%Y-%m-%d")

    data = {}

    # FRED: DFII10
    path = _cache_path("DFII10")
    if not refresh and _cache_fresh(path):
        s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze("columns")
        s.name = "DFII10"
        print(f"  [cache] DFII10 (10Y TIPS): {len(s)} obs")
    else:
        print(f"  [fetch] DFII10 (10Y TIPS)...", end=" ")
        s = fetch_fred_series("DFII10", start_date, end_date)
        s.to_csv(path)
        print(f"{len(s)} obs")
    data["DFII10"] = s

    # Yahoo tickers
    for ticker in YAHOO_TICKERS:
        path = _cache_path(ticker)
        if not refresh and _cache_fresh(path):
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            print(f"  [cache] {ticker}: {len(df)} days")
        else:
            print(f"  [fetch] {ticker}...", end=" ")
            df = fetch_yahoo(ticker, start_date, end_date)
            df.to_csv(path)
            print(f"{len(df)} days")
        data[ticker] = df

    # Align FRED to GLD trading days
    trading_days = data["GLD"].index
    data["DFII10"] = data["DFII10"].reindex(trading_days, method="ffill")

    # Trim to requested period
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=years * 365))
    trading_days = trading_days[trading_days >= cutoff]

    return data, trading_days


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COMPONENT CALCULATORS
# ═══════════════════════════════════════════════════════════════════════════════

def _pct_change(series, idx, lookback=14):
    """Percentage change over lookback days ending at idx."""
    if idx < lookback:
        return 0.0
    return ((series.iloc[idx] / series.iloc[idx - lookback]) - 1) * 100


def calc_gld_price(gld_close, idx, mult=5):
    """Score = 50 + (GLD 14d % change * mult), clamped 0-100."""
    pct = _pct_change(gld_close, idx, 14)
    return max(0, min(100, 50 + pct * mult))


def calc_rsi_ma_momentum(gold_close, idx):
    """
    Composite RSI + MA50 + MA200 score.
    Matches live: ma50_contrib (±15), ma200_contrib (±10), rsi_contrib (±25).
    """
    if idx < 200:
        return 50.0

    prices = gold_close.iloc[:idx + 1]
    current = prices.iloc[-1]
    ma50 = prices.iloc[-50:].mean()
    ma200 = prices.iloc[-200:].mean()

    # RSI 14
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]
    if pd.isna(current_rsi):
        current_rsi = 50.0

    ma50_pct = ((current - ma50) / ma50) * 100
    ma50_contrib = max(-15, min(15, ma50_pct * 1.5))
    ma200_pct = ((current - ma200) / ma200) * 100
    ma200_contrib = max(-10, min(10, ma200_pct * 0.5))
    rsi_contrib = max(-25, min(25, (current_rsi - 50) * 0.5))

    score = 50 + ma50_contrib + ma200_contrib + rsi_contrib
    return max(0, min(100, score))


def calc_dollar_index(dxy_close, idx, mult=15):
    """Score = 50 - (DXY 14d % change * mult), clamped 0-100."""
    pct = _pct_change(dxy_close, idx, 14)
    return max(0, min(100, 50 - pct * mult))


def calc_real_rates(dfii10, idx, mult=18.75):
    """Score = 75 - (TIPS rate * mult), clamped 0-100."""
    if pd.isna(dfii10.iloc[idx]):
        return 50.0
    return max(0, min(100, 75 - dfii10.iloc[idx] * mult))


def calc_vix(vix_close, idx, lookback=63, z_mult=25):
    """
    Score = 50 + (VIX z-score vs lookback period * z_mult), clamped 0-100.
    High VIX = market fear = gold safe haven demand = greed for gold.
    """
    if idx < lookback:
        return 50.0
    window = vix_close.iloc[idx - lookback:idx + 1]
    avg = window.mean()
    std = window.std()
    if std == 0:
        return 50.0
    z = (vix_close.iloc[idx] - avg) / std
    return max(0, min(100, 50 + z * z_mult))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest(data, trading_days, weights, config) -> list[dict]:
    """Run the backtest over all trading days."""
    gld_close = data["GLD"]["Close"]
    gold_close = data["GC=F"]["Close"]
    dxy_close = data["DX=F"]["Close"]
    vix_close = data["^VIX"]["Close"]
    dfii10 = data["DFII10"]

    gld_mult = config.get("gld_mult", 5)
    dxy_mult = config.get("dxy_mult", 15)
    rr_mult = config.get("real_rates_mult", 18.75)
    vix_z_mult = config.get("vix_z_mult", 25)

    results = []
    all_dates = gld_close.index
    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    # Also need index maps for other series (may have different dates)
    gold_dates = {d: i for i, d in enumerate(gold_close.index)}
    dxy_dates = {d: i for i, d in enumerate(dxy_close.index)}
    vix_dates = {d: i for i, d in enumerate(vix_close.index)}

    for day in trading_days:
        if day not in date_to_idx:
            continue
        gld_idx = date_to_idx[day]
        if gld_idx < 200:  # Need 200 days for MA200
            continue

        gold_idx = gold_dates.get(day)
        dxy_idx = dxy_dates.get(day)
        vix_idx = vix_dates.get(day)

        if gold_idx is None or dxy_idx is None or vix_idx is None:
            continue

        comps = []
        comps.append(calc_gld_price(gld_close, gld_idx, gld_mult))
        comps.append(calc_rsi_ma_momentum(gold_close, gold_idx))
        comps.append(calc_dollar_index(dxy_close, dxy_idx, dxy_mult))
        comps.append(calc_real_rates(dfii10, gld_idx, rr_mult))
        comps.append(calc_vix(vix_close, vix_idx, z_mult=vix_z_mult))

        score = sum(c * w for c, w in zip(comps, weights))
        score = max(0, min(100, score))

        results.append({
            "date": day,
            "score": round(score, 1),
            "gld_price": round(float(gld_close.iloc[gld_idx]), 2),
            "components": [round(c, 1) for c in comps],
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def _label(score):
    r = round(score)
    if r <= 25:
        return "Extreme Fear"
    elif r <= 45:
        return "Fear"
    elif r <= 55:
        return "Neutral"
    elif r <= 75:
        return "Greed"
    return "Extreme Greed"


def print_stats(results, config, weights):
    """Print comprehensive backtest statistics."""
    if not results:
        print("No results to analyze.")
        return

    scores = np.array([r["score"] for r in results])
    prices = np.array([r["gld_price"] for r in results])
    dates = [r["date"] for r in results]

    date_start = dates[0].strftime("%Y-%m-%d")
    date_end = dates[-1].strftime("%Y-%m-%d")

    print(f"\n{'=' * 65}")
    print(f"  GOLD BACKTEST ({len(results)} days, {date_start} to {date_end})")
    print(f"{'=' * 65}")

    w_str = " ".join(f"{n}={w:.0%}" for n, w in zip(COMPONENT_NAMES, weights))
    print(f"\nConfig: {w_str}")

    # Correlations
    corr_level = np.corrcoef(scores, prices)[0, 1]
    score_diff = np.diff(scores)
    price_diff = np.diff(prices)
    corr_changes = np.corrcoef(score_diff, price_diff)[0, 1]
    agree = np.sum(np.sign(score_diff) == np.sign(price_diff))
    dir_pct = agree / len(score_diff) * 100

    print(f"\nCorrelation score vs GLD (level):      {corr_level:.3f}")
    print(f"Correlation score vs GLD (changes):    {corr_changes:.3f}")
    print(f"Directional agreement:                 {dir_pct:.1f}%")

    print(f"\nScore: min={scores.min():.1f}  max={scores.max():.1f}  "
          f"mean={scores.mean():.1f}  median={np.median(scores):.1f}  std={scores.std():.1f}")
    print(f"GLD:   min={prices.min():.2f}  max={prices.max():.2f}")

    labels = [_label(s) for s in scores]
    n = len(labels)
    print(f"\nDistribution:")
    for cat in ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]:
        count = labels.count(cat)
        print(f"  {cat:20s} {count / n * 100:5.1f}%  ({count})")

    # Key dates
    date_lookup = {r["date"].strftime("%Y-%m-%d"): r for r in results}
    print(f"\nKey dates:")
    for d, label in KEY_DATES:
        if d in date_lookup:
            r = date_lookup[d]
            print(f"  {d} {label:30s} Score={r['score']:5.1f}  GLD=${r['gld_price']:.2f}")
        else:
            target = pd.Timestamp(d)
            closest = min(dates, key=lambda x: abs(x - target))
            r = date_lookup.get(closest.strftime("%Y-%m-%d"))
            if r and abs(closest - target).days <= 5:
                print(f"  {closest.strftime('%Y-%m-%d')} {label:30s} Score={r['score']:5.1f}  GLD=${r['gld_price']:.2f}  (nearest)")

    # Component statistics
    comp_arrays = np.array([r["components"] for r in results])
    print(f"\nComponent stats:")
    for i, name in enumerate(COMPONENT_NAMES):
        col = comp_arrays[:, i]
        at_0 = np.sum(col <= 0.5) / len(col) * 100
        at_100 = np.sum(col >= 99.5) / len(col) * 100
        print(f"  {name:18s} min={col.min():5.1f}  max={col.max():5.1f}  "
              f"std={col.std():5.1f}  sat={at_0 + at_100:.1f}%")

    # Component correlations with GLD
    print(f"\nComponent correlations with GLD (level):")
    for i, name in enumerate(COMPONENT_NAMES):
        col = comp_arrays[:, i]
        corr = np.corrcoef(col, prices)[0, 1]
        print(f"  {name:18s} {corr:+.3f}  (weight {weights[i]:.0%})")

    # Forward returns analysis (predictive power)
    print(f"\nPredictive power (score vs forward GLD returns):")
    for horizon in [5, 10, 20, 60]:
        if len(scores) <= horizon:
            continue
        fwd_returns = (prices[horizon:] / prices[:-horizon] - 1) * 100
        s = scores[:-horizon]
        corr = np.corrcoef(s, fwd_returns)[0, 1]
        print(f"  Score vs {horizon:2d}d fwd return:  corr={corr:+.3f}  "
              f"({'good contrarian signal' if corr < -0.1 else 'weak signal' if abs(corr) < 0.1 else 'momentum signal'})")

    # Zone analysis: returns by score bucket
    print(f"\nAverage forward returns by score zone (20d):")
    if len(scores) > 20:
        fwd_20d = (prices[20:] / prices[:-20] - 1) * 100
        s = scores[:-20]
        zones = [
            ("Extreme Fear (0-25)", 0, 25),
            ("Fear (25-45)", 25, 45),
            ("Neutral (45-55)", 45, 55),
            ("Greed (55-75)", 55, 75),
            ("Extreme Greed (75-100)", 75, 100),
        ]
        for label, lo, hi in zones:
            mask = (s >= lo) & (s < hi) if hi < 100 else (s >= lo) & (s <= hi)
            if mask.sum() > 0:
                avg_ret = fwd_20d[mask].mean()
                pct_positive = (fwd_20d[mask] > 0).sum() / mask.sum() * 100
                print(f"  {label:30s} n={mask.sum():4d}  avg={avg_ret:+.2f}%  positive={pct_positive:.0f}%")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Gold Fear & Greed Index — Backtest Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backtest_gold.py                                    # Default model
  python backtest_gold.py --weights 0.30,0.25,0.20,0.15,0.10
  python backtest_gold.py --gld-mult 7
  python backtest_gold.py --refresh --years 3
  python backtest_gold.py --compare
        """,
    )
    parser.add_argument("--weights", type=str, default=None,
                        help="Comma-separated weights for 5 components (GLD,RSI/MA,DXY,RealRates,VIX)")
    parser.add_argument("--gld-mult", type=float, default=5,
                        help="GLD price momentum multiplier (default: 5)")
    parser.add_argument("--dxy-mult", type=float, default=15,
                        help="Dollar index multiplier (default: 15)")
    parser.add_argument("--real-rates-mult", type=float, default=18.75,
                        help="Real rates multiplier (default: 18.75)")
    parser.add_argument("--vix-z-mult", type=float, default=25,
                        help="VIX z-score multiplier (default: 25)")
    parser.add_argument("--years", type=int, default=5,
                        help="Number of years to backtest (default: 5)")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-download of all data")
    parser.add_argument("--compare", action="store_true",
                        help="Compare multiple preset configurations")

    args = parser.parse_args()

    if args.weights:
        weights = [float(w) for w in args.weights.split(",")]
        if len(weights) != 5:
            parser.error("--weights must have exactly 5 comma-separated values")
        wsum = sum(weights)
        if abs(wsum - 1.0) > 0.01:
            print(f"Warning: weights sum to {wsum:.2f}, normalizing to 1.0")
            weights = [w / wsum for w in weights]
    else:
        weights = DEFAULT_WEIGHTS

    config = {
        "gld_mult": args.gld_mult,
        "dxy_mult": args.dxy_mult,
        "real_rates_mult": args.real_rates_mult,
        "vix_z_mult": args.vix_z_mult,
    }

    print(f"\nLoading data ({args.years} years)...")
    data, trading_days = load_or_fetch_data(years=args.years, refresh=args.refresh)
    print(f"  Trading days available: {len(trading_days)}")

    if args.compare:
        presets = [
            ("Current model", DEFAULT_WEIGHTS, {}),
            ("GLD mult=7", DEFAULT_WEIGHTS, {"gld_mult": 7}),
            ("GLD mult=3", DEFAULT_WEIGHTS, {"gld_mult": 3}),
            ("DXY mult=10", DEFAULT_WEIGHTS, {"dxy_mult": 10}),
            ("RR=25% GLD=25%", [0.25, 0.25, 0.20, 0.25, 0.05], {}),
        ]

        base = {"gld_mult": 5, "dxy_mult": 15, "real_rates_mult": 18.75, "vix_z_mult": 25}

        print(f"\n{'=' * 75}")
        print(f"  COMPARISON: {len(presets)} configurations")
        print(f"{'=' * 75}")

        header = f"{'Config':25s} {'Corr(lvl)':>10s} {'Corr(chg)':>10s} {'Dir%':>6s} {'Range':>12s} {'Std':>6s}"
        print(f"\n{header}")
        print("-" * len(header))

        for label, w, overrides in presets:
            cfg = {**base, **overrides}
            res = run_backtest(data, trading_days, w, cfg)
            if not res:
                continue
            scores = np.array([r["score"] for r in res])
            prices = np.array([r["gld_price"] for r in res])
            corr_l = np.corrcoef(scores, prices)[0, 1]
            sd, pd_ = np.diff(scores), np.diff(prices)
            corr_c = np.corrcoef(sd, pd_)[0, 1]
            agree = np.sum(np.sign(sd) == np.sign(pd_)) / len(sd) * 100
            print(f"  {label:23s} {corr_l:>10.3f} {corr_c:>10.3f} {agree:>5.1f}% "
                  f"{scores.min():>5.1f}-{scores.max():<5.1f} {scores.std():>5.1f}")

        print()
        return

    results = run_backtest(data, trading_days, weights, config)
    print_stats(results, config, weights)


if __name__ == "__main__":
    main()
