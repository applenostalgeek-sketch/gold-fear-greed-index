#!/usr/bin/env python3
"""
Post daily Fear & Greed Index tweet to Twitter/X.
Reads the 4 JSON data files and picks the most interesting "story" of the day.

10 story detectors, priority-ranked:
  1. Extreme readings (score <= 20 or >= 80)
  2. Big daily mover (|change| > 6 pts)
  3. Divergence (risk-on vs risk-off spread > 25)
  4. Zone crossing (sentiment label changed)
  5. Streak (5+ days same direction)
  6. All aligned (all 4 same direction)
  7. Biggest gap (max - min > 40)
  8. Weekly move (|7-day change| > 10)
  9. Component extreme (sub-component at 0 or 100)
  10. Calm day (fallback)

Usage:
    python post_tweet.py              # Post tweet (requires API credentials)
    python post_tweet.py --dry-run    # Preview tweet without posting
"""

import json
import os
import sys
from datetime import datetime, timezone

ICONS = {'gold': '🪙', 'bonds': '📊', 'stocks': '📈', 'crypto': '🟠'}
NAMES = {'gold': 'Gold', 'bonds': 'Bonds', 'stocks': 'Stocks', 'crypto': 'Crypto'}
ASSETS = ['gold', 'bonds', 'stocks', 'crypto']


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


def get_label(score):
    """Get sentiment label for a score."""
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


def get_weekly_change(data, name):
    """Get score change vs 7 days ago."""
    history = get_history(data, name, 8)
    if len(history) >= 7:
        return round(history[0]['score'] - history[6]['score'], 1)
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


def get_scores(data):
    """Get all current scores as rounded integers."""
    return {name: round(data[name]['score']) for name in ASSETS}


def get_highest_lowest(data):
    """Get the highest and lowest scoring assets."""
    scores = get_scores(data)
    highest = max(scores, key=scores.get)
    lowest = min(scores, key=scores.get)
    return highest, scores[highest], lowest, scores[lowest]


def add_contrast(data, main_asset):
    """Add a contrast line about another asset to enrich the story."""
    highest, h_score, lowest, l_score = get_highest_lowest(data)

    if main_asset == lowest and h_score - l_score >= 30:
        return f"Meanwhile {NAMES[highest]} sits at {h_score} ({get_label(h_score)})."
    elif main_asset == highest and h_score - l_score >= 30:
        return f"Meanwhile {NAMES[lowest]} sits at {l_score} ({get_label(l_score)})."
    elif main_asset != highest:
        return f"{NAMES[highest]} leads at {h_score} ({get_label(h_score)})."
    elif main_asset != lowest:
        return f"{NAMES[lowest]} trails at {l_score} ({get_label(l_score)})."

    return None


def get_component_detail(data, name):
    """Extract a readable detail line from components."""
    components = data[name].get('components', {})

    if name == 'crypto':
        ctx = components.get('context', {}).get('detail', '')
        vol = components.get('volatility', {}).get('detail', '')
        parts = []
        if 'change' in ctx:
            change = ctx.split(': ')[1] if ': ' in ctx else ctx
            parts.append(f"BTC {change} in 30 days")
        if vol and 'Vol' in vol:
            vol_val = vol.split(': ')[1].replace(' annualized', '') if ': ' in vol else ''
            if vol_val:
                parts.append(f"Volatility at {vol_val}")
        return '. '.join(parts) + '.' if parts else None

    if name == 'gold':
        detail = components.get('gld_price', {}).get('detail', '')
        if ':' in detail:
            change = detail.split(': ')[1]
            return f"GLD {change} in 14 days."
        return None

    if name == 'stocks':
        detail = components.get('price_strength', {}).get('detail', '')
        if detail:
            return f"{detail}."
        return None

    if name == 'bonds':
        detail = components.get('duration_risk', {}).get('detail', '')
        if detail:
            return f"{detail}."
        return None

    return None


# ─── Story detectors (priority order) ───


def detect_extreme(data):
    """Detector 1: Extreme readings (<= 20 or >= 80)."""
    extremes = []
    for name in ASSETS:
        s = round(data[name]['score'])
        if s <= 20 or s >= 80:
            extremes.append((name, s))

    if not extremes:
        return None, 0

    # Multiple extremes — very rare
    if len(extremes) >= 2:
        lines = []
        for name, s in extremes:
            lines.append(f"{ICONS[name]} {NAMES[name]}: {s} — {get_label(s)}")
        tweet = "Multiple extreme readings today.\n\n" + "\n".join(lines)
        highest, h_score, lowest, l_score = get_highest_lowest(data)
        gap = h_score - l_score
        if gap >= 30:
            tweet += f"\n\n{gap} points separate {NAMES[highest]} from {NAMES[lowest]}."
        return tweet, 100

    # Single extreme
    name, s = extremes[0]
    label = get_label(s)
    change = get_daily_change(data, name)

    # Direction-aware phrasing
    if s <= 20:
        if change < -3:
            verb = "drops to"
        elif change > 2:
            verb = "recovers slightly to"
        else:
            verb = "still deep at"
    else:
        if change > 3:
            verb = "climbs to"
        elif change < -2:
            verb = "pulls back to"
        else:
            verb = "holds strong at"

    tweet = f"{NAMES[name]} Fear & Greed {verb} {s} — {label}."

    # Add component detail
    detail = get_component_detail(data, name)
    if detail:
        tweet += f"\n\n{detail}"

    # Add contrast with another market
    contrast = add_contrast(data, name)
    if contrast:
        highest, h_score, lowest, l_score = get_highest_lowest(data)
        gap = h_score - l_score
        tweet += f"\n\n{contrast}"
        if gap >= 40:
            tweet += f"\n{gap} points separate the two."

    return tweet, 95


def detect_big_mover(data):
    """Detector 2: One asset moved significantly today (|change| > 6)."""
    changes = {name: get_daily_change(data, name) for name in ASSETS}
    biggest = max(changes, key=lambda k: abs(changes[k]))
    change = changes[biggest]

    if abs(change) < 6:
        return None, 0

    s = round(data[biggest]['score'])
    direction = "jumps" if change > 0 else "drops"
    sign = "+" if change > 0 else ""

    tweet = f"{NAMES[biggest]} {direction} {sign}{round(change)} pts today."
    tweet += f"\n\n{ICONS[biggest]} Now at {s} ({get_label(s)})."

    contrast = add_contrast(data, biggest)
    if contrast:
        tweet += f"\n\n{contrast}"

    return tweet, 85


def detect_divergence(data):
    """Detector 3: Risk-on vs risk-off diverging (spread > 25)."""
    risk_on_avg = (data['stocks']['score'] + data['crypto']['score']) / 2
    risk_off_avg = (data['bonds']['score'] + data['gold']['score']) / 2
    spread = abs(risk_on_avg - risk_off_avg)

    if spread < 25:
        return None, 0

    scores = get_scores(data)

    if risk_off_avg > risk_on_avg:
        tweet = "Safe havens leading while risk assets lag.\n\n"
        tweet += f"🪙 Gold {scores['gold']} · 📊 Bonds {scores['bonds']}\n"
        tweet += f"📈 Stocks {scores['stocks']} · 🟠 Crypto {scores['crypto']}\n\n"
        tweet += f"Defensive avg: {round(risk_off_avg)} vs Risk avg: {round(risk_on_avg)}."
    else:
        tweet = "Risk assets surging, safe havens quiet.\n\n"
        tweet += f"📈 Stocks {scores['stocks']} · 🟠 Crypto {scores['crypto']}\n"
        tweet += f"🪙 Gold {scores['gold']} · 📊 Bonds {scores['bonds']}\n\n"
        tweet += f"Risk avg: {round(risk_on_avg)} vs Defensive avg: {round(risk_off_avg)}."

    return tweet, 75


def detect_zone_crossing(data):
    """Detector 4: An asset changed sentiment zone vs yesterday."""
    crossings = []
    for name in ASSETS:
        history = get_history(data, name, 2)
        if len(history) >= 2:
            old_label = get_label(history[1]['score'])
            new_label = get_label(history[0]['score'])
            if old_label != new_label:
                crossings.append((name, old_label, new_label, round(history[0]['score'])))

    if not crossings:
        return None, 0

    if len(crossings) >= 2:
        lines = [f"{ICONS[n]} {NAMES[n]}: {old} → {new} ({s})" for n, old, new, s in crossings]
        tweet = "Sentiment shifts across markets.\n\n" + "\n".join(lines)
        return tweet, 70

    name, old_l, new_l, s = crossings[0]
    tweet = f"{NAMES[name]} shifts from {old_l} to {new_l}."
    tweet += f"\n\n{ICONS[name]} Now at {s}/100."

    streak = get_streak(data, name)
    if abs(streak) >= 3:
        direction = "rising" if streak > 0 else "falling"
        tweet += f" {direction.capitalize()} {abs(streak)} days straight."

    contrast = add_contrast(data, name)
    if contrast:
        tweet += f"\n\n{contrast}"

    return tweet, 70


def detect_streak(data):
    """Detector 5: An asset rising/falling 5+ days straight."""
    best_name = None
    best_streak = 0
    for name in ASSETS:
        streak = get_streak(data, name)
        if abs(streak) > abs(best_streak):
            best_streak = streak
            best_name = name

    if abs(best_streak) < 5:
        return None, 0

    s = round(data[best_name]['score'])
    direction = "rising" if best_streak > 0 else "falling"

    tweet = f"{NAMES[best_name]} {direction} {abs(best_streak)} days straight."
    tweet += f"\n\n{ICONS[best_name]} Now at {s} ({get_label(s)})."

    contrast = add_contrast(data, best_name)
    if contrast:
        tweet += f"\n\n{contrast}"

    return tweet, 65


def detect_all_aligned(data):
    """Detector 6: All 4 assets moving in the same direction."""
    changes = {name: get_daily_change(data, name) for name in ASSETS}

    all_up = all(c > 1 for c in changes.values())
    all_down = all(c < -1 for c in changes.values())

    if not all_up and not all_down:
        return None, 0

    scores = get_scores(data)

    if all_up:
        tweet = "All 4 markets trending toward Greed today.\n\n"
    else:
        tweet = "All 4 markets trending toward Fear today.\n\n"

    tweet += f"🪙 Gold {scores['gold']} · 📊 Bonds {scores['bonds']}\n"
    tweet += f"📈 Stocks {scores['stocks']} · 🟠 Crypto {scores['crypto']}"

    return tweet, 60


def detect_biggest_gap(data):
    """Detector 7: Huge gap between highest and lowest (> 40 pts)."""
    highest, h_score, lowest, l_score = get_highest_lowest(data)
    gap = h_score - l_score

    if gap < 40:
        return None, 0

    tweet = f"{gap} points separate {NAMES[highest]} from {NAMES[lowest]}.\n\n"
    tweet += f"{ICONS[highest]} {NAMES[highest]}: {h_score} ({get_label(h_score)})\n"
    tweet += f"{ICONS[lowest]} {NAMES[lowest]}: {l_score} ({get_label(l_score)})"

    if h_score >= 70 and l_score <= 30:
        tweet += "\n\nOne in Greed, the other in Fear."
    else:
        tweet += "\n\nVery different stories across markets."

    return tweet, 55


def detect_weekly_move(data):
    """Detector 8: Significant move over 7 days (|change| > 10)."""
    changes = {name: get_weekly_change(data, name) for name in ASSETS}
    biggest = max(changes, key=lambda k: abs(changes[k]))
    change = changes[biggest]

    if abs(change) < 10:
        return None, 0

    s = round(data[biggest]['score'])
    direction = "gained" if change > 0 else "lost"

    tweet = f"{NAMES[biggest]} {direction} {abs(round(change))} pts this week."
    tweet += f"\n\n{ICONS[biggest]} Now at {s} ({get_label(s)})."

    contrast = add_contrast(data, biggest)
    if contrast:
        tweet += f"\n\n{contrast}"

    return tweet, 50


def detect_component_extreme(data):
    """Detector 9: A sub-component maxed out (score <= 5 or >= 95)."""
    component_labels = {
        'gold': {
            'gld_price': 'gold price momentum',
            'momentum': 'RSI & moving averages',
            'dollar_index': 'dollar weakness',
            'real_rates': 'real interest rates',
            'vix': 'VIX',
        },
        'stocks': {
            'price_strength': 'S&P 500 strength',
            'vix': 'VIX',
            'momentum': 'RSI & moving averages',
            'market_breadth': 'market breadth',
            'junk_bonds': 'junk bond demand',
            'safe_haven': 'safe haven demand',
            'sector_rotation': 'sector rotation',
        },
        'bonds': {
            'yield_curve': 'the yield curve',
            'duration_risk': 'TLT momentum',
            'credit_quality': 'credit quality',
            'real_rates': 'real interest rates',
            'bond_volatility': 'bond volatility',
            'equity_vs_bonds': 'equity vs bonds rotation',
        },
        'crypto': {
            'context': '30-day price trend',
            'momentum': 'RSI & moving averages',
            'dominance': 'BTC vs altcoin rotation',
            'volume': 'trading volume',
            'volatility': 'price volatility',
        },
    }

    for name in ASSETS:
        components = data[name].get('components', {})
        for comp_key, comp_data in components.items():
            score = comp_data['score']
            if score <= 5 or score >= 95:
                comp_name = component_labels.get(name, {}).get(comp_key, comp_key)
                s = round(data[name]['score'])
                detail = comp_data.get('detail', '')

                side = "fear" if score <= 5 else "greed"
                tweet = f"{NAMES[name]} at {s} ({get_label(s)})."
                tweet += f"\n\nUnder the hood: {comp_name} is maxed out on the {side} side."

                if detail:
                    tweet += f"\n{detail}."

                return tweet, 45

    return None, 0


def detect_calm(data):
    """Detector 10: Calm day fallback — still tells a mini-story."""
    scores = get_scores(data)
    highest, h_score, lowest, l_score = get_highest_lowest(data)
    gap = h_score - l_score

    tweet = "Markets today.\n\n"
    tweet += f"🪙 Gold {scores['gold']} · 📊 Bonds {scores['bonds']}\n"
    tweet += f"📈 Stocks {scores['stocks']} · 🟠 Crypto {scores['crypto']}\n\n"

    if gap >= 20:
        tweet += f"{NAMES[highest]} leads, {NAMES[lowest]} trails. Watching for the next move."
    else:
        tweet += "Everything close together. Calm before something moves."

    return tweet, 10


# ─── Main logic ───


def generate_best_tweet(data):
    """Try all detectors and pick the highest-priority story."""
    detectors = [
        detect_extreme,
        detect_big_mover,
        detect_divergence,
        detect_zone_crossing,
        detect_streak,
        detect_all_aligned,
        detect_biggest_gap,
        detect_weekly_move,
        detect_component_extreme,
        detect_calm,
    ]

    best_tweet = None
    best_priority = -1

    for detector in detectors:
        tweet, priority = detector(data)
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
        print("Required: TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET")
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

    print(f"--- Tweet ({len(tweet)}/280 chars) ---")
    print(tweet)
    print("---")

    if dry_run:
        print("\n[DRY RUN] Tweet not posted.")
    else:
        post_tweet(tweet)


if __name__ == '__main__':
    main()
