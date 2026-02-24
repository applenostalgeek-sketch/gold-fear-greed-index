#!/usr/bin/env python3
"""
Bonds Fear & Greed Index — Backtest Framework

Standalone tool to test model variants against historical data.
Downloads FRED (yield curve, TIPS) and Yahoo (TLT, LQD, SPY) data,
caches locally, and computes the index with configurable parameters.

Usage:
    python backtest_bonds.py                          # Default model
    python backtest_bonds.py --weights 0.35,0.20,0.15,0.15,0.10,0.05
    python backtest_bonds.py --real-rates-mode delta_30d
    python backtest_bonds.py --duration-mult 12
    python backtest_bonds.py --refresh --years 3
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

FRED_SERIES = {
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "DFII10": "10-Year TIPS Yield (Real Rates)",
}

YAHOO_TICKERS = ["TLT", "LQD", "SPY"]

DEFAULT_WEIGHTS = [0.30, 0.20, 0.20, 0.15, 0.10, 0.05]
COMPONENT_NAMES = [
    "Duration Risk",
    "Yield Curve",
    "Credit Quality",
    "Real Rates",
    "Bond Volatility",
    "Eq vs Bonds",
]

KEY_DATES = [
    ("2022-10-21", "TLT crash bottom"),
    ("2023-10-19", "TLT yearly low"),
    ("2023-03-13", "SVB crisis"),
    ("2020-08-04", "TLT all-time high"),
    ("2022-01-03", "Rate hike cycle start"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATA LAYER
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_fred_series(series_id: str, start: str, end: str) -> pd.Series:
    """Fetch a FRED time series and return as pandas Series (date index, float values)."""
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
        if o["value"] == ".":  # FRED uses "." for missing
            continue
        dates.append(pd.Timestamp(o["date"]))
        values.append(float(o["value"]))

    s = pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id)
    return s


def fetch_yahoo(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch Yahoo Finance OHLCV data."""
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_MAX_AGE_HOURS * 3600


def load_or_fetch_data(years: int = 5, refresh: bool = False) -> dict:
    """
    Load all data sources, using CSV cache when available.
    Returns dict with keys: TLT, LQD, SPY (DataFrames), DGS10, DGS2, DFII10 (Series).
    All aligned to trading days with forward-fill for FRED gaps.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=years * 365 + 90)).strftime("%Y-%m-%d")

    data = {}

    # FRED series
    for sid, desc in FRED_SERIES.items():
        path = _cache_path(sid)
        if not refresh and _cache_fresh(path):
            s = pd.read_csv(path, index_col=0, parse_dates=True).squeeze("columns")
            s.name = sid
            print(f"  [cache] {sid} ({desc}): {len(s)} obs")
        else:
            print(f"  [fetch] {sid} ({desc})...", end=" ")
            s = fetch_fred_series(sid, start_date, end_date)
            s.to_csv(path)
            print(f"{len(s)} obs")
        data[sid] = s

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

    # Align everything to TLT trading days
    trading_days = data["TLT"].index
    for sid in FRED_SERIES:
        # Reindex FRED to trading days, forward-fill weekday gaps
        data[sid] = data[sid].reindex(trading_days, method="ffill")

    # Trim to requested period
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=years * 365))
    trading_days = trading_days[trading_days >= cutoff]

    return data, trading_days


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COMPONENT CALCULATORS (pure functions)
# ═══════════════════════════════════════════════════════════════════════════════

def _pct_change(series, idx, lookback=14):
    """Percentage change over lookback days ending at idx."""
    if idx < lookback:
        return 0.0
    return ((series.iloc[idx] / series.iloc[idx - lookback]) - 1) * 100


def calc_duration_risk(tlt_close, idx, mult=15):
    """Score = 50 + (TLT 14d % change * mult), clamped 0-100."""
    pct = _pct_change(tlt_close, idx, 14)
    return max(0, min(100, 50 + pct * mult))


def calc_yield_curve(dgs10, dgs2, idx, mult=30):
    """Score = 50 + (10Y-2Y spread * mult), clamped 0-100."""
    if pd.isna(dgs10.iloc[idx]) or pd.isna(dgs2.iloc[idx]):
        return 50.0
    spread = dgs10.iloc[idx] - dgs2.iloc[idx]
    return max(0, min(100, 50 + spread * mult))


def calc_credit_quality(lqd_close, tlt_close, idx, mult=20):
    """Score = 50 + ((LQD 14d change - TLT 14d change) * mult), clamped 0-100."""
    lqd_pct = _pct_change(lqd_close, idx, 14)
    tlt_pct = _pct_change(tlt_close, idx, 14)
    spread = lqd_pct - tlt_pct
    return max(0, min(100, 50 + spread * mult))


def calc_real_rates(series, idx, mode="level", center=1.5, mult=20):
    """
    Real rates score. Modes:
      'level':     50 - (DFII10 - center) * mult
      'delta_30d': 50 - (30d change in series * 50)
      'delta_14d': 50 - (14d change in series * 100)
    """
    if pd.isna(series.iloc[idx]):
        return 50.0

    if mode == "level":
        return max(0, min(100, 50 - (series.iloc[idx] - center) * mult))
    elif mode == "delta_30d":
        if idx < 30:
            return 50.0
        delta = series.iloc[idx] - series.iloc[idx - 30]
        return max(0, min(100, 50 - delta * 50))
    elif mode == "delta_14d":
        if idx < 14:
            return 50.0
        delta = series.iloc[idx] - series.iloc[idx - 14]
        return max(0, min(100, 50 - delta * 100))
    else:
        raise ValueError(f"Unknown real_rates mode: {mode}")


def calc_bond_volatility(tlt_close, idx, mult=75):
    """Score = 50 + (1 - vol5d/vol30d) * mult, clamped 0-100."""
    if idx < 30:
        return 50.0
    returns = tlt_close.pct_change()
    vol_5d = returns.iloc[idx - 4 : idx + 1].std() * np.sqrt(252) * 100
    vol_30d = returns.iloc[idx - 29 : idx + 1].std() * np.sqrt(252) * 100
    if vol_30d == 0:
        return 50.0
    ratio = vol_5d / vol_30d
    return max(0, min(100, 50 + (1 - ratio) * mult))


def calc_equity_vs_bonds(tlt_close, spy_close, idx, mult=8):
    """Score = 50 + (TLT 14d - SPY 14d) * mult, clamped 0-100."""
    tlt_pct = _pct_change(tlt_close, idx, 14)
    spy_pct = _pct_change(spy_close, idx, 14)
    relative = tlt_pct - spy_pct
    return max(0, min(100, 50 + relative * mult))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest(data, trading_days, weights, config) -> list[dict]:
    """
    Run the backtest over all trading days.
    Returns list of dicts with date, score, components, tlt_price.
    """
    tlt_close = data["TLT"]["Close"]
    lqd_close = data["LQD"]["Close"]
    spy_close = data["SPY"]["Close"]
    dgs10 = data["DGS10"]
    dgs2 = data["DGS2"]
    dfii10 = data["DFII10"]

    # For real rates, choose source series based on mode
    rr_mode = config.get("real_rates_mode", "level")
    if rr_mode == "level":
        rr_series = dfii10
    else:
        # delta modes use DGS10 (nominal 10Y changes)
        rr_series = dgs10

    rr_center = config.get("real_rates_center", 1.5)
    rr_mult = config.get("real_rates_mult", 20)
    dur_mult = config.get("duration_mult", 15)
    yc_mult = config.get("yield_curve_mult", 30)
    cq_mult = config.get("credit_quality_mult", 20)
    bv_mult = config.get("bond_vol_mult", 75)
    eb_mult = config.get("equity_bonds_mult", 8)

    results = []
    # Build positional index map for fast lookup
    all_dates = tlt_close.index
    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    for day in trading_days:
        if day not in date_to_idx:
            continue
        idx = date_to_idx[day]
        if idx < 30:  # Need at least 30 days of history
            continue

        # Also need idx in FRED-aligned series
        comps = []
        comps.append(calc_duration_risk(tlt_close, idx, dur_mult))
        comps.append(calc_yield_curve(dgs10, dgs2, idx, yc_mult))
        comps.append(calc_credit_quality(lqd_close, tlt_close, idx, cq_mult))
        comps.append(calc_real_rates(rr_series, idx, rr_mode, rr_center, rr_mult))
        comps.append(calc_bond_volatility(tlt_close, idx, bv_mult))
        comps.append(calc_equity_vs_bonds(tlt_close, spy_close, idx, eb_mult))

        score = sum(c * w for c, w in zip(comps, weights))
        score = max(0, min(100, score))

        results.append({
            "date": day,
            "score": round(score, 1),
            "tlt_price": round(float(tlt_close.iloc[idx]), 2),
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
    prices = np.array([r["tlt_price"] for r in results])
    dates = [r["date"] for r in results]

    date_start = dates[0].strftime("%Y-%m-%d")
    date_end = dates[-1].strftime("%Y-%m-%d")

    rr_mode = config.get("real_rates_mode", "level")

    print(f"\n{'=' * 65}")
    print(f"  BONDS BACKTEST ({len(results)} days, {date_start} to {date_end})")
    print(f"{'=' * 65}")

    # Config summary
    w_str = " ".join(
        f"{n}={w:.0%}" for n, w in zip(COMPONENT_NAMES, weights)
    )
    print(f"\nConfig: {w_str}")
    print(f"        RealRates mode={rr_mode}")

    # Correlations
    corr_level = np.corrcoef(scores, prices)[0, 1]
    score_diff = np.diff(scores)
    price_diff = np.diff(prices)
    corr_changes = np.corrcoef(score_diff, price_diff)[0, 1]

    # Directional agreement
    agree = np.sum(np.sign(score_diff) == np.sign(price_diff))
    dir_pct = agree / len(score_diff) * 100

    print(f"\nCorrelation score vs TLT (level):      {corr_level:.3f}")
    print(f"Correlation score vs TLT (changes):    {corr_changes:.3f}")
    print(f"Directional agreement:                 {dir_pct:.1f}%")

    # Score distribution
    print(f"\nScore: min={scores.min():.1f}  max={scores.max():.1f}  "
          f"mean={scores.mean():.1f}  median={np.median(scores):.1f}  std={scores.std():.1f}")
    print(f"TLT:   min={prices.min():.2f}  max={prices.max():.2f}")

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
            print(f"  {d} {label:25s} Score={r['score']:5.1f}  TLT=${r['tlt_price']:.2f}")
        else:
            # Find closest date
            target = pd.Timestamp(d)
            closest = min(dates, key=lambda x: abs(x - target))
            r = date_lookup.get(closest.strftime("%Y-%m-%d"))
            if r and abs(closest - target).days <= 5:
                print(f"  {closest.strftime('%Y-%m-%d')} {label:25s} Score={r['score']:5.1f}  TLT=${r['tlt_price']:.2f}  (nearest)")

    # Component statistics
    comp_arrays = np.array([r["components"] for r in results])
    print(f"\nComponent stats:")
    for i, name in enumerate(COMPONENT_NAMES):
        col = comp_arrays[:, i]
        print(f"  {name:18s} min={col.min():5.1f}  max={col.max():5.1f}  "
              f"mean={col.mean():5.1f}  std={col.std():5.1f}")

    # Component correlations with TLT
    print(f"\nComponent correlations with TLT (level):")
    for i, name in enumerate(COMPONENT_NAMES):
        col = comp_arrays[:, i]
        corr = np.corrcoef(col, prices)[0, 1]
        print(f"  {name:18s} {corr:+.3f}  (weight {weights[i]:.0%})")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Bonds Fear & Greed Index — Backtest Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backtest_bonds.py                                    # Default model
  python backtest_bonds.py --weights 0.35,0.20,0.15,0.15,0.10,0.05
  python backtest_bonds.py --real-rates-mode delta_30d
  python backtest_bonds.py --duration-mult 12 --yield-curve-mult 25
  python backtest_bonds.py --refresh --years 3
  python backtest_bonds.py --compare                          # Compare 4 presets
        """,
    )
    parser.add_argument(
        "--weights", type=str, default=None,
        help="Comma-separated weights for 6 components (Duration,YieldCurve,Credit,RealRates,BondVol,EqBonds)",
    )
    parser.add_argument(
        "--real-rates-mode", choices=["level", "delta_30d", "delta_14d"], default="level",
        help="Real rates calculation mode (default: level)",
    )
    parser.add_argument("--real-rates-center", type=float, default=1.5,
                        help="Center point for level mode (default: 1.5)")
    parser.add_argument("--real-rates-mult", type=float, default=20,
                        help="Multiplier for real rates (default: 20)")
    parser.add_argument("--duration-mult", type=float, default=15,
                        help="Multiplier for duration risk (default: 15)")
    parser.add_argument("--yield-curve-mult", type=float, default=30,
                        help="Multiplier for yield curve (default: 30)")
    parser.add_argument("--credit-quality-mult", type=float, default=20,
                        help="Multiplier for credit quality (default: 20)")
    parser.add_argument("--bond-vol-mult", type=float, default=75,
                        help="Multiplier for bond volatility (default: 75)")
    parser.add_argument("--equity-bonds-mult", type=float, default=8,
                        help="Multiplier for equity vs bonds (default: 8)")
    parser.add_argument("--years", type=int, default=5,
                        help="Number of years to backtest (default: 5)")
    parser.add_argument("--refresh", action="store_true",
                        help="Force re-download of all data")
    parser.add_argument("--compare", action="store_true",
                        help="Compare multiple preset configurations")

    args = parser.parse_args()

    # Parse weights
    if args.weights:
        weights = [float(w) for w in args.weights.split(",")]
        if len(weights) != 6:
            parser.error("--weights must have exactly 6 comma-separated values")
        wsum = sum(weights)
        if abs(wsum - 1.0) > 0.01:
            print(f"Warning: weights sum to {wsum:.2f}, normalizing to 1.0")
            weights = [w / wsum for w in weights]
    else:
        weights = DEFAULT_WEIGHTS

    config = {
        "real_rates_mode": args.real_rates_mode,
        "real_rates_center": args.real_rates_center,
        "real_rates_mult": args.real_rates_mult,
        "duration_mult": args.duration_mult,
        "yield_curve_mult": args.yield_curve_mult,
        "credit_quality_mult": args.credit_quality_mult,
        "bond_vol_mult": args.bond_vol_mult,
        "equity_bonds_mult": args.equity_bonds_mult,
    }

    # Fetch data
    print(f"\nLoading data ({args.years} years)...")
    data, trading_days = load_or_fetch_data(years=args.years, refresh=args.refresh)
    print(f"  Trading days available: {len(trading_days)}")

    if args.compare:
        # Compare multiple presets
        presets = [
            ("Current model", DEFAULT_WEIGHTS, {"real_rates_mode": "level", "duration_mult": 15,
             "yield_curve_mult": 30, "credit_quality_mult": 20, "real_rates_center": 1.5,
             "real_rates_mult": 20, "bond_vol_mult": 75, "equity_bonds_mult": 8}),
            ("RR delta_30d", DEFAULT_WEIGHTS, {**config, "real_rates_mode": "delta_30d"}),
            ("RR delta_14d", DEFAULT_WEIGHTS, {**config, "real_rates_mode": "delta_14d"}),
            ("Duration 35%", [0.35, 0.20, 0.15, 0.15, 0.10, 0.05],
             {"real_rates_mode": "level", "duration_mult": 15, "yield_curve_mult": 30,
              "credit_quality_mult": 20, "real_rates_center": 1.5, "real_rates_mult": 20,
              "bond_vol_mult": 75, "equity_bonds_mult": 8}),
        ]

        print(f"\n{'=' * 75}")
        print(f"  COMPARISON: {len(presets)} configurations")
        print(f"{'=' * 75}")

        header = f"{'Config':25s} {'Corr(lvl)':>10s} {'Corr(chg)':>10s} {'Dir%':>6s} {'Range':>12s} {'Std':>6s}"
        print(f"\n{header}")
        print("-" * len(header))

        for label, w, cfg in presets:
            res = run_backtest(data, trading_days, w, cfg)
            if not res:
                continue
            scores = np.array([r["score"] for r in res])
            prices = np.array([r["tlt_price"] for r in res])
            corr_l = np.corrcoef(scores, prices)[0, 1]
            sd, pd_ = np.diff(scores), np.diff(prices)
            corr_c = np.corrcoef(sd, pd_)[0, 1]
            agree = np.sum(np.sign(sd) == np.sign(pd_)) / len(sd) * 100
            print(f"  {label:23s} {corr_l:>10.3f} {corr_c:>10.3f} {agree:>5.1f}% "
                  f"{scores.min():>5.1f}-{scores.max():<5.1f} {scores.std():>5.1f}")

        print()
        return

    # Single run
    results = run_backtest(data, trading_days, weights, config)
    print_stats(results, config, weights)


if __name__ == "__main__":
    main()
