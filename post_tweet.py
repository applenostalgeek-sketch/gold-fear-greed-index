#!/usr/bin/env python3
"""
Post daily Fear & Greed Index tweet to Twitter/X.
Reads the 4 JSON data files and picks the most interesting "story" of the day.

Every tweet follows the same structure:
  [Headline — the story of the day]
  [Dashboard — all 4 scores, always]
  [Optional context line]
  [URL]

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
PLURAL = {'stocks', 'bonds'}
URL = "onoff.markets"


def conj(name, s_form, p_form):
    """Conjugate: s_form for Gold/Crypto (singular), p_form for Stocks/Bonds (plural)."""
    return p_form if name in PLURAL else s_form


def dashboard(data):
    """Build the 4-score dashboard block."""
    scores = get_scores(data)
    return (f"🪙 Gold {scores['gold']} · 📊 Bonds {scores['bonds']}\n"
            f"📈 Stocks {scores['stocks']} · 🟠 Crypto {scores['crypto']}")


def build_tweet(headline, data, context=None):
    """Assemble tweet: headline + optional context + URL (image attached separately)."""
    parts = [headline.strip()]
    if context:
        parts.append(context.strip())
    parts.append(URL)
    tweet = "\n\n".join(parts)
    # Drop context if too long
    if len(tweet) > 280 and context:
        parts = [headline.strip(), URL]
        tweet = "\n\n".join(parts)
    return tweet


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
        lines = [f"{ICONS[n]} {NAMES[n]}: {s} — {get_label(s)}" for n, s in extremes]
        headline = "Multiple extreme readings today.\n" + "\n".join(lines)
        highest, h_score, _, l_score = get_highest_lowest(data)
        gap = h_score - l_score
        context = f"{gap} pts gap across markets." if gap >= 30 else None
        return build_tweet(headline, data, context), 100

    # Single extreme
    name, s = extremes[0]
    label = get_label(s)
    change = get_daily_change(data, name)

    if s <= 20:
        if change < -3:
            verb = conj(name, "drops to", "drop to")
        elif change > 2:
            verb = conj(name, "recovers to", "recover to")
        else:
            verb = "still deep at"
    else:
        if change > 3:
            verb = conj(name, "climbs to", "climb to")
        elif change < -2:
            verb = conj(name, "pulls back to", "pull back to")
        else:
            verb = "holding strong at"

    headline = f"{ICONS[name]} {NAMES[name]} {verb} {s} — {label}."
    detail = get_component_detail(data, name)
    return build_tweet(headline, data, detail), 95


def detect_big_mover(data):
    """Detector 2: One asset moved significantly today (|change| > 6)."""
    changes = {name: get_daily_change(data, name) for name in ASSETS}
    biggest = max(changes, key=lambda k: abs(changes[k]))
    change = changes[biggest]

    if abs(change) < 6:
        return None, 0

    s = round(data[biggest]['score'])
    if change > 0:
        direction = conj(biggest, "jumps", "jump")
    else:
        direction = conj(biggest, "drops", "drop")

    headline = (f"{ICONS[biggest]} {NAMES[biggest]} {direction} "
                f"{abs(round(change))} pts today — now at {s} ({get_label(s)}).")

    return build_tweet(headline, data), 85


def detect_divergence(data):
    """Detector 3: Risk-on vs risk-off diverging (spread > 25)."""
    risk_on_avg = (data['stocks']['score'] + data['crypto']['score']) / 2
    risk_off_avg = (data['bonds']['score'] + data['gold']['score']) / 2
    spread = abs(risk_on_avg - risk_off_avg)

    if spread < 25:
        return None, 0

    if risk_off_avg > risk_on_avg:
        headline = "Safe havens leading, risk assets lagging."
        context = f"Defensive avg: {round(risk_off_avg)} vs Risk avg: {round(risk_on_avg)}."
    else:
        headline = "Risk assets surging, safe havens quiet."
        context = f"Risk avg: {round(risk_on_avg)} vs Defensive avg: {round(risk_off_avg)}."

    return build_tweet(headline, data, context), 75


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
        headline = "Sentiment shifts across markets.\n" + "\n".join(lines)
        return build_tweet(headline, data), 70

    name, old_l, new_l, s = crossings[0]
    headline = f"{ICONS[name]} {NAMES[name]} {conj(name, 'shifts', 'shift')} from {old_l} to {new_l} ({s})."

    streak = get_streak(data, name)
    context = None
    if abs(streak) >= 3:
        direction = "rising" if streak > 0 else "falling"
        context = f"{direction.capitalize()} {abs(streak)} days straight."

    return build_tweet(headline, data, context), 70


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

    headline = (f"{ICONS[best_name]} {NAMES[best_name]} {direction} "
                f"{abs(best_streak)} days straight — now at {s} ({get_label(s)}).")

    return build_tweet(headline, data), 65


def detect_all_aligned(data):
    """Detector 6: All 4 assets moving in the same direction."""
    changes = {name: get_daily_change(data, name) for name in ASSETS}

    all_up = all(c > 1 for c in changes.values())
    all_down = all(c < -1 for c in changes.values())

    if not all_up and not all_down:
        return None, 0

    if all_up:
        headline = "All 4 markets trending toward Greed today."
    else:
        headline = "All 4 markets trending toward Fear today."

    return build_tweet(headline, data), 60


def detect_biggest_gap(data):
    """Detector 7: Huge gap between highest and lowest (> 40 pts)."""
    highest, h_score, lowest, l_score = get_highest_lowest(data)
    gap = h_score - l_score

    if gap < 40:
        return None, 0

    headline = f"{gap} pts separate {NAMES[highest]} ({h_score}) from {NAMES[lowest]} ({l_score})."

    context = None
    if h_score >= 70 and l_score <= 30:
        context = "One in Greed, the other in Fear."

    return build_tweet(headline, data, context), 55


def detect_weekly_move(data):
    """Detector 8: Significant move over 7 days (|change| > 10)."""
    changes = {name: get_weekly_change(data, name) for name in ASSETS}
    biggest = max(changes, key=lambda k: abs(changes[k]))
    change = changes[biggest]

    if abs(change) < 10:
        return None, 0

    s = round(data[biggest]['score'])
    if change > 0:
        direction = conj(biggest, "gains", "gain")
    else:
        direction = conj(biggest, "loses", "lose")

    headline = (f"{ICONS[biggest]} {NAMES[biggest]} {direction} "
                f"{abs(round(change))} pts this week — now at {s} ({get_label(s)}).")

    return build_tweet(headline, data), 50


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
            'market_participation': 'market participation',
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
                side = "fear" if score <= 5 else "greed"

                headline = (f"{ICONS[name]} {NAMES[name]} at {s} ({get_label(s)}) "
                            f"— {comp_name} maxed on {side} side.")

                return build_tweet(headline, data), 45

    return None, 0


def detect_calm(data):
    """Detector 10: Calm day fallback — still tells a mini-story."""
    highest, h_score, lowest, l_score = get_highest_lowest(data)
    gap = h_score - l_score

    headline = "Market sentiment today."

    if gap >= 20:
        context = (f"{NAMES[highest]} {conj(highest, 'leads', 'lead')}, "
                   f"{NAMES[lowest]} {conj(lowest, 'trails', 'trail')}.")
    else:
        context = "All markets close together. Watching for the next move."

    return build_tweet(headline, data, context), 10


# ─── Main logic ───


def load_ai_context():
    """Load tweet text from market-summary.json, fall back to first sentence of summary."""
    try:
        with open('data/market-summary.json', 'r') as f:
            data = json.load(f)

        # Prefer dedicated tweet field
        tweet = data.get('tweet', '')
        if tweet and len(tweet) >= 20:
            return tweet

        # Fall back to first sentence of summary
        summary = data.get('summary', '')
        if not summary or len(summary) < 20:
            return None
        import re
        match = re.search(r'(?<![A-Z])\.\s', summary)
        if match and match.start() < 200:
            return summary[:match.start() + 1]
        if len(summary) > 200:
            truncated = summary[:200]
            last_space = truncated.rfind(' ')
            if last_space > 100:
                return truncated[:last_space] + '...'
        return summary if len(summary) <= 200 else summary[:197] + '...'
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def generate_best_tweet(data):
    """Try AI context first, then fall back to story detectors."""
    # Try AI context as headline
    ai_headline = load_ai_context()
    if ai_headline:
        tweet = build_tweet(ai_headline, data)
        if len(tweet) <= 280:
            return tweet

    # Fallback: story detectors (priority order)
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


def upload_image():
    """Upload og-home.png via Twitter API v1.1. Returns media_id or None."""
    try:
        import tweepy
    except ImportError:
        return None

    image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'og-home.png')
    if not os.path.exists(image_path):
        print("Warning: og-home.png not found, tweeting without image.")
        return None

    api_key = os.environ.get('TWITTER_API_KEY')
    api_secret = os.environ.get('TWITTER_API_SECRET')
    access_token = os.environ.get('TWITTER_ACCESS_TOKEN')
    access_secret = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')

    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api = tweepy.API(auth)
        media = api.media_upload(image_path)
        print(f"Image uploaded: media_id={media.media_id}")
        return media.media_id
    except Exception as e:
        print(f"Warning: Image upload failed ({e}), tweeting without image.")
        return None


def post_tweet(tweet_text):
    """Post the tweet using Tweepy, with optional image."""
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

    # Upload image first
    media_id = upload_image()

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    try:
        kwargs = {'text': tweet_text}
        if media_id:
            kwargs['media_ids'] = [media_id]
        response = client.create_tweet(**kwargs)
        tweet_id = response.data['id']
        print(f"Tweet posted successfully! ID: {tweet_id}")
        return tweet_id
    except tweepy.Forbidden as e:
        print(f"Error 403 Forbidden: {e}")
        print("This usually means a duplicate tweet. Scores may not have changed enough.")
        sys.exit(1)
    except tweepy.TweepyException as e:
        print(f"Twitter API error: {e}")
        sys.exit(1)


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
