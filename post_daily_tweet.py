#!/usr/bin/env python3
"""
Daily Twitter bot for OnOff.Markets sentiment indices
Posts market sentiment update at 09:00 Paris time
"""

import json
import os
from datetime import datetime
import tweepy

def load_index_data(filename):
    """Load sentiment index data from JSON file"""
    try:
        with open(f'data/{filename}', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None

def calculate_market_rotation(bonds, gold, stocks, crypto):
    """Calculate Risk-On vs Risk-Off score"""
    risk_off = (bonds + gold) / 2
    risk_on = (stocks + crypto) / 2

    # Net score: positive = Risk-On, negative = Risk-Off
    net_score = risk_on - risk_off

    # Convert to 0-100 scale (0 = Extreme Risk-Off, 100 = Extreme Risk-On)
    # Assuming max delta is ±50, map to 0-100
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

def post_tweet(tweet_text):
    """Post tweet using Twitter API v1.1"""

    # Get credentials from environment variables
    api_key = os.environ.get('TWITTER_API_KEY')
    api_secret = os.environ.get('TWITTER_API_SECRET')
    access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
    access_token_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

    if not all([api_key, api_secret, access_token, access_token_secret]):
        raise ValueError("Missing Twitter API credentials in environment variables")

    # Authenticate with Twitter
    auth = tweepy.OAuth1UserHandler(
        api_key, api_secret,
        access_token, access_token_secret
    )

    # Create API object (v1.1)
    api = tweepy.API(auth)

    # Verify credentials
    try:
        api.verify_credentials()
        print("✅ Twitter authentication successful")
    except Exception as e:
        raise Exception(f"Twitter authentication failed: {e}")

    # Post tweet
    try:
        response = api.update_status(tweet_text)
        print(f"✅ Tweet posted successfully!")
        print(f"Tweet ID: {response.id}")
        print(f"URL: https://twitter.com/user/status/{response.id}")
        return response
    except Exception as e:
        raise Exception(f"Failed to post tweet: {e}")

def main():
    """Main execution function"""

    print("🤖 Starting daily Twitter bot...")

    # Load all index data
    print("📥 Loading sentiment data...")
    bonds_data = load_index_data('bonds-fear-greed.json')
    gold_data = load_index_data('gold-fear-greed.json')
    stocks_data = load_index_data('stocks-fear-greed.json')
    crypto_data = load_index_data('crypto-fear-greed.json')

    if not all([bonds_data, gold_data, stocks_data, crypto_data]):
        raise Exception("Failed to load one or more index data files")

    print("✅ All data loaded successfully")

    # Format tweet
    print("✍️  Formatting tweet...")
    tweet_text = format_tweet(bonds_data, gold_data, stocks_data, crypto_data)

    print("\n" + "="*50)
    print("Tweet preview:")
    print("="*50)
    print(tweet_text)
    print("="*50)
    print(f"Character count: {len(tweet_text)}/280")
    print("="*50 + "\n")

    # Post to Twitter
    print("📤 Posting to Twitter...")
    post_tweet(tweet_text)

    print("✅ Daily update complete!")

if __name__ == "__main__":
    main()
