"""
send_alerts.py - Send email alerts when an index changes zone significantly.

Tracks 5 indices: Gold, Bonds, Stocks, Crypto + Market Sentiment.
Compares current labels/scores with previous values.
Alert triggers: zone change + score delta >= threshold (7pts assets, 5pts sentiment).
Sends personalized emails to Resend audience subscribers based on their preferences.

Run: python send_alerts.py
Env: RESEND_API_KEY, RESEND_AUDIENCE_ID
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
RESEND_AUDIENCE_ID = os.environ.get('RESEND_AUDIENCE_ID')
FROM_EMAIL = 'OnOff.Markets <newsletter@onoff.markets>'

ASSETS = {
    'gold':   {'file': 'data/gold-fear-greed.json',   'name': 'Gold',   'icon': '\U0001fa99', 'url': 'https://onoff.markets/gold.html'},
    'bonds':  {'file': 'data/bonds-fear-greed.json',   'name': 'Bonds',  'icon': '\U0001f4ca', 'url': 'https://onoff.markets/bonds.html'},
    'stocks': {'file': 'data/stocks-fear-greed.json',  'name': 'Stocks', 'icon': '\U0001f4c8', 'url': 'https://onoff.markets/stocks.html'},
    'crypto': {'file': 'data/crypto-fear-greed.json',  'name': 'Crypto', 'icon': '\u20bf',     'url': 'https://onoff.markets/crypto.html'},
}

PREVIOUS_LABELS_FILE = 'data/previous-labels.json'
PREVIOUS_SCORES_FILE = 'data/previous-scores.json'

# Delta thresholds: minimum score change required (in addition to zone change)
DELTA_THRESHOLD_ASSET = 7      # for gold, bonds, stocks, crypto
DELTA_THRESHOLD_SENTIMENT = 5  # for market sentiment

ZONE_COLORS = {
    'Extreme Fear': '#ef4444',
    'Fear': '#f59e0b',
    'Neutral': '#888888',
    'Greed': '#22c55e',
    'Extreme Greed': '#06b6d4',
}


def get_label(score):
    rounded = round(score)
    if rounded <= 25: return 'Extreme Fear'
    if rounded <= 45: return 'Fear'
    if rounded <= 55: return 'Neutral'
    if rounded <= 75: return 'Greed'
    return 'Extreme Greed'


def load_current_scores():
    """Load current score and label for each asset + compute sentiment."""
    current = {}
    for key, config in ASSETS.items():
        path = Path(config['file'])
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            current[key] = {
                'score': data.get('score'),
                'label': data.get('label'),
                'history': data.get('history', []),
            }

    # Compute Market Sentiment (Risk-On vs Risk-Off)
    if all(k in current for k in ['gold', 'bonds', 'stocks', 'crypto']):
        risk_on = (current['stocks']['score'] + current['crypto']['score']) / 2
        risk_off = (current['bonds']['score'] + current['gold']['score']) / 2
        sentiment_score = round(((risk_on - risk_off + 100) / 200) * 100, 1)
        current['sentiment'] = {
            'score': sentiment_score,
            'label': get_label(sentiment_score),
            'history': [],
        }

    return current


def load_previous_labels():
    path = Path(PREVIOUS_LABELS_FILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_previous_scores():
    path = Path(PREVIOUS_SCORES_FILE)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_current_state(current):
    """Save both labels and scores for next run."""
    labels = {key: val['label'] for key, val in current.items()}
    scores = {key: val['score'] for key, val in current.items()}
    with open(PREVIOUS_LABELS_FILE, 'w') as f:
        json.dump(labels, f, indent=2)
    with open(PREVIOUS_SCORES_FILE, 'w') as f:
        json.dump(scores, f, indent=2)


def get_context(key, current, new_label):
    """Generate a dynamic context line based on historical data."""
    if key == 'sentiment':
        return None

    history = current.get(key, {}).get('history', [])
    if not history or len(history) < 2:
        return None

    sorted_hist = sorted(history, key=lambda x: x['date'], reverse=True)

    # Find last time this asset was in the same zone
    last_time = None
    for entry in sorted_hist[1:]:  # skip today
        if get_label(entry['score']) == new_label:
            last_time = entry['date']
            break

    if last_time:
        days_ago = (datetime.now() - datetime.strptime(last_time, '%Y-%m-%d')).days
        if days_ago <= 1:
            return None
        elif days_ago < 7:
            return f"Was in {new_label} {days_ago} days ago."
        elif days_ago < 60:
            weeks = days_ago // 7
            return f"Last time in {new_label}: {weeks} week{'s' if weeks > 1 else ''} ago."
        else:
            date_obj = datetime.strptime(last_time, '%Y-%m-%d')
            return f"Last time in {new_label}: {date_obj.strftime('%B %d, %Y')}."
    else:
        return f"First time in {new_label} in over a year."


def find_changes(current, previous_labels, previous_scores):
    """Find indices where zone changed AND score delta exceeds threshold."""
    all_config = {
        **{k: v for k, v in ASSETS.items()},
        'sentiment': {
            'name': 'Market Sentiment',
            'icon': '\U0001f310',
            'url': 'https://onoff.markets/',
        }
    }

    changes = []
    for key, data in current.items():
        prev_label = previous_labels.get(key)
        curr_label = data['label']
        curr_score = data['score']
        prev_score = previous_scores.get(key)

        # Must have a zone change
        if not prev_label or not curr_label or prev_label == curr_label:
            continue

        # Must exceed delta threshold
        threshold = DELTA_THRESHOLD_SENTIMENT if key == 'sentiment' else DELTA_THRESHOLD_ASSET
        if prev_score is not None:
            delta = abs(curr_score - prev_score)
            if delta < threshold:
                print(f"  SKIP: {key} zone changed ({prev_label} -> {curr_label}) but delta {delta:.1f} < {threshold}")
                continue

        config = all_config.get(key, {})
        context = get_context(key, current, curr_label)
        changes.append({
            'key': key,
            'name': config.get('name', key),
            'icon': config.get('icon', ''),
            'url': config.get('url', 'https://onoff.markets'),
            'score': curr_score,
            'old_label': prev_label,
            'new_label': curr_label,
            'context': context,
        })
    return changes


def fetch_subscribers():
    """Fetch all active subscribers from Resend audience."""
    if not RESEND_AUDIENCE_ID:
        print("  RESEND_AUDIENCE_ID not set")
        return []

    url = f'https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts'
    response = requests.get(url, headers={
        'Authorization': f'Bearer {RESEND_API_KEY}',
    })

    if response.status_code != 200:
        print(f"  ERROR fetching subscribers: {response.status_code} {response.text}")
        return []

    result = response.json()
    contacts = result.get('data', [])

    subscribers = []
    for contact in contacts:
        if contact.get('unsubscribed'):
            continue
        email = contact.get('email')
        prefs_str = contact.get('first_name', '')
        prefs = [p.strip() for p in prefs_str.split(',') if p.strip()] if prefs_str else []
        subscribers.append({
            'email': email,
            'preferences': prefs,
        })

    return subscribers


def filter_changes_for_subscriber(changes, preferences):
    """Filter changes based on subscriber's asset preferences."""
    if not preferences:
        return changes
    return [c for c in changes if c['key'] in preferences]


def build_email_subject(changes):
    if len(changes) == 1:
        c = changes[0]
        return f"{c['icon']} {c['name']} just entered {c['new_label']} ({round(c['score'])}/100)"
    names = ', '.join(c['name'] for c in changes)
    return f"Zone change: {names}"


def build_email_html(changes):
    blocks = []
    for c in changes:
        color = ZONE_COLORS.get(c['new_label'], '#ffffff')
        old_color = ZONE_COLORS.get(c['old_label'], '#888888')
        score = round(c['score'])

        context_html = ''
        if c.get('context'):
            context_html = f"""
            <div style="font-size: 13px; color: #777; margin-bottom: 16px; font-style: italic;">
                {c['context']}
            </div>"""

        blocks.append(f"""
        <div style="margin-bottom: 32px;">
            <div style="font-size: 14px; color: #999; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px;">
                {c['icon']} {c['name']}
            </div>
            <div style="font-size: 42px; font-weight: 800; color: {color}; margin-bottom: 4px;">
                {score}<span style="font-size: 18px; color: #666; font-weight: 400;">/100</span>
            </div>
            <div style="font-size: 16px; margin-bottom: 12px;">
                <span style="color: {old_color};">{c['old_label']}</span>
                <span style="color: #555;"> &rarr; </span>
                <span style="color: {color}; font-weight: 600;">{c['new_label']}</span>
            </div>{context_html}
            <a href="{c['url']}" style="color: {color}; text-decoration: none; font-size: 14px;">
                View full breakdown &rarr;
            </a>
        </div>""")

    body = '\n'.join(blocks)

    return f"""
    <div style="background: #0a0a0a; color: #ffffff; padding: 40px 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 480px; margin: 0 auto;">
            <div style="text-align: center; margin-bottom: 32px;">
                <span style="font-size: 18px; font-weight: 700; color: #fff;">On<span style="color: #888;">\u25cf\u25cf</span>Off<span style="color: #666; font-weight: 400;">.Markets</span></span>
            </div>

            {body}

            <div style="border-top: 1px solid #222; margin-top: 32px; padding-top: 20px; font-size: 12px; color: #555; text-align: center;">
                <a href="https://onoff.markets" style="color: #666; text-decoration: none;">onoff.markets</a>
                &nbsp;|&nbsp; Real-time market sentiment
                <br><br>
                <span style="font-size: 11px;">To unsubscribe, visit <a href="https://onoff.markets" style="color: #666;">onoff.markets</a> and click Alerts.</span>
            </div>
        </div>
    </div>"""


def send_email(subject, html, to_email):
    response = requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {RESEND_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'from': FROM_EMAIL,
            'to': [to_email],
            'reply_to': 'contact@onoff.markets',
            'subject': subject,
            'html': html,
        }
    )

    if response.status_code == 200:
        print(f"  Email sent to {to_email}")
        return True
    else:
        print(f"  ERROR sending email: {response.status_code} {response.text}")
        return False


def main():
    print("Checking for zone changes...")

    if not RESEND_API_KEY:
        print("  RESEND_API_KEY not set, skipping alerts")
        return

    current = load_current_scores()
    previous_labels = load_previous_labels()
    previous_scores = load_previous_scores()

    if not previous_labels:
        print("  No previous labels found (first run). Saving current state.")
        save_current_state(current)
        return

    changes = find_changes(current, previous_labels, previous_scores)

    if not changes:
        print("  No significant zone changes detected.")
    else:
        for c in changes:
            ctx = f" ({c['context']})" if c.get('context') else ''
            print(f"  CHANGE: {c['name']} {c['old_label']} -> {c['new_label']} (score: {c['score']}){ctx}")

        # Fetch subscribers from Resend audience
        subscribers = fetch_subscribers()

        if not subscribers:
            print("  No subscribers found.")
        else:
            print(f"  Sending to {len(subscribers)} subscriber(s)...")
            sent = 0
            for sub in subscribers:
                sub_changes = filter_changes_for_subscriber(changes, sub['preferences'])
                if not sub_changes:
                    print(f"  SKIP {sub['email']} (no matching preferences)")
                    continue

                subject = build_email_subject(sub_changes)
                html = build_email_html(sub_changes)
                if send_email(subject, html, sub['email']):
                    sent += 1
                # Rate limit: Resend allows max 2 req/s
                time.sleep(0.6)

            print(f"  Done: {sent} email(s) sent.")

    # Always save current state for next run
    save_current_state(current)


if __name__ == '__main__':
    main()
