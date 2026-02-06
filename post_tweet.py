#!/usr/bin/env python3
"""
Post daily Fear & Greed Index tweet to Twitter/X.
Reads the 4 JSON data files and generates a varied, data-driven tweet.

The script detects the most interesting "story" in the data and picks
the best tweet format automatically. 7 possible formats:
  1. Extreme readings (score < 20 or > 80)
  2. Biggest daily mover
  3. Divergence (risk-on vs risk-off going opposite ways)
  4. Threshold crossing (zone change: Fear → Greed, etc.)
  5. Winning streak (rising/falling X days in a row)
  6. All aligned (all 4 moving same direction)
  7. Standard daily recap

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

ICONS = {'gold': '🪙', 'bonds': '📊', 'stocks': '📈', 'crypto': '🟠'}
NAMES = {'gold': 'Gold', 'bonds': 'Bonds', 'stocks': 'Stocks', 'crypto': 'Crypto'}
HASHTAGS = "#FearAndGreed #MarketSentiment"


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
            print(f"Warning: {path} not found")
            return None
    return data


def get_today():
    return datetime.now(timezone.utc).strftime('%b %d')


def calculate_market_sentiment(data):
    """Calculate overall Risk-On vs Risk-Off score (same formula as index.html)."""
    risk_on = (data['stocks']['score'] + data['crypto']['score']) / 2
    risk_off = (data['bonds']['score'] + data['gold']['score']) / 2
    rotation_score = risk_on - risk_off
    return round(((rotation_score + 100) / 200) * 100)


def get_sentiment_label(position):
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


def get_label_for_score(score):
    if score <= 25:
        return "Extreme Fear"
    elif score <= 45:
        return "Fear"
    elif score <= 55:
        return "Neutral"
    elif score <= 75:
        return "Greed"
    return "Extreme Greed"


def get_history(data, name, days=7):
    """Get last N days of history for an asset."""
    history = data[name].get('history', [])
    return history[:days]


def get_daily_change(data, name):
    """Get score change vs yesterday."""
    history = get_history(data, name, 2)
    if len(history) >= 2:
        return round(history[0]['score'] - history[1]['score'], 1)
    return 0


def get_streak(data, name):
    """Count consecutive days moving in the same direction."""
    history = get_history(data, name, 14)
    if len(history) < 2:
        return 0
    direction = 1 if history[0]['score'] > history[1]['score'] else -1
    streak = 1
    for i in range(1, len(history) - 1):
        if direction > 0 and history[i]['score'] > history[i + 1]['score']:
            streak += 1
        elif direction < 0 and history[i]['score'] < history[i + 1]['score']:
            streak += 1
        else:
            break
    return streak * direction


def score_line(name, data):
    """Format a single asset line: 🪙 Gold: 68 → Greed"""
    score = round(data[name]['score'])
    change = get_daily_change(data, name)
    if change > 2:
        arrow = "↑"
    elif change < -2:
        arrow = "↓"
    else:
        arrow = "→"
    return f"{ICONS[name]} {NAMES[name]}: {score} {arrow} {data[name]['label']}"


def all_scores_block(data):
    """Generate the 4-line scores block."""
    return "\n".join(score_line(name, data) for name in ['gold', 'bonds', 'stocks', 'crypto'])


def overall_line(data):
    """Generate the overall sentiment line."""
    position = calculate_market_sentiment(data)
    label, _ = get_sentiment_label(position)
    return f"Overall: {label} ({position}/100)"


# ─── Tweet generators (priority order) ───


def tweet_extreme(data):
    """Priority 1: Extreme readings detected."""
    extremes = []
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        s = data[name]['score']
        if s <= 15 or s >= 85:
            extremes.append((name, s))

    if not extremes:
        return None, 0

    today = get_today()

    if len(extremes) >= 2:
        # Multiple extremes — very rare, high priority
        lines = []
        for name, s in extremes:
            flag = "⚠️" if s <= 15 else "🔥"
            lines.append(f"{ICONS[name]} {NAMES[name]}: {round(s)} — {data[name]['label']} {flag}")
        tweet = (
            f"🚨 Multiple extreme readings — {today}\n\n"
            + "\n".join(lines) + "\n\n"
            + overall_line(data) + "\n\n"
            + HASHTAGS
        )
        return tweet, 100

    name, s = extremes[0]
    change = get_daily_change(data, name)
    direction = "plunging" if change < -5 else ("surging" if change > 5 else "deep in" if s <= 15 else "running hot at")

    tweet = (
        f"⚠️ {NAMES[name]} {direction} {data[name]['label']} territory — {today}\n\n"
        f"{ICONS[name]} {NAMES[name]}: {round(s)}/100\n\n"
        + all_scores_block(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 90


def tweet_divergence(data):
    """Priority 2: Risk-on and risk-off assets diverging strongly."""
    risk_on_avg = (data['stocks']['score'] + data['crypto']['score']) / 2
    risk_off_avg = (data['bonds']['score'] + data['gold']['score']) / 2
    spread = abs(risk_on_avg - risk_off_avg)

    if spread < 25:
        return None, 0

    today = get_today()

    if risk_on_avg > risk_off_avg:
        narrative = "Risk assets and safe havens telling opposite stories"
        detail = f"Risk-On avg: {round(risk_on_avg)} vs Risk-Off avg: {round(risk_off_avg)}"
    else:
        narrative = "Safe havens surging while risk assets retreat"
        detail = f"Risk-Off avg: {round(risk_off_avg)} vs Risk-On avg: {round(risk_on_avg)}"

    tweet = (
        f"📐 {narrative} — {today}\n\n"
        f"{detail}\n\n"
        + all_scores_block(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 80


def tweet_biggest_mover(data):
    """Priority 3: One asset moved significantly more than others."""
    changes = {}
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        changes[name] = get_daily_change(data, name)

    biggest_name = max(changes, key=lambda k: abs(changes[k]))
    biggest_change = changes[biggest_name]

    if abs(biggest_change) < 6:
        return None, 0

    today = get_today()
    direction = "jumps" if biggest_change > 0 else "drops"
    score = round(data[biggest_name]['score'])
    sign = "+" if biggest_change > 0 else ""

    tweet = (
        f"📊 {NAMES[biggest_name]} {direction} {sign}{round(biggest_change)} pts today — {today}\n\n"
        f"{ICONS[biggest_name]} {NAMES[biggest_name]}: {score}/100 ({data[biggest_name]['label']})\n\n"
        + all_scores_block(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 70


def tweet_threshold_crossing(data):
    """Priority 4: An asset just changed sentiment zone."""
    crossings = []
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        history = get_history(data, name, 2)
        if len(history) >= 2:
            old_label = get_label_for_score(history[1]['score'])
            new_label = get_label_for_score(history[0]['score'])
            if old_label != new_label:
                crossings.append((name, old_label, new_label))

    if not crossings:
        return None, 0

    today = get_today()

    if len(crossings) == 1:
        name, old_l, new_l = crossings[0]
        score = round(data[name]['score'])
        tweet = (
            f"🔀 {NAMES[name]} shifts from {old_l} to {new_l} — {today}\n\n"
            f"{ICONS[name]} {NAMES[name]}: {score}/100\n\n"
            + all_scores_block(data) + "\n\n"
            + HASHTAGS
        )
    else:
        lines = [f"{ICONS[n]} {NAMES[n]}: {old} → {new}" for n, old, new in crossings]
        tweet = (
            f"🔀 Sentiment shifts detected — {today}\n\n"
            + "\n".join(lines) + "\n\n"
            + all_scores_block(data) + "\n\n"
            + HASHTAGS
        )
    return tweet, 65


def tweet_streak(data):
    """Priority 5: An asset on a notable streak."""
    best_name = None
    best_streak = 0
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        streak = get_streak(data, name)
        if abs(streak) > abs(best_streak):
            best_streak = streak
            best_name = name

    if abs(best_streak) < 5:
        return None, 0

    today = get_today()
    direction = "rising" if best_streak > 0 else "falling"
    score = round(data[best_name]['score'])

    tweet = (
        f"📈 {NAMES[best_name]} {direction} for {abs(best_streak)} days straight — {today}\n\n"
        f"{ICONS[best_name]} {NAMES[best_name]}: {score}/100 ({data[best_name]['label']})\n\n"
        + all_scores_block(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 60


def tweet_all_aligned(data):
    """Priority 6: All 4 assets moving in the same direction."""
    changes = {}
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        changes[name] = get_daily_change(data, name)

    all_up = all(c > 1 for c in changes.values())
    all_down = all(c < -1 for c in changes.values())

    if not all_up and not all_down:
        return None, 0

    today = get_today()
    if all_up:
        narrative = "All 4 markets trending toward greed"
        emoji = "🟢"
    else:
        narrative = "All 4 markets trending toward fear"
        emoji = "🔴"

    tweet = (
        f"{emoji} {narrative} — {today}\n\n"
        + all_scores_block(data) + "\n\n"
        + overall_line(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 55


def tweet_standard(data):
    """Priority 7: Standard daily recap (always works)."""
    today = get_today()
    position = calculate_market_sentiment(data)
    _, emoji = get_sentiment_label(position)

    tweet = (
        f"{emoji} Market Sentiment — {today}\n\n"
        + all_scores_block(data) + "\n\n"
        + overall_line(data) + "\n\n"
        + HASHTAGS
    )
    return tweet, 10


# ─── Main logic ───


def generate_best_tweet(data):
    """Try all tweet generators and pick the highest-priority one that fits."""
    generators = [
        tweet_extreme,
        tweet_divergence,
        tweet_biggest_mover,
        tweet_threshold_crossing,
        tweet_streak,
        tweet_all_aligned,
        tweet_standard,
    ]

    best_tweet = None
    best_priority = -1

    for gen in generators:
        tweet, priority = gen(data)
        if tweet and len(tweet) <= 280 and priority > best_priority:
            best_tweet = tweet
            best_priority = priority

    return best_tweet


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

    tweet = generate_best_tweet(data)

    if tweet is None:
        print("Error: Could not generate any tweet.")
        sys.exit(1)

    # Safety: truncate hashtags if somehow too long
    if len(tweet) > 280:
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
