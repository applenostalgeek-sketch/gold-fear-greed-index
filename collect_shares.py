"""
collect_shares.py - Collect daily ETF shares outstanding for capital flow tracking.

Tracks shares outstanding for key ETFs representing each asset class:
  - GLD  (Gold)
  - TLT  (Bonds)
  - SPY  (Stocks)
  - GBTC (Crypto) — IBIT/BITO don't expose sharesOutstanding via yfinance

Changes in shares outstanding = creation/redemption = proxy for real capital flows.
Data stored in data/etf-shares.json, accumulating daily.

Run: python collect_shares.py
"""

import json
import yfinance as yf
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path('data/etf-shares.json')

ETFS = {
    'gold': 'GLD',
    'bonds': 'TLT',
    'stocks': 'SPY',
    'crypto': 'GBTC',
}


def load_existing():
    """Load existing shares data or return empty structure."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        'etfs': ETFS,
        'history': [],
    }


def collect_shares():
    """Fetch current shares outstanding for each ETF."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = {'date': today}
    success_count = 0

    for asset_key, symbol in ETFS.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            shares = info.get('sharesOutstanding')

            if shares and shares > 0:
                entry[asset_key] = int(shares)
                print(f"  {symbol}: {shares:,.0f} shares")
                success_count += 1
            else:
                # Fallback: try totalAssets as proxy
                total = info.get('totalAssets')
                if total and total > 0:
                    entry[asset_key] = int(total)
                    print(f"  {symbol}: totalAssets={total:,.0f} (no sharesOutstanding)")
                    success_count += 1
                else:
                    entry[asset_key] = None
                    print(f"  {symbol}: no data available")
        except Exception as e:
            entry[asset_key] = None
            print(f"  {symbol}: ERROR - {e}")

    return entry, success_count


def main():
    print("Collecting ETF shares outstanding...")

    data = load_existing()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # Check if we already have today's data
    existing_dates = {h['date'] for h in data['history']}
    if today in existing_dates:
        print(f"  Already have data for {today}, updating...")
        data['history'] = [h for h in data['history'] if h['date'] != today]

    entry, success_count = collect_shares()

    if success_count == 0:
        print("  No data collected, skipping save.")
        return

    data['history'].append(entry)

    # Sort by date and keep last 365 entries
    data['history'].sort(key=lambda x: x['date'])
    if len(data['history']) > 365:
        data['history'] = data['history'][-365:]

    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  Saved to {DATA_FILE} ({len(data['history'])} entries)")

    # Show flow info if we have 2+ days
    if len(data['history']) >= 2:
        prev = data['history'][-2]
        curr = data['history'][-1]
        print("\n  Daily changes:")
        for asset_key, symbol in ETFS.items():
            prev_val = prev.get(asset_key)
            curr_val = curr.get(asset_key)
            if prev_val and curr_val:
                pct = ((curr_val - prev_val) / prev_val) * 100
                direction = 'INFLOW' if pct > 0 else 'OUTFLOW' if pct < 0 else 'FLAT'
                print(f"    {symbol}: {pct:+.2f}% ({direction})")


if __name__ == '__main__':
    main()
