#!/usr/bin/env python3
"""
Backtest analysis for Gold Fear & Greed Index
Validates the predictive power of extreme readings
"""

import json
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


def load_index_data(filepath: str = 'data/gold-fear-greed.json') -> Dict:
    """Load the index data from JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)


def get_gold_prices(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch gold prices from Yahoo Finance"""
    gold = yf.Ticker("GC=F")
    df = gold.history(start=start_date, end=end_date)
    return df


def calculate_forward_returns(
    history: List[Dict],
    gold_prices: pd.DataFrame,
    threshold_high: float = 75,
    threshold_low: float = 35
) -> Dict:
    """
    Calculate forward returns after extreme readings

    Args:
        history: List of {date, score} dictionaries
        gold_prices: DataFrame with gold prices
        threshold_high: Score above which we consider "Extreme Greed"
        threshold_low: Score below which we consider "Extreme Fear"

    Returns:
        Dictionary with backtest results
    """
    extreme_greed_signals = []
    extreme_fear_signals = []

    for i, entry in enumerate(history):
        date = entry['date']
        score = entry['score']

        # Skip if we don't have enough future data
        if i < 30:
            continue

        try:
            # Get price on signal date (make timezone-aware to match yfinance)
            signal_date = pd.Timestamp(date).tz_localize('UTC')

            # Find nearest available date in price data
            if signal_date not in gold_prices.index:
                nearest_idx = gold_prices.index.asof(signal_date)
                if pd.isna(nearest_idx):
                    continue
                signal_date = nearest_idx

            signal_price = gold_prices.loc[signal_date, 'Close']

            # Calculate forward returns (7, 14, 30 days)
            returns = {}
            for days in [7, 14, 30]:
                if i >= days:
                    future_date = history[i - days]['date']
                    future_date_ts = pd.Timestamp(future_date).tz_localize('UTC')

                    if future_date_ts not in gold_prices.index:
                        nearest_idx = gold_prices.index.asof(future_date_ts)
                        if pd.isna(nearest_idx):
                            continue
                        future_date_ts = nearest_idx

                    future_price = gold_prices.loc[future_date_ts, 'Close']
                    returns[f'{days}d'] = ((future_price - signal_price) / signal_price) * 100

            # Categorize signal
            if score >= threshold_high:
                extreme_greed_signals.append({
                    'date': date,
                    'score': score,
                    'price': float(signal_price),
                    **returns
                })
            elif score <= threshold_low:
                extreme_fear_signals.append({
                    'date': date,
                    'score': score,
                    'price': float(signal_price),
                    **returns
                })

        except Exception as e:
            print(f"Error processing {date}: {e}")
            continue

    # Calculate statistics
    def calc_stats(signals: List[Dict], timeframe: str) -> Dict:
        if not signals:
            return {'count': 0, 'avg_return': 0, 'win_rate': 0, 'median_return': 0}

        returns = [s[timeframe] for s in signals if timeframe in s]
        if not returns:
            return {'count': 0, 'avg_return': 0, 'win_rate': 0, 'median_return': 0}

        wins = sum(1 for r in returns if r > 0)

        return {
            'count': len(returns),
            'avg_return': sum(returns) / len(returns),
            'win_rate': (wins / len(returns)) * 100,
            'median_return': sorted(returns)[len(returns) // 2],
            'best_return': max(returns),
            'worst_return': min(returns)
        }

    return {
        'extreme_greed': {
            'count': len(extreme_greed_signals),
            'threshold': threshold_high,
            'description': 'Score ≥ 75 → Expected: Price correction',
            '7d': calc_stats(extreme_greed_signals, '7d'),
            '14d': calc_stats(extreme_greed_signals, '14d'),
            '30d': calc_stats(extreme_greed_signals, '30d'),
            'signals': extreme_greed_signals[:5]  # Last 5 signals
        },
        'extreme_fear': {
            'count': len(extreme_fear_signals),
            'threshold': threshold_low,
            'description': 'Score ≤ 35 → Expected: Price rally',
            '7d': calc_stats(extreme_fear_signals, '7d'),
            '14d': calc_stats(extreme_fear_signals, '14d'),
            '30d': calc_stats(extreme_fear_signals, '30d'),
            'signals': extreme_fear_signals[:5]  # Last 5 signals
        },
        'analysis_period': {
            'start': history[-1]['date'],
            'end': history[0]['date'],
            'total_days': len(history)
        }
    }


def main():
    """Generate backtest analysis"""
    print("🔍 Starting backtest analysis...\n")

    # Load index data
    print("📂 Loading index data...")
    data = load_index_data()
    history = data['history']
    print(f"   Loaded {len(history)} days of history")

    # Fetch gold prices
    print("\n📊 Fetching gold price data...")
    start_date = history[-1]['date']
    end_date = history[0]['date']
    gold_prices = get_gold_prices(start_date, end_date)
    print(f"   Fetched {len(gold_prices)} price points")

    # Calculate backtest
    print("\n🧮 Calculating forward returns...")
    backtest = calculate_forward_returns(history, gold_prices)

    # Print summary
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)

    print(f"\n📅 Analysis Period: {backtest['analysis_period']['start']} → {backtest['analysis_period']['end']}")
    print(f"   Total: {backtest['analysis_period']['total_days']} days")

    print(f"\n🔴 EXTREME GREED (Score ≥ {backtest['extreme_greed']['threshold']})")
    print(f"   Total signals: {backtest['extreme_greed']['count']}")
    for period in ['7d', '14d', '30d']:
        stats = backtest['extreme_greed'][period]
        if stats['count'] > 0:
            print(f"\n   {period.upper()} Forward Returns:")
            print(f"      Avg: {stats['avg_return']:+.2f}%")
            print(f"      Median: {stats['median_return']:+.2f}%")
            print(f"      Win Rate: {stats['win_rate']:.1f}%")
            print(f"      Range: {stats['worst_return']:+.2f}% to {stats['best_return']:+.2f}%")

    print(f"\n🟢 EXTREME FEAR (Score ≤ {backtest['extreme_fear']['threshold']})")
    print(f"   Total signals: {backtest['extreme_fear']['count']}")
    for period in ['7d', '14d', '30d']:
        stats = backtest['extreme_fear'][period]
        if stats['count'] > 0:
            print(f"\n   {period.upper()} Forward Returns:")
            print(f"      Avg: {stats['avg_return']:+.2f}%")
            print(f"      Median: {stats['median_return']:+.2f}%")
            print(f"      Win Rate: {stats['win_rate']:.1f}%")
            print(f"      Range: {stats['worst_return']:+.2f}% to {stats['best_return']:+.2f}%")

    # Save to file
    output_file = 'data/backtest.json'
    with open(output_file, 'w') as f:
        json.dump(backtest, f, indent=2)

    print(f"\n✅ Backtest saved to {output_file}")
    print("="*60)


if __name__ == "__main__":
    main()
