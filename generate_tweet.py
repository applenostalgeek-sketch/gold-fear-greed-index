#!/usr/bin/env python3
"""
Local tweet generator for OnOff.Markets
Run this script to generate a formatted tweet to copy-paste manually
"""

import json
from datetime import datetime

def load_index_data(filename):
    """Load sentiment index data from JSON file"""
    try:
        with open(f'data/{filename}', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filename}: {e}")
        return None

def calculate_market_rotation(bonds, gold, stocks, crypto):
    """Calculate Risk-On vs Risk-Off score"""
    risk_off = (bonds + gold) / 2
    risk_on = (stocks + crypto) / 2

    # Net score: positive = Risk-On, negative = Risk-Off
    net_score = risk_on - risk_off

    # Convert to 0-100 scale (0 = Extreme Risk-Off, 100 = Extreme Risk-On)
    rotation_score = 50 + (net_score / 2)
    rotation_score = max(0, min(100, rotation_score))

    if rotation_score >= 55:
        return "Risk-On", round(rotation_score, 1)
    elif rotation_score <= 45:
        return "Risk-Off", round(rotation_score, 1)
    else:
        return "Neutral", round(rotation_score, 1)

def format_tweet(bonds_data, gold_data, stocks_data, crypto_data):
    """Format the daily tweet message"""

    # Extract scores
    bonds_score = round(bonds_data['score'], 0)
    gold_score = round(gold_data['score'], 0)
    stocks_score = round(stocks_data['score'], 0)
    crypto_score = round(crypto_data['score'], 0)

    # Extract labels
    bonds_label = bonds_data['label']
    gold_label = gold_data['label']
    stocks_label = stocks_data['label']
    crypto_label = crypto_data['label']

    # Calculate market rotation
    rotation_label, rotation_score = calculate_market_rotation(
        bonds_score, gold_score, stocks_score, crypto_score
    )

    # Format date (Paris time)
    date_str = datetime.now().strftime("%d %b %Y")

    # Build tweet
    tweet = f"""📊 Market Sentiment - {date_str}

📊 Bonds: {int(bonds_score)} ({bonds_label})
🪙 Gold: {int(gold_score)} ({gold_label})
📈 Stocks: {int(stocks_score)} ({stocks_label})
₿ Crypto: {int(crypto_score)} ({crypto_label})

Market: {rotation_label} ({rotation_score}%)

→ onoff.markets"""

    return tweet

def main():
    """Main execution function"""

    print("\n" + "="*60)
    print("🤖 OnOff.Markets - Tweet Generator")
    print("="*60 + "\n")

    # Load all index data
    print("📥 Loading sentiment data...")
    bonds_data = load_index_data('bonds-fear-greed.json')
    gold_data = load_index_data('gold-fear-greed.json')
    stocks_data = load_index_data('stocks-fear-greed.json')
    crypto_data = load_index_data('crypto-fear-greed.json')

    if not all([bonds_data, gold_data, stocks_data, crypto_data]):
        print("\n❌ Failed to load one or more index data files")
        return

    print("✅ All data loaded successfully\n")

    # Format tweet
    tweet_text = format_tweet(bonds_data, gold_data, stocks_data, crypto_data)

    # Display tweet
    print("="*60)
    print("📋 TWEET TO COPY-PASTE:")
    print("="*60)
    print()
    print(tweet_text)
    print()
    print("="*60)
    print(f"Character count: {len(tweet_text)}/280")
    print("="*60)
    print()
    print("✅ Copy the text above and paste it on Twitter!")
    print()

if __name__ == "__main__":
    main()
