#!/usr/bin/env python3
"""
Post daily Fear & Greed Index tweet to Twitter/X.
Reads the 4 JSON data files and generates a formatted tweet.

Usage:
    python post_tweet.py              # Post tweet (requires API credentials)
    python post_tweet.py --dry-run    # Preview tweet without posting

Environment variables (for posting):
    TWITTER_API_KEY
    TWITTER_API_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET
"""

import json
import os
import sys
from datetime import datetime, timezone


def load_data():
    """Load all 4 index JSON files."""
    data = {}
    files = {
        'gold': 'data/gold-fear-greed.json',
        'bonds': 'data/bonds-fear-greed.json',
        'stocks': 'data/stocks-fear-greed.json',
        'crypto': 'data/crypto-fear-greed.json',
    }

    for name, path in files.items():
        try:
            with open(path, 'r') as f:
                data[name] = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {path} not found, skipping {name}")
            return None

    return data


def calculate_market_sentiment(data):
    """Calculate overall Risk-On vs Risk-Off score (same formula as index.html)."""
    risk_on = (data['stocks']['score'] + data['crypto']['score']) / 2
    risk_off = (data['bonds']['score'] + data['gold']['score']) / 2
    rotation_score = risk_on - risk_off
    position = ((rotation_score + 100) / 200) * 100
    return round(position)


def get_sentiment_label(position):
    """Get label and emoji for the overall sentiment score."""
    if position < 25:
        return "EXTREME RISK-OFF", "🔴"
    elif position < 45:
        return "DEFENSIVE", "🛡️"
    elif position < 55:
        return "BALANCED", "⚖️"
    elif position < 75:
        return "RISK-ON", "🚀"
    else:
        return "EXTREME RISK-ON", "⚡"


def get_score_bar(score):
    """Generate a simple visual bar for a score."""
    filled = round(score / 10)
    return "▓" * filled + "░" * (10 - filled)


def get_change_arrow(data, name):
    """Get daily change arrow from history."""
    history = data[name].get('history', [])
    if len(history) >= 2:
        today = history[0]['score']
        yesterday = history[1]['score']
        diff = today - yesterday
        if diff > 2:
            return "↑"
        elif diff < -2:
            return "↓"
    return "→"


def generate_tweet(data):
    """Generate the tweet text from index data."""
    gold = data['gold']
    bonds = data['bonds']
    stocks = data['stocks']
    crypto = data['crypto']

    # Overall sentiment
    position = calculate_market_sentiment(data)
    label, emoji = get_sentiment_label(position)

    # Daily changes
    g_arrow = get_change_arrow(data, 'gold')
    b_arrow = get_change_arrow(data, 'bonds')
    s_arrow = get_change_arrow(data, 'stocks')
    c_arrow = get_change_arrow(data, 'crypto')

    # Date
    today = datetime.now(timezone.utc).strftime('%b %d')

    # Build tweet
    tweet = (
        f"{emoji} Market Sentiment — {today}\n"
        f"\n"
        f"🪙 Gold: {round(gold['score'])} {g_arrow} {gold['label']}\n"
        f"📊 Bonds: {round(bonds['score'])} {b_arrow} {bonds['label']}\n"
        f"📈 Stocks: {round(stocks['score'])} {s_arrow} {stocks['label']}\n"
        f"🟠 Crypto: {round(crypto['score'])} {c_arrow} {crypto['label']}\n"
        f"\n"
        f"Overall: {label} ({position}/100)\n"
        f"\n"
        f"onoff.markets\n"
        f"\n"
        f"#FearAndGreed #MarketSentiment"
    )

    return tweet


def generate_extreme_tweet(data):
    """Generate a more impactful tweet when extremes are detected."""
    gold = data['gold']
    bonds = data['bonds']
    stocks = data['stocks']
    crypto = data['crypto']

    extremes = []
    if gold['score'] <= 20 or gold['score'] >= 80:
        extremes.append(('gold', gold))
    if bonds['score'] <= 20 or bonds['score'] >= 80:
        extremes.append(('bonds', bonds))
    if stocks['score'] <= 20 or stocks['score'] >= 80:
        extremes.append(('stocks', stocks))
    if crypto['score'] <= 20 or crypto['score'] >= 80:
        extremes.append(('crypto', crypto))

    if not extremes:
        return None

    position = calculate_market_sentiment(data)
    label, emoji = get_sentiment_label(position)
    today = datetime.now(timezone.utc).strftime('%b %d')

    icons = {'gold': '🪙', 'bonds': '📊', 'stocks': '📈', 'crypto': '🟠'}

    extreme_lines = []
    for name, d in extremes:
        icon = icons[name]
        if d['score'] <= 20:
            extreme_lines.append(f"{icon} {name.title()}: {round(d['score'])} — {d['label']} ⚠️")
        else:
            extreme_lines.append(f"{icon} {name.title()}: {round(d['score'])} — {d['label']} 🔥")

    tweet = (
        f"⚠️ Extreme readings detected — {today}\n"
        f"\n"
        + "\n".join(extreme_lines) + "\n"
        f"\n"
        f"Overall: {label} ({position}/100)\n"
        f"\n"
        f"Full breakdown → onoff.markets\n"
        f"\n"
        f"#FearAndGreed #MarketSentiment"
    )

    # Fall back to normal if too long
    if len(tweet) > 280:
        return None

    return tweet


def post_tweet(tweet_text):
    """Post the tweet using Tweepy."""
    try:
        import tweepy
    except ImportError:
        print("Error: tweepy not installed. Run: pip install tweepy")
        sys.exit(1)

    api_key = os.environ.get('TWITTER_API_KEY')
    api_secret = os.environ.get('TWITTER_API_SECRET')
    access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
    access_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

    if not all([api_key, api_secret, access_token, access_secret]):
        print("Error: Missing Twitter API credentials.")
        print("Required env vars: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
        sys.exit(1)

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    response = client.create_tweet(text=tweet_text)
    tweet_id = response.data['id']
    print(f"Tweet posted successfully! ID: {tweet_id}")
    return tweet_id


def main():
    dry_run = '--dry-run' in sys.argv

    data = load_data()
    if data is None:
        print("Error: Could not load all data files.")
        sys.exit(1)

    # Try extreme tweet first, fall back to standard
    tweet = generate_extreme_tweet(data)
    if tweet is None:
        tweet = generate_tweet(data)

    # Verify length
    if len(tweet) > 280:
        print(f"Warning: Tweet is {len(tweet)} chars, truncating hashtags...")
        # Remove hashtags to fit
        tweet = tweet.rsplit('\n\n#', 1)[0]

    print(f"--- Tweet ({len(tweet)}/280 chars) ---")
    print(tweet)
    print("---")

    if dry_run:
        print("\n[DRY RUN] Tweet not posted.")
    else:
        post_tweet(tweet)


if __name__ == '__main__':
    main()
