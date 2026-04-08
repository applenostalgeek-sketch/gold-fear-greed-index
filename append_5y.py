#!/usr/bin/env python3
"""Append today's scores to 5-year history files.

Reads the latest entry from each 1Y JSON (DESC order),
appends it to the corresponding 5Y JSON (ASC order),
and removes entries older than 5 years.
"""

import json
import math
import os
from datetime import datetime, timedelta, timezone

ASSETS = {
    'gold': {
        'source': 'data/gold-fear-greed.json',
        'target': 'data/history-5y-gold.json'
    },
    'stocks': {
        'source': 'data/stocks-fear-greed.json',
        'target': 'data/history-5y-stocks.json'
    },
    'crypto': {
        'source': 'data/crypto-fear-greed.json',
        'target': 'data/history-5y-crypto.json'
    },
    'bonds': {
        'source': 'data/bonds-fear-greed.json',
        'target': 'data/history-5y-bonds.json'
    },
}


def get_label(score):
    if score >= 75: return "Extreme Greed"
    if score >= 55: return "Greed"
    if score >= 45: return "Neutral"
    if score >= 25: return "Fear"
    return "Extreme Fear"


def append_5y():
    cutoff = (datetime.now() - timedelta(days=5 * 365)).strftime('%Y-%m-%d')

    for asset, paths in ASSETS.items():
        source_path = paths['source']
        target_path = paths['target']

        if not os.path.exists(source_path) or not os.path.exists(target_path):
            print(f"  Skipping {asset}: file not found")
            continue

        # Read source (1Y, DESC order — newest first)
        with open(source_path) as f:
            source = json.load(f)

        today_entry = source['history'][0]
        today_date = today_entry['date']

        # Read target (5Y, ASC order — oldest first)
        with open(target_path) as f:
            target = json.load(f)

        history = target['history']

        # Check if date already exists
        existing_dates = {e['date'] for e in history}
        if today_date in existing_dates:
            print(f"  {asset}: {today_date} already exists, skipping")
            continue

        # Build new entry (5Y format includes label)
        new_entry = {
            'date': today_date,
            'score': today_entry['score'],
            'label': get_label(today_entry['score']),
        }
        price = today_entry.get('price')
        if price is not None and not (isinstance(price, float) and math.isnan(price)):
            new_entry['price'] = price

        history.append(new_entry)

        # Remove entries older than 5 years
        history = [e for e in history if e['date'] >= cutoff]

        # Sort ASC (5Y convention)
        history.sort(key=lambda x: x['date'])

        # Update metadata
        scores = [e['score'] for e in history]
        target['history'] = history
        target['generated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        target['total_days'] = len(history)
        target['date_range'] = {
            'start': history[0]['date'],
            'end': history[-1]['date']
        }
        target['score_stats'] = {
            'min': round(min(scores), 1),
            'max': round(max(scores), 1),
            'avg': round(sum(scores) / len(scores), 1)
        }

        with open(target_path, 'w') as f:
            json.dump(target, f, indent=2)

        print(f"  {asset}: appended {today_date} (score: {new_entry['score']}), total: {len(history)} days")


if __name__ == '__main__':
    print("Appending today's scores to 5Y history...")
    append_5y()
    print("Done.")
