#!/usr/bin/env python3
"""
Calibration script to test different crypto F&G formulas against Alternative.me
Goal: Find weights/formulas that minimize error vs the industry standard
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Alternative.me reference data (January 2026)
REFERENCE_DATA = {
    '2026-01-01': 20, '2026-01-02': 28, '2026-01-03': 29, '2026-01-04': 25,
    '2026-01-05': 26, '2026-01-06': 44, '2026-01-07': 42, '2026-01-08': 28,
    '2026-01-09': 27, '2026-01-10': 25, '2026-01-11': 29, '2026-01-12': 27,
    '2026-01-13': 26, '2026-01-14': 48, '2026-01-15': 61, '2026-01-16': 49,
    '2026-01-17': 50, '2026-01-18': 49, '2026-01-19': 44, '2026-01-20': 32,
    '2026-01-21': 24, '2026-01-22': 20, '2026-01-23': 24, '2026-01-24': 25,
    '2026-01-25': 25, '2026-01-26': 20, '2026-01-27': 29, '2026-01-28': 29,
    '2026-01-29': 26, '2026-01-30': 16,
}


def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    # Convert to Series if needed
    if not isinstance(prices, pd.Series):
        prices = pd.Series(prices)

    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if len(rsi) > 0 else 50


def test_formula(weights, params, debug=False):
    """
    Test a formula configuration against reference data

    weights: dict with component weights
    params: dict with formula parameters (multipliers, caps, etc.)
    """
    # Download data - need extra history for MA200 (need ~220 days before first test date)
    btc = yf.download('BTC-USD', start='2025-04-01', end='2026-02-01', progress=False)
    eth = yf.download('ETH-USD', start='2025-04-01', end='2026-02-01', progress=False)

    if debug:
        print(f"Downloaded BTC data: {len(btc)} rows")
        print(f"BTC date range: {btc.index[0]} to {btc.index[-1]}")

    errors = []
    results = []
    skipped = 0

    for date_str, ref_score in REFERENCE_DATA.items():
        try:
            date = pd.Timestamp(date_str)
            if date not in btc.index:
                skipped += 1
                if debug:
                    print(f"  Skipping {date_str}: not in BTC data")
                continue

            # Get data up to this date
            btc_slice = btc.loc[:date]
            eth_slice = eth.loc[:date]

            if len(btc_slice) < 200:
                skipped += 1
                if debug:
                    print(f"  Skipping {date_str}: only {len(btc_slice)} rows (need 200)")
                continue

            # Calculate components
            components = {}

            # 1. Momentum (RSI + MA)
            if debug:
                print(f"  Processing {date_str}: {len(btc_slice)} rows")

            # Handle MultiIndex columns from yfinance
            close_col = btc_slice['Close'].iloc[:, 0] if isinstance(btc_slice['Close'], pd.DataFrame) else btc_slice['Close']

            rsi = calculate_rsi(close_col)
            ma50 = close_col.rolling(50).mean().iloc[-1]
            ma200 = close_col.rolling(200).mean().iloc[-1]
            current_price = close_col.iloc[-1]

            # RSI component - LOWER BASELINE (was 30, now 50)
            # RSI < 30 = extreme fear, RSI > 70 = extreme greed
            rsi_score = max(0, min(100, (rsi - 50) * params['rsi_mult']))
            components['rsi'] = rsi_score

            # MA component - bear/bull context (LOWER baseline)
            if current_price > ma200:
                # Bull market
                ma_score = 40 if current_price > ma50 else 30
            else:
                # Bear market - MUCH lower
                ma_score = 20 if current_price > ma50 else 10
            components['ma'] = ma_score

            momentum_score = (rsi_score * 0.6 + ma_score * 0.4)
            components['momentum'] = momentum_score

            # 2. Market Context - 30-day trend (LOWER baseline from 50 to 30)
            btc_30d_ago = close_col.iloc[-30] if len(btc_slice) >= 30 else close_col.iloc[0]
            change_30d = ((current_price - btc_30d_ago) / btc_30d_ago) * 100

            # Baseline 30 instead of 50, cap at ±30 points
            context_score = 30 + max(-30, min(30, change_30d * params['context_mult']))
            components['context'] = context_score

            # 3. Volatility - FIXED! High vol = fear (low score)
            returns_14d = close_col.pct_change().tail(14)
            vol_14d = returns_14d.std() * np.sqrt(365) * 100

            # Simple: vol > 40% = fear (0), vol < 20% = greed (100)
            # Linear interpolation between 20% and 40%
            if vol_14d >= 40:
                vol_score = 0
            elif vol_14d <= 20:
                vol_score = 100
            else:
                # Linear: 100 at 20%, 0 at 40%
                vol_score = 100 - ((vol_14d - 20) / 20) * 100

            # Apply multiplier
            vol_score = vol_score * params['vol_mult']
            components['volatility'] = vol_score

            # 4. BTC Dominance (INVERTED - dominance up = fear, LOWER baseline)
            eth_close = eth_slice['Close'].iloc[:, 0] if isinstance(eth_slice['Close'], pd.DataFrame) else eth_slice['Close']

            btc_14d_change = ((current_price - close_col.iloc[-14]) / close_col.iloc[-14]) * 100
            eth_14d_change = ((eth_close.iloc[-1] - eth_close.iloc[-14]) / eth_close.iloc[-14]) * 100

            # If BTC outperforms ETH = dominance up = fear
            rel_performance = btc_14d_change - eth_14d_change
            # LOWER baseline: 30 instead of 50
            dominance_score = 30 - (rel_performance * params['dom_mult'])
            dominance_score = max(0, min(100, dominance_score))
            components['dominance'] = dominance_score

            # 5. Price Momentum - 14-day change (LOWER baseline from 50 to 30)
            change_14d = btc_14d_change
            # Baseline 30, cap at ±30 points
            momentum_14d_score = 30 + max(-30, min(30, change_14d * params['price_mult']))
            components['price_momentum'] = momentum_14d_score

            # Calculate weighted score
            score = (
                components['momentum'] * weights['momentum'] +
                components['context'] * weights['context'] +
                components['volatility'] * weights['volatility'] +
                components['dominance'] * weights['dominance'] +
                components['price_momentum'] * weights['price_momentum']
            )

            error = abs(score - ref_score)
            errors.append(error)
            results.append({
                'date': date_str,
                'ref': ref_score,
                'calc': score,
                'error': error
            })

        except Exception as e:
            if debug:
                print(f"Error on {date_str}: {e}")
                import traceback
                traceback.print_exc()
            continue

    if debug:
        print(f"Processed {len(errors)} dates, skipped {skipped} dates")

    if not errors:
        return float('inf'), []

    avg_error = np.mean(errors)
    return avg_error, results


# Test different configurations
print("Testing different weight configurations...")
print("="*70)

best_error = float('inf')
best_config = None
best_results = None

# Configuration space to test - Smarter, focused search
# Key insight: We're +22 points too optimistic, so we need VERY conservative params
test_configs = []

# Test a smaller, more focused set of configs
# Focus on: very low RSI multipliers, low context multipliers, high dominance weight

# Weight combinations (15 combos)
weight_combos = [
    # Dominance-heavy (capital rotation is key signal)
    {'momentum': 0.10, 'context': 0.20, 'volatility': 0.15, 'dominance': 0.40, 'price_momentum': 0.15},
    {'momentum': 0.10, 'context': 0.25, 'volatility': 0.15, 'dominance': 0.35, 'price_momentum': 0.15},
    {'momentum': 0.15, 'context': 0.20, 'volatility': 0.15, 'dominance': 0.35, 'price_momentum': 0.15},
    # Context-heavy (long-term trend matters)
    {'momentum': 0.10, 'context': 0.30, 'volatility': 0.15, 'dominance': 0.30, 'price_momentum': 0.15},
    {'momentum': 0.10, 'context': 0.35, 'volatility': 0.15, 'dominance': 0.25, 'price_momentum': 0.15},
    # Balanced but conservative
    {'momentum': 0.15, 'context': 0.25, 'volatility': 0.15, 'dominance': 0.30, 'price_momentum': 0.15},
    {'momentum': 0.15, 'context': 0.25, 'volatility': 0.20, 'dominance': 0.25, 'price_momentum': 0.15},
]

# Parameter combinations - Adjusted for new lower baseline formulas
param_combos = [
    # RSI now centered at 50, so higher multipliers needed
    {'rsi_mult': 1.5, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.6},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.6},
    {'rsi_mult': 2.5, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.6},
    # Vary context mult
    {'rsi_mult': 2.0, 'context_mult': 0.6, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.6},
    {'rsi_mult': 2.0, 'context_mult': 1.0, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.6},
    # Vary volatility mult
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.6, 'dom_mult': 2.0, 'price_mult': 0.6},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 1.0, 'dom_mult': 2.0, 'price_mult': 0.6},
    # Vary dominance
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 1.5, 'price_mult': 0.6},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.5, 'price_mult': 0.6},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 3.0, 'price_mult': 0.6},
    # Vary price momentum
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.4},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 0.8},
    {'rsi_mult': 2.0, 'context_mult': 0.8, 'vol_mult': 0.8, 'dom_mult': 2.0, 'price_mult': 1.0},
    # Combinations
    {'rsi_mult': 1.8, 'context_mult': 0.7, 'vol_mult': 0.9, 'dom_mult': 2.2, 'price_mult': 0.7},
    {'rsi_mult': 2.2, 'context_mult': 0.9, 'vol_mult': 0.7, 'dom_mult': 1.8, 'price_mult': 0.5},
]

# Generate all combinations
for weights in weight_combos:
    for params in param_combos:
        test_configs.append({'weights': weights.copy(), 'params': params.copy()})

print(f"Testing {len(test_configs)} configurations (focused search)...")

for i, config in enumerate(test_configs):
    # Progress indicator every 10 configs
    if i % 10 == 0:
        print(f"Testing {i+1}/{len(test_configs)}... (best so far: {best_error:.1f} points)")

    debug = False  # Disable debug for speed
    error, results = test_formula(config['weights'], config['params'], debug=debug)

    if error < best_error:
        best_error = error
        best_config = config
        best_results = results
        print(f"  ✅ Config {i+1}: NEW BEST! Error = {error:.1f} points")

print("\n" + "="*70)
if best_config is None:
    print("❌ NO VALID CONFIGURATION FOUND")
    print("All configurations returned infinite error - check debug output above")
else:
    print(f"BEST CONFIGURATION (Avg Error: {best_error:.1f} points)")
    print("="*70)
    print("\nWeights:")
    for k, v in best_config['weights'].items():
        print(f"  {k}: {v:.2f}")

    print("\nParameters:")
    for k, v in best_config['params'].items():
        print(f"  {k}: {v:.2f}")

    print("\nDetailed Results:")
    print(f"{'Date':<12} {'Ref':>6} {'Calc':>6} {'Error':>6}")
    print("-"*35)
    for r in best_results[:10]:  # Show first 10
        print(f"{r['date']:<12} {r['ref']:>6.0f} {r['calc']:>6.1f} {r['error']:>6.1f}")
    print("...")

    # Save best config
    with open('/tmp/best_crypto_config.json', 'w') as f:
        json.dump(best_config, f, indent=2)
    print("\n✅ Best configuration saved to /tmp/best_crypto_config.json")
