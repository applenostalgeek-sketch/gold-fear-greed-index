"""
One-shot script: generate price history JSON files for compare.html
Run once: python generate_prices.py
Creates: data/prices-btc.json, data/prices-gld.json, data/prices-spy.json, data/prices-tlt.json
"""
import yfinance as yf
import json
from datetime import datetime, timedelta

symbols = {
    'btc': 'BTC-USD',
    'gld': 'GLD',
    'spy': 'SPY',
    'tlt': 'TLT'
}

end = datetime.now()
start = end - timedelta(days=400)

for key, symbol in symbols.items():
    print(f"Fetching {symbol}...")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'))

    prices = []
    for date, row in hist.iterrows():
        prices.append({
            'date': date.strftime('%Y-%m-%d'),
            'price': round(float(row['Close']), 2)
        })

    path = f'data/prices-{key}.json'
    with open(path, 'w') as f:
        json.dump(prices, f)

    print(f"  -> {path} ({len(prices)} days)")

print("Done!")
