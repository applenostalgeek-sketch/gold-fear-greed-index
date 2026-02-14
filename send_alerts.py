"""
send_alerts.py - Send email alerts when an index changes zone.

Tracks 5 indices: Gold, Bonds, Stocks, Crypto + Market Sentiment.
Compares current labels with previous labels stored in data/previous-labels.json.
If any index changed zone (e.g. Greed -> Extreme Greed), sends an email via Resend
with dynamic context from historical data.

Run: python send_alerts.py
Env: RESEND_API_KEY, ALERT_EMAIL (recipient)
"""

import json
import os
import requests
from pathlib import Path
from datetime import datetime

RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
ALERT_EMAIL = os.environ.get('ALERT_EMAIL', 'contact@onoff.markets')
FROM_EMAIL = 'OnOff.Markets <newsletter@onoff.markets>'

ASSETS = {
    'gold':   {'file': 'data/gold-fear-greed.json',   'name': 'Gold',   'icon': '\U0001fa99', 'url': 'https://onoff.markets/gold.html'},
    'bonds':  {'file': 'data/bonds-fear-greed.json',   'name': 'Bonds',  'icon': '\U0001f4ca', 'url': 'https://onoff.markets/bonds.html'},
    'stocks': {'file': 'data/stocks-fear-greed.json',  'name': 'Stocks', 'icon': '\U0001f4c8', 'url': 'https://onoff.markets/stocks.html'},
    'crypto': {'file': 'data/crypto-fear-greed.json',  'name': 'Crypto', 'icon': '\u20bf',     'url': 'https://onoff.markets/crypto.html'},
}

PREVIOUS_LABELS_FILE = 'data/previous-labels.json'

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


def save_current_labels(current):
    labels = {key: val['label'] for key, val in current.items()}
    with open(PREVIOUS_LABELS_FILE, 'w') as f:
        json.dump(labels, f, indent=2)


def get_context(key, current, new_label):
    """Generate a dynamic context line based on historical data."""
    # For sentiment, no history file
    if key == 'sentiment':
        return None

    history = current.get(key, {}).get('history', [])
    if not history or len(history) < 2:
        return None

    sorted_hist = sorted(history, key=lambda x: x['date'], reverse=True)

    # Find last time this asset was in the same zone
    last_time = None
    for entry in sorted_hist[1:]:  # skip today
        if entry.get('label') == new_label:
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
        # Never been in this zone in available history
        return f"First time in {new_label} in over a year."


def find_changes(current, previous):
    """Find indices where the zone label changed."""
    # Config for sentiment (not in ASSETS dict)
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
        prev_label = previous.get(key)
        curr_label = data['label']
        if prev_label and curr_label and prev_label != curr_label:
            config = all_config.get(key, {})
            context = get_context(key, current, curr_label)
            changes.append({
                'key': key,
                'name': config.get('name', key),
                'icon': config.get('icon', ''),
                'url': config.get('url', 'https://onoff.markets'),
                'score': data['score'],
                'old_label': prev_label,
                'new_label': curr_label,
                'context': context,
            })
    return changes


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
    previous = load_previous_labels()

    if not previous:
        print("  No previous labels found (first run). Saving current labels.")
        save_current_labels(current)
        return

    changes = find_changes(current, previous)

    if not changes:
        print("  No zone changes detected.")
    else:
        for c in changes:
            ctx = f" ({c['context']})" if c.get('context') else ''
            print(f"  CHANGE: {c['name']} {c['old_label']} -> {c['new_label']} (score: {c['score']}){ctx}")

        subject = build_email_subject(changes)
        html = build_email_html(changes)
        send_email(subject, html, ALERT_EMAIL)

    # Always save current labels for next run
    save_current_labels(current)


if __name__ == '__main__':
    main()
