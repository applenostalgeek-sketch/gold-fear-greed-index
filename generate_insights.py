"""
Generate dynamic insights JSON for each market.
Reads F&G history, fetches prices via yfinance, computes:
- Pearson correlation (90d + full history)
- Backtest at Extreme Fear / Extreme Greed thresholds
- Score statistics
- Dynamic signal texts

Run: python generate_insights.py
Output: data/insights-crypto.json, data/insights-gold.json,
        data/insights-stocks.json, data/insights-bonds.json
"""

import json
import sys
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

USE_5Y = '--5y' in sys.argv

MARKETS = {
    'crypto': {'fg_file': 'data/crypto-fear-greed.json', 'fg_5y': 'data/history-5y-crypto.json', 'price_symbol': 'BTC-USD', 'price_label': 'BTC'},
    'gold':   {'fg_file': 'data/gold-fear-greed.json',   'fg_5y': 'data/history-5y-gold.json',   'price_symbol': 'GLD',     'price_label': 'GLD'},
    'stocks': {'fg_file': 'data/stocks-fear-greed.json',  'fg_5y': 'data/history-5y-stocks.json',  'price_symbol': 'SPY',     'price_label': 'SPY'},
    'bonds':  {'fg_file': 'data/bonds-fear-greed.json',   'fg_5y': 'data/history-5y-bonds.json',   'price_symbol': 'TLT',     'price_label': 'TLT'},
}

FEAR_THRESHOLD = 25
GREED_THRESHOLD = 75


def load_fg_history(path):
    """Load F&G JSON and return sorted history list + current score."""
    with open(path) as f:
        data = json.load(f)
    history = sorted(data.get('history', []), key=lambda x: x['date'])
    return history, data.get('score'), data.get('label')


def load_5y_history(path):
    """Load 5-year rebuild JSON. Returns history list + current score/label."""
    with open(path) as f:
        data = json.load(f)
    history = data.get('history', [])
    if not history:
        return [], None, None
    last = history[-1]
    return history, last['score'], last.get('label', get_label_for_score(last['score']))


def get_label_for_score(score):
    if score <= 25: return "Extreme Fear"
    if score <= 45: return "Fear"
    if score <= 55: return "Neutral"
    if score <= 75: return "Greed"
    return "Extreme Greed"


def fetch_prices(symbol, days=500):
    """Fetch price history via yfinance. Returns dict {date_str: close_price}."""
    end = datetime.now()
    start = end - timedelta(days=days)
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))
    prices = {}
    for date, row in hist.iterrows():
        prices[date.strftime('%Y-%m-%d')] = round(float(row['Close']), 2)
    return prices


def align_data(fg_history, price_map):
    """Align F&G scores with prices by date. Returns list of {date, score, price}."""
    aligned = []
    for entry in fg_history:
        d = entry['date']
        if d in price_map:
            aligned.append({'date': d, 'score': entry['score'], 'price': price_map[d]})
    return aligned


def pearson_r(scores, prices):
    """Compute Pearson correlation coefficient. Returns float or None."""
    if len(scores) < 5:
        return None
    scores = np.array(scores, dtype=float)
    prices = np.array(prices, dtype=float)
    if np.std(scores) == 0 or np.std(prices) == 0:
        return None
    return round(float(np.corrcoef(scores, prices)[0, 1]), 3)


def correlation_label(r):
    """Human-readable label for correlation value."""
    if r is None:
        return "Insufficient data"
    ar = abs(r)
    direction = "positive" if r > 0 else "negative" if r < 0 else ""
    if ar >= 0.7:
        return f"Strong {direction}"
    if ar >= 0.4:
        return f"Moderate {direction}"
    if ar >= 0.2:
        return f"Weak {direction}"
    return "Negligible"


def find_episodes(aligned, threshold, direction='below'):
    """
    Find episodes where score crosses a threshold.
    direction='below' for Extreme Fear, 'above' for Extreme Greed.
    Returns list of episodes, each = {start_idx, date, score, price}.
    Only the first day of each consecutive episode is kept.
    """
    episodes = []
    in_episode = False

    for i, point in enumerate(aligned):
        crossed = point['score'] < threshold if direction == 'below' else point['score'] > threshold
        if crossed and not in_episode:
            episodes.append({
                'idx': i,
                'date': point['date'],
                'score': point['score'],
                'price': point['price']
            })
            in_episode = True
        elif not crossed:
            in_episode = False

    return episodes


def compute_returns(episodes, aligned, horizons=[30, 60, 90]):
    """
    For each episode, compute price return at +N trading days.
    Returns dict of horizon -> {returns: [...], win_count, total}.
    """
    results = {}
    for h in horizons:
        returns = []
        for ep in episodes:
            future_idx = ep['idx'] + h
            if future_idx < len(aligned):
                entry_price = ep['price']
                future_price = aligned[future_idx]['price']
                ret = round((future_price - entry_price) / entry_price * 100, 1)
                returns.append(ret)
        results[h] = {
            'returns': returns,
            'avg': round(np.mean(returns), 1) if returns else None,
            'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100) if returns else None,
            'count': len(returns)
        }
    return results


def compute_score_stats(fg_history, current_score):
    """Compute min, max, avg, percentile of current score."""
    scores = [h['score'] for h in fg_history]
    if not scores:
        return None
    percentile = round(sum(1 for s in scores if s <= current_score) / len(scores) * 100)

    # Percentile label
    if percentile >= 95:
        plabel = "Near 12-month high"
    elif percentile >= 85:
        plabel = "Upper range"
    elif percentile <= 5:
        plabel = "Near 12-month low"
    elif percentile <= 15:
        plabel = "Lower range"
    else:
        plabel = None

    return {
        'min': round(min(scores), 1),
        'max': round(max(scores), 1),
        'avg': round(np.mean(scores), 1),
        'current': current_score,
        'current_percentile': percentile,
        'percentile_label': plabel,
        'distance_to_fear': round(min(scores) - FEAR_THRESHOLD, 1),
        'distance_to_greed': round(max(scores) - GREED_THRESHOLD, 1),
    }


def generate_signals(current_score, current_label, extreme_fear, extreme_greed, score_stats, market_name):
    """Generate dynamic signal texts based on current state."""
    signals = []
    score_int = round(current_score)

    # Active Extreme Fear
    if current_score < FEAR_THRESHOLD:
        if extreme_fear['episodes'] > 0 and extreme_fear.get('avg_return_30d') is not None:
            avg = extreme_fear['avg_return_30d']
            sign = "+" if avg >= 0 else ""
            signals.append(
                f"The index is in Extreme Fear ({score_int}). "
                f"Historically, buying at these levels returned "
                f"{sign}{avg}% over 30 days "
                f"({extreme_fear['win_rate_30d']}% success rate)."
            )
        else:
            signals.append(
                f"The index is in Extreme Fear ({score_int}). "
                f"Not enough historical data yet to calculate returns after similar readings."
            )

    # Active Extreme Greed
    elif current_score > GREED_THRESHOLD:
        if extreme_greed['episodes'] > 0 and extreme_greed.get('avg_return_30d') is not None:
            avg = extreme_greed['avg_return_30d']
            verb = "declined" if avg < 0 else "gained"
            signals.append(
                f"The index is in Extreme Greed ({score_int}). "
                f"Historically, the price {verb} an average of "
                f"{abs(avg)}% in the 30 days following similar readings."
            )
        else:
            signals.append(
                f"The index is in Extreme Greed ({score_int}). "
                f"Not enough historical data yet to measure what typically follows."
            )

    # Normal zone — check recent exit from extreme
    else:
        fear_last = extreme_fear.get('last')
        greed_last = extreme_greed.get('last')

        if fear_last and fear_last['days_ago'] <= 30:
            if extreme_fear.get('avg_return_60d') is not None:
                avg = extreme_fear['avg_return_60d']
                verb = "gained" if avg >= 0 else "declined"
                signals.append(
                    f"The index exited Extreme Fear {fear_last['days_ago']} days ago. "
                    f"After previous exits, the price {verb} "
                    f"{abs(avg)}% over 60 days on average."
                )
            else:
                signals.append(
                    f"The index exited Extreme Fear {fear_last['days_ago']} days ago."
                )
        elif greed_last and greed_last['days_ago'] <= 30:
            if extreme_greed.get('avg_return_60d') is not None:
                avg = extreme_greed['avg_return_60d']
                verb = "declined" if avg < 0 else "gained"
                signals.append(
                    f"The index exited Extreme Greed {greed_last['days_ago']} days ago. "
                    f"After previous exits, the price {verb} "
                    f"{abs(avg)}% over 60 days on average."
                )

    # No extremes ever (bonds)
    if extreme_fear['episodes'] == 0 and extreme_greed['episodes'] == 0 and score_stats:
        signals.append(
            f"This index has never reached Extreme Fear or Extreme Greed. "
            f"The score ranges between {score_stats['min']} and {score_stats['max']}, "
            f"suggesting sentiment has limited impact on this market."
        )

    # Partial extremes (e.g. gold: no EF but has EG)
    elif extreme_fear['episodes'] == 0 and extreme_greed['episodes'] > 0 and not signals:
        if score_stats and score_stats['percentile_label']:
            signals.append(
                f"The index is at {score_int} ({current_label}) — "
                f"{score_stats['percentile_label'].lower()} (P{score_stats['current_percentile']}). "
                f"The score never dropped below {score_stats['min']} (Extreme Fear starts at {FEAR_THRESHOLD})."
            )
    elif extreme_greed['episodes'] == 0 and extreme_fear['episodes'] > 0 and not signals:
        if score_stats:
            signals.append(
                f"The index is at {score_int} ({current_label}). "
                f"The score never rose above {score_stats['max']} (Extreme Greed starts at {GREED_THRESHOLD})."
            )

    # Percentile-based signal when in normal zone
    if not signals and score_stats:
        if score_stats['current_percentile'] >= 90:
            signals.append(
                f"The index is at {score_int} ({current_label}) — higher than {score_stats['current_percentile']}% of readings over the past 12 months."
            )
        elif score_stats['current_percentile'] <= 10:
            signals.append(
                f"The index is at {score_int} ({current_label}) — lower than {100 - score_stats['current_percentile']}% of readings over the past 12 months."
            )

    # Fallback
    if not signals:
        if score_stats:
            signals.append(
                f"The index is at {score_int} ({current_label}). "
                f"Over the past 12 months, it ranged from {score_stats['min']} to {score_stats['max']}."
            )

    return signals


def process_market(name, config):
    """Process one market and return insights dict."""
    print(f"\n{'='*50}")
    print(f"Processing {name.upper()} ({'5Y' if USE_5Y else '1Y'})...")

    if USE_5Y:
        # Load 5-year rebuild (already has prices embedded)
        fg_history, current_score, current_label = load_5y_history(config['fg_5y'])
        print(f"  5Y history: {len(fg_history)} days, current: {current_score} ({current_label})")

        # Build aligned list directly from 5y data (already has prices)
        aligned = [{'date': h['date'], 'score': h['score'], 'price': h['price']}
                   for h in fg_history if 'price' in h]
        print(f"  Aligned: {len(aligned)} data points")
    else:
        # Load 1-year F&G history
        fg_history, current_score, current_label = load_fg_history(config['fg_file'])
        print(f"  F&G history: {len(fg_history)} days, current: {current_score} ({current_label})")

        # Fetch prices
        print(f"  Fetching {config['price_symbol']} prices...")
        price_map = fetch_prices(config['price_symbol'])
        print(f"  Prices: {len(price_map)} days")

        # Align
        aligned = align_data(fg_history, price_map)
        print(f"  Aligned: {len(aligned)} data points")

    if len(aligned) < 10:
        print(f"  WARNING: Not enough aligned data for {name}")
        return None

    # Correlation
    all_scores = [p['score'] for p in aligned]
    all_prices = [p['price'] for p in aligned]
    r_full = pearson_r(all_scores, all_prices)

    last_90 = aligned[-90:] if len(aligned) >= 90 else aligned
    r_90d = pearson_r([p['score'] for p in last_90], [p['price'] for p in last_90])

    # Correlation trend
    if r_90d is not None and r_full is not None:
        diff = abs(r_90d) - abs(r_full)
        if diff > 0.15:
            corr_trend = 'strengthening'
            corr_trend_detail = f"Recently stronger ({r_90d} vs {r_full} overall)"
        elif diff < -0.15:
            corr_trend = 'weakening'
            corr_trend_detail = f"Recently weaker ({r_90d} vs {r_full} overall)"
        else:
            corr_trend = 'stable'
            corr_trend_detail = f"Consistent ({r_90d} vs {r_full} overall)"
    else:
        corr_trend = None
        corr_trend_detail = None

    correlation = {
        'r_90d': r_90d,
        'r_full': r_full,
        'label_90d': correlation_label(r_90d),
        'label_full': correlation_label(r_full),
        'trend': corr_trend,
        'trend_detail': corr_trend_detail,
    }
    print(f"  Correlation: r_90d={r_90d}, r_full={r_full}")

    # Score stats
    score_stats = compute_score_stats(fg_history, current_score)
    print(f"  Score range: {score_stats['min']} - {score_stats['max']} (avg: {score_stats['avg']})")

    today = datetime.now().strftime('%Y-%m-%d')

    # Extreme Fear backtest
    fear_episodes = find_episodes(aligned, FEAR_THRESHOLD, 'below')
    fear_returns = compute_returns(fear_episodes, aligned)
    fear_total_days = sum(1 for p in aligned if p['score'] < FEAR_THRESHOLD)
    fear_last = None
    if fear_episodes:
        last_ep = fear_episodes[-1]
        days_ago = (datetime.strptime(today, '%Y-%m-%d') - datetime.strptime(last_ep['date'], '%Y-%m-%d')).days
        fear_last = {
            'date': last_ep['date'],
            'score': round(last_ep['score'], 1),
            'price': last_ep['price'],
            'days_ago': days_ago
        }

    extreme_fear = {
        'threshold': FEAR_THRESHOLD,
        'episodes': len(fear_episodes),
        'total_days': fear_total_days,
        'avg_return_30d': fear_returns[30]['avg'],
        'avg_return_60d': fear_returns[60]['avg'],
        'avg_return_90d': fear_returns[90]['avg'],
        'win_rate_30d': fear_returns[30]['win_rate'],
        'episodes_with_30d_data': fear_returns[30]['count'],
        'episodes_with_60d_data': fear_returns[60]['count'],
        'episodes_with_90d_data': fear_returns[90]['count'],
        'last': fear_last,
    }
    print(f"  Extreme Fear: {len(fear_episodes)} episodes, {fear_total_days} days")

    # Extreme Greed backtest
    greed_episodes = find_episodes(aligned, GREED_THRESHOLD, 'above')
    greed_returns = compute_returns(greed_episodes, aligned)
    greed_total_days = sum(1 for p in aligned if p['score'] > GREED_THRESHOLD)
    greed_last = None
    if greed_episodes:
        last_ep = greed_episodes[-1]
        days_ago = (datetime.strptime(today, '%Y-%m-%d') - datetime.strptime(last_ep['date'], '%Y-%m-%d')).days
        greed_last = {
            'date': last_ep['date'],
            'score': round(last_ep['score'], 1),
            'price': last_ep['price'],
            'days_ago': days_ago
        }

    extreme_greed = {
        'threshold': GREED_THRESHOLD,
        'episodes': len(greed_episodes),
        'total_days': greed_total_days,
        'avg_return_30d': greed_returns[30]['avg'],
        'avg_return_60d': greed_returns[60]['avg'],
        'avg_return_90d': greed_returns[90]['avg'],
        'win_rate_30d': greed_returns[30]['win_rate'],
        'episodes_with_30d_data': greed_returns[30]['count'],
        'episodes_with_60d_data': greed_returns[60]['count'],
        'episodes_with_90d_data': greed_returns[90]['count'],
        'last': greed_last,
    }
    print(f"  Extreme Greed: {len(greed_episodes)} episodes, {greed_total_days} days")

    # Signals
    signals = generate_signals(current_score, current_label, extreme_fear, extreme_greed, score_stats, name)
    for s in signals:
        print(f"  Signal: {s}")

    return {
        'updated': datetime.now(tz=None).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'asset': name,
        'price_symbol': config['price_symbol'],
        'price_label': config['price_label'],
        'correlation': correlation,
        'score_stats': score_stats,
        'extreme_fear': extreme_fear,
        'extreme_greed': extreme_greed,
        'signals': signals,
    }


def main():
    print("Generating market insights...")

    suffix = '-5y' if USE_5Y else ''
    for name, config in MARKETS.items():
        try:
            insights = process_market(name, config)
            if insights:
                path = f'data/insights{suffix}-{name}.json'
                with open(path, 'w') as f:
                    json.dump(insights, f, indent=2)
                print(f"  -> Saved to {path}")
        except Exception as e:
            print(f"  ERROR processing {name}: {e}")

    print("\nDone!")


if __name__ == '__main__':
    main()
