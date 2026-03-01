"""
Rebuild 5 years of F&G index history for all 4 markets.
Standalone script — does NOT modify any existing files.

Fetches all price data once, computes scores via vectorized pandas,
saves to separate files: data/history-5y-{market}.json

Run: python3 rebuild_5y.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime, timedelta

YEARS = 6  # Fetch 6 years to have 200-day MA buffer for 5 years of scores

FRED_API_KEY = '6f92656f50613f5438ddc820ff3ee3d8'
FRED_SERIES = ['DGS10', 'DGS2', 'DFII10']

SYMBOLS = [
    'BTC-USD', 'ETH-USD',
    'GC=F', 'GLD', 'SPY', '^VIX', 'DX-Y.NYB', '^TNX',
    'RSP', 'HYG', 'TLT', 'QQQ', 'XLP', 'LQD', 'SHY'
]


def clamp(series):
    """Clamp a pandas Series to 0-100."""
    return series.clip(0, 100)


def compute_rsi(close, period=14):
    """Compute RSI as a full pandas Series."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def fetch_fred_series(series_id, api_key, start, end):
    """Fetch a FRED series and return as pd.Series indexed by date."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
        'observation_start': start.strftime('%Y-%m-%d'),
        'observation_end': end.strftime('%Y-%m-%d'),
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        obs = resp.json().get('observations', [])
        records = {}
        for o in obs:
            if o['value'] != '.':
                records[pd.Timestamp(o['date'])] = float(o['value'])
        series = pd.Series(records).sort_index()
        print(f"  FRED {series_id}: {len(series)} observations loaded")
        return series
    except Exception as e:
        print(f"  FRED {series_id} ERROR: {e}")
        return pd.Series(dtype=float)


def fetch_all():
    """Fetch all Yahoo symbols + FRED series for 6 years.
    Returns dict of symbol -> DataFrame/Series.
    Normalizes all indices to date-only (no timezone) for proper alignment."""
    end = datetime.now()
    start = end - timedelta(days=YEARS * 365)
    data = {}

    # Yahoo Finance
    for sym in SYMBOLS:
        print(f"  Fetching {sym}...")
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
            if len(hist) > 0:
                # Normalize index to date-only for cross-symbol alignment
                hist.index = hist.index.tz_localize(None).normalize()
                # Remove duplicate dates (keep last)
                hist = hist[~hist.index.duplicated(keep='last')]
                data[sym] = hist
                print(f"    -> {len(hist)} days")
            else:
                print(f"    -> WARNING: no data")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    # FRED series
    print("\nFetching FRED data...")
    for series_id in FRED_SERIES:
        fred_data = fetch_fred_series(series_id, FRED_API_KEY, start, end)
        if len(fred_data) > 0:
            data[f'FRED_{series_id}'] = fred_data

    return data


def get_label(score):
    if score <= 25:
        return "Extreme Fear"
    elif score <= 45:
        return "Fear"
    elif score <= 55:
        return "Neutral"
    elif score <= 75:
        return "Greed"
    else:
        return "Extreme Greed"


# ========================================
# GOLD
# ========================================
def calc_gold(data):
    print("\nCalculating GOLD scores...")
    gld = data['GLD']['Close']
    gc = data.get('GC=F', {})
    vix = data['^VIX']['Close']
    dxy = data['DX-Y.NYB']['Close']
    tnx = data['^TNX']['Close']
    dfii10 = data.get('FRED_DFII10', pd.Series(dtype=float))

    # 1. GLD Price Momentum (30%)
    gld_mom_14d = (gld / gld.shift(14) - 1) * 100
    gld_price_score = clamp(50 + gld_mom_14d * 5)

    # 2. Momentum RSI/MA (25%)
    rsi = compute_rsi(gld, 14)
    ma50 = gld.rolling(50).mean()
    ma200 = gld.rolling(200).mean()

    ma50_pct = ((gld - ma50) / ma50) * 100
    ma50_contrib = (ma50_pct * 1.5).clip(-15, 15)

    ma200_pct = ((gld - ma200) / ma200) * 100
    ma200_contrib = (ma200_pct * 0.5).clip(-10, 10)

    rsi_contrib = ((rsi - 50) * 0.5).clip(-25, 25)
    momentum_score = clamp(50 + ma50_contrib + ma200_contrib + rsi_contrib)

    # 3. Dollar Index (20%)
    dxy_change_14d = (dxy / dxy.shift(14) - 1) * 100
    dollar_score = clamp(50 - dxy_change_14d * 15)

    # 4. Real Rates (15%) — FRED DFII10 (TIPS), fallback Yahoo ^TNX
    if len(dfii10) > 0:
        # Align FRED DFII10 to GLD trading days (forward-fill for weekends/holidays)
        dfii10_aligned = dfii10.reindex(gld.index, method='ffill')
        real_rates_score = clamp(75 - (dfii10_aligned * 18.75))
        print("  Gold Real Rates: using FRED DFII10")
    else:
        real_rates_score = clamp(100 - (tnx - 2) * 25)
        print("  Gold Real Rates: FRED unavailable, using Yahoo ^TNX fallback")

    # 5. VIX (10%)
    vix_avg = vix.rolling(63).mean()  # ~3 months
    vix_std = vix.rolling(63).std()
    vix_z = (vix - vix_avg) / vix_std
    vix_score = clamp(50 + vix_z * 25)

    # Weighted average
    # Align all series to common dates
    df = pd.DataFrame({
        'gld_price': gld_price_score,
        'momentum': momentum_score,
        'dollar': dollar_score,
        'real_rates': real_rates_score,
        'vix': vix_score,
    }).dropna()

    df['score'] = (
        df['gld_price'] * 0.30 +
        df['momentum'] * 0.25 +
        df['dollar'] * 0.20 +
        df['real_rates'] * 0.15 +
        df['vix'] * 0.10
    ).round(1)

    return df['score']


# ========================================
# STOCKS
# ========================================
def calc_stocks(data):
    print("\nCalculating STOCKS scores...")
    spy = data['SPY']['Close']
    vix = data['^VIX']['Close']
    rsp = data['RSP']['Close']
    hyg = data['HYG']['Close']
    tlt = data['TLT']['Close']
    qqq = data['QQQ']['Close']
    xlp = data['XLP']['Close']

    # 1. Price Strength (20%)
    spy_mom = (spy / spy.shift(14) - 1) * 100
    price_score = clamp(50 + spy_mom * 8)

    # 2. VIX continuous (20%)
    vix_score = clamp(90 - (vix - 10) * 3.2)

    # 3. Momentum RSI/MA (15%)
    rsi = compute_rsi(spy, 14)
    ma50 = spy.rolling(50).mean()
    ma200 = spy.rolling(200).mean()

    above_50 = spy > ma50
    above_200 = spy > ma200
    ma_score = pd.Series(25.0, index=spy.index)
    ma_score[above_200 & ~above_50] = 40.0
    ma_score[above_50 & ~above_200] = 60.0
    ma_score[above_50 & above_200] = 75.0

    momentum_score = clamp(rsi * 0.7 + ma_score * 0.3)

    # 4. Market Participation (15%)
    spy_ret = (spy / spy.shift(14) - 1) * 100
    rsp_ret = (rsp / rsp.shift(14) - 1) * 100
    participation_score = clamp(50 + (rsp_ret - spy_ret) * 18)

    # 5. Junk Bonds (10%)
    hyg_ret = (hyg / hyg.shift(14) - 1) * 100
    tlt_ret = (tlt / tlt.shift(14) - 1) * 100
    junk_score = clamp(50 + (hyg_ret - tlt_ret) * 14)

    # 6. Safe Haven (10%)
    tlt_mom = (tlt / tlt.shift(14) - 1) * 100
    safe_haven_score = clamp(50 - tlt_mom * 8)

    # 7. Sector Rotation (10%)
    qqq_ret = (qqq / qqq.shift(14) - 1) * 100
    xlp_ret = (xlp / xlp.shift(14) - 1) * 100
    sector_score = clamp(50 + (qqq_ret - xlp_ret) * 5)

    df = pd.DataFrame({
        'price': price_score,
        'vix': vix_score,
        'momentum': momentum_score,
        'participation': participation_score,
        'junk': junk_score,
        'safe_haven': safe_haven_score,
        'sector': sector_score,
    }).dropna()

    df['score'] = (
        df['price'] * 0.20 +
        df['vix'] * 0.20 +
        df['momentum'] * 0.15 +
        df['participation'] * 0.15 +
        df['junk'] * 0.10 +
        df['safe_haven'] * 0.10 +
        df['sector'] * 0.10
    ).round(1)

    return df['score']


# ========================================
# CRYPTO
# ========================================
def calc_crypto(data):
    print("\nCalculating CRYPTO scores...")
    btc = data['BTC-USD']['Close']
    eth = data['ETH-USD']['Close']
    btc_vol = data['BTC-USD']['Volume']

    # 1. Context (30%)
    btc_30d = (btc / btc.shift(30) - 1) * 100
    context_score = clamp(50 + (btc_30d * 1.7).clip(-50, 50))

    # 2. Momentum RSI/MA (20%)
    rsi = compute_rsi(btc, 14)
    ma50 = btc.rolling(50).mean()
    ma200 = btc.rolling(200).mean()

    above_50 = btc > ma50
    above_200 = btc > ma200
    ma_score = pd.Series(20.0, index=btc.index)
    ma_score[above_50 & ~above_200] = 40.0
    ma_score[above_200 & ~above_50] = 60.0
    ma_score[above_50 & above_200] = 80.0

    rsi_clamped = rsi.clip(0, 100)
    momentum_score = clamp(rsi_clamped * 0.6 + ma_score * 0.4)

    # 3. BTC Dominance (20%) — inverted
    btc_ret = (btc / btc.shift(14) - 1) * 100
    eth_ret = (eth / eth.shift(14) - 1) * 100
    dominance_score = clamp(50 - (btc_ret - eth_ret) * 3.0)

    # 4. Volume Trend (15%)
    vol_30d = btc_vol.rolling(30).mean()
    vol_7d = btc_vol.rolling(7).mean()
    vol_ratio = vol_7d / vol_30d
    price_dir = (btc > btc.shift(7)).astype(float) * 2 - 1  # +1 or -1
    volume_score = clamp(50 + (vol_ratio - 1) * 50 * price_dir)

    # 5. Volatility (15%)
    btc_returns = btc.pct_change()
    vol_14d = btc_returns.rolling(14).std() * np.sqrt(365) * 100
    # vol >= 80 → 0, vol <= 25 → 100, linear between (matches live: 25-80% range)
    volatility_score = clamp(100 - ((vol_14d - 25) / 55) * 100)

    df = pd.DataFrame({
        'context': context_score,
        'momentum': momentum_score,
        'dominance': dominance_score,
        'volume': volume_score,
        'volatility': volatility_score,
    }).dropna()

    df['score'] = (
        df['context'] * 0.30 +
        df['momentum'] * 0.20 +
        df['dominance'] * 0.20 +
        df['volume'] * 0.15 +
        df['volatility'] * 0.15
    ).round(1)

    return df['score']


# ========================================
# BONDS
# ========================================
def calc_bonds(data):
    print("\nCalculating BONDS scores...")
    tlt = data['TLT']['Close']
    hyg = data['HYG']['Close']
    lqd = data['LQD']['Close']
    spy = data['SPY']['Close']
    tnx = data['^TNX']['Close']
    dgs10 = data.get('FRED_DGS10', pd.Series(dtype=float))
    dgs2 = data.get('FRED_DGS2', pd.Series(dtype=float))
    dfii10 = data.get('FRED_DFII10', pd.Series(dtype=float))

    # 1. Duration Risk / TLT Momentum (30% — PRIMARY)
    tlt_mom = (tlt / tlt.shift(15) - 1) * 100
    duration_score = clamp(50 + tlt_mom * 12)

    # 2. Credit Quality (20%) — V3: HYG vs LQD (credit risk appetite)
    hyg_change = (hyg / hyg.shift(15) - 1) * 100
    lqd_change = (lqd / lqd.shift(15) - 1) * 100
    credit_score = clamp(50 + (hyg_change - lqd_change) * 20)

    # 3. Yield Curve (20%) — FRED DGS10 - DGS2, fallback Yahoo
    if len(dgs10) > 0 and len(dgs2) > 0:
        # Align FRED to TLT trading days
        dgs10_aligned = dgs10.reindex(tlt.index, method='ffill')
        dgs2_aligned = dgs2.reindex(tlt.index, method='ffill')
        spread = dgs10_aligned - dgs2_aligned
        yield_curve_score = clamp(50 + spread * 30)
        print("  Bonds Yield Curve: using FRED DGS10-DGS2")
    else:
        # Fallback: Yahoo ^TNX only (no ^IRX needed)
        yield_curve_score = clamp(50 + (tnx - 4.0) * 30)
        print("  Bonds Yield Curve: FRED unavailable, using Yahoo fallback")

    # 4. Real Rates (15%) — FRED DFII10 (TIPS), fallback Yahoo ^TNX
    if len(dfii10) > 0:
        dfii10_aligned = dfii10.reindex(tlt.index, method='ffill')
        real_rates_score = clamp(50 - (dfii10_aligned - 1.5) * 20)
        print("  Bonds Real Rates: using FRED DFII10")
    else:
        real_rates_score = clamp(50 - (tnx - 4.0) * 20)
        print("  Bonds Real Rates: FRED unavailable, using Yahoo ^TNX fallback")

    # 5. Bond Volatility (10%)
    tlt_returns = tlt.pct_change()
    vol_5d = tlt_returns.rolling(5).std() * np.sqrt(252) * 100
    vol_30d = tlt_returns.rolling(30).std() * np.sqrt(252) * 100
    vol_ratio = vol_5d / vol_30d
    bond_vol_score = clamp(50 + (1 - vol_ratio) * 60)

    # 6. Equity vs Bonds (5%)
    tlt_14d = (tlt / tlt.shift(15) - 1) * 100
    spy_14d = (spy / spy.shift(15) - 1) * 100
    equity_vs_bonds_score = clamp(50 + (tlt_14d - spy_14d) * 8)

    df = pd.DataFrame({
        'duration': duration_score,
        'yield_curve': yield_curve_score,
        'credit': credit_score,
        'real_rates': real_rates_score,
        'bond_vol': bond_vol_score,
        'eq_vs_bonds': equity_vs_bonds_score,
    }).dropna()

    df['score'] = (
        df['duration'] * 0.30 +
        df['yield_curve'] * 0.20 +
        df['credit'] * 0.20 +
        df['real_rates'] * 0.15 +
        df['bond_vol'] * 0.10 +
        df['eq_vs_bonds'] * 0.05
    ).round(1)

    return df['score']


# ========================================
# MAIN
# ========================================
def save_history(scores, name, price_symbol, data):
    """Save score history + aligned prices to JSON."""
    prices = data[price_symbol]['Close']

    history = []
    for date, score in scores.items():
        d = date.strftime('%Y-%m-%d')
        price = prices.get(date)
        entry = {'date': d, 'score': float(score), 'label': get_label(score)}
        if price is not None:
            entry['price'] = round(float(price), 2)
        history.append(entry)

    # Trim to ~5 years
    cutoff = datetime.now() - timedelta(days=5 * 365)
    history = [h for h in history if h['date'] >= cutoff.strftime('%Y-%m-%d')]

    output = {
        'asset': name,
        'generated': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_days': len(history),
        'date_range': {
            'start': history[0]['date'] if history else None,
            'end': history[-1]['date'] if history else None,
        },
        'score_stats': {
            'min': round(min(h['score'] for h in history), 1) if history else None,
            'max': round(max(h['score'] for h in history), 1) if history else None,
            'avg': round(sum(h['score'] for h in history) / len(history), 1) if history else None,
        },
        'history': history,
    }

    path = f'data/history-5y-{name}.json'
    with open(path, 'w') as f:
        json.dump(output, f)
    print(f"  -> Saved {path} ({len(history)} days)")

    # Quick stats
    scores_list = [h['score'] for h in history]
    ef_days = sum(1 for s in scores_list if s <= 25)
    eg_days = sum(1 for s in scores_list if s > 75)
    print(f"     Range: {output['score_stats']['min']} - {output['score_stats']['max']} (avg: {output['score_stats']['avg']})")
    print(f"     Extreme Fear days: {ef_days}, Extreme Greed days: {eg_days}")


def main():
    print("=" * 60)
    print("5-YEAR REBUILD — Fear & Greed Index History")
    print("=" * 60)
    print(f"\nFetching {len(SYMBOLS)} symbols ({YEARS} years of data)...\n")

    data = fetch_all()

    # Check we have minimum data
    missing = [s for s in SYMBOLS if s not in data]
    if missing:
        print(f"\nWARNING: Missing symbols: {missing}")

    # Calculate and save each market
    try:
        gold_scores = calc_gold(data)
        save_history(gold_scores, 'gold', 'GLD', data)
    except Exception as e:
        print(f"  GOLD ERROR: {e}")

    try:
        stocks_scores = calc_stocks(data)
        save_history(stocks_scores, 'stocks', 'SPY', data)
    except Exception as e:
        print(f"  STOCKS ERROR: {e}")

    try:
        crypto_scores = calc_crypto(data)
        save_history(crypto_scores, 'crypto', 'BTC-USD', data)
    except Exception as e:
        print(f"  CRYPTO ERROR: {e}")

    try:
        bonds_scores = calc_bonds(data)
        save_history(bonds_scores, 'bonds', 'TLT', data)
    except Exception as e:
        print(f"  BONDS ERROR: {e}")

    print("\n" + "=" * 60)
    print("Done! Files saved to data/history-5y-*.json")
    print("=" * 60)


if __name__ == '__main__':
    main()
