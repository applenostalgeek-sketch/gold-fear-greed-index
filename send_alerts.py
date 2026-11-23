"""
send_alerts.py - Email subscribers when a market's mood changes sharply or hits an extreme.

Two kinds of alert, merged into one email per subscriber and per day:
  - Sharp move: an index changes zone AND moves at least N points since yesterday
    (gold 11, stocks 8, crypto 8, bonds 7, sentiment 7). Arriving in Neutral never alerts.
  - New extreme: an index is at its lowest (or highest) for at least 180 days.
    One email per episode: none if the same kind of record already happened in the
    previous 30 days, so a slide that keeps deepening does not email every morning.
Each subscriber only gets the indices they chose. The short AI context (the tweet
text) opens the email when today's text came from the model (source "ai").

Run: python send_alerts.py
Env: RESEND_API_KEY, RESEND_AUDIENCE_ID
     ALERT_TEST_TO=<address>  test mode: send only to that address, ignore the quiet
                              period, and never save state.
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

# Delta thresholds: minimum score change required (in addition to zone change).
# Calibrated per asset from each index's own daily volatility + signal value:
#   gold   = noisy / no edge        -> strict (11)
#   stocks = real contrarian signal -> sensitive (8)
#   crypto = above its own jitter   -> 8 (catches multi-day slides into a new zone)
#   bonds  = low-vol, rarely > ~8   -> 7 (else it never alerts)
DELTA_THRESHOLDS_ASSET = {'gold': 11, 'stocks': 8, 'crypto': 8, 'bonds': 7}
DELTA_THRESHOLD_ASSET_DEFAULT = 10  # fallback for any unlisted asset key
DELTA_THRESHOLD_SENTIMENT = 7  # for market sentiment

# Zones we do not email about. Neutral is not a mood, it is the absence of one:
# an alert saying "nothing in particular is happening" interrupts a subscriber
# to tell them nothing. It is also the narrowest band (46-55 = 10 points, against
# 20 for Fear and Greed), so an index drifting through the middle crosses its
# edges twice as often as any other boundary — bonds sits in Neutral 39% of the
# time and crosses in or out 53 times a year.
#
# Measured over 5 years of history: Neutral was the destination of 73 of 181
# alerts (40%), and the least durable — still true five days later only 43% of
# the time, against 68% for both Fear and Greed. Dropping it takes the mailing
# from 36 to 22 alerts a year and removes exactly the ones that say nothing.
#
# A move that merely passes through Neutral on its way to Fear or Greed still
# alerts on arrival. Skipping a large drop straight into Neutral was considered
# and rejected: a two-boundary jump into Neutral happened 0 times in 5 years
# (it needs a >20-point day; the largest ever seen is 16.6), so the exception
# would have been dead code. If "big move" ever deserves an alert, it is its own
# feature, measured on its own terms — not a branch bolted onto zone logic.
SILENT_ZONES = {'Neutral'}

ZONE_STYLES = {
    'Extreme Fear': {'color': '#dc2626', 'bg': '#fef2f2'},
    'Fear':         {'color': '#d97706', 'bg': '#fffbeb'},
    'Neutral':      {'color': '#666666', 'bg': '#f5f5f5'},
    'Greed':        {'color': '#16a34a', 'bg': '#f0fdf4'},
    'Extreme Greed':{'color': '#0891b2', 'bg': '#ecfeff'},
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

    # Compute Market Sentiment (simple average of all 4 indices)
    if all(k in current for k in ['gold', 'bonds', 'stocks', 'crypto']):
        sentiment_score = round((current['gold']['score'] + current['stocks']['score'] + current['crypto']['score'] + current['bonds']['score']) / 4, 1)
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

        # ... to a zone worth an email
        if curr_label in SILENT_ZONES:
            print(f"  SKIP: {key} moved {prev_label} -> {curr_label} (silent zone)")
            continue

        # Must exceed delta threshold
        threshold = DELTA_THRESHOLD_SENTIMENT if key == 'sentiment' else DELTA_THRESHOLDS_ASSET.get(key, DELTA_THRESHOLD_ASSET_DEFAULT)
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


# ---------------------------------------------------------------------------
# New extremes ("lowest / highest since")
# ---------------------------------------------------------------------------
# Volumes measured over 4 years (Nov 2022 - Nov 2026): see the replay in the
# commit message. Sharp moves alone gave 15.5 emails a year to a subscriber to
# everything.
RECORD_MIN_DAYS = 180
RECORD_QUIET_DAYS = 30
HISTORY_5Y = 'data/history-5y-{}.json'


def _day(s):
    return datetime.strptime(s, '%Y-%m-%d')


def load_series():
    """date -> score for each index, 5-year file underneath and the published
    1-year file on top (the same merge the site's charts use). Market Sentiment
    is the plain average of the four, on the dates all four have."""
    series = {}
    for key, config in ASSETS.items():
        by_date = {}
        for path in (HISTORY_5Y.format(key), config['file']):
            try:
                with open(path) as f:
                    for row in json.load(f).get('history', []):
                        if row.get('score') is not None:
                            by_date[row['date']] = row['score']
            except Exception as e:
                print(f"  (series {key}: {path} unreadable: {e})")
        series[key] = by_date
    if all(series.get(k) for k in ASSETS):
        common = set.intersection(*(set(series[k]) for k in ASSETS))
        series['sentiment'] = {d: sum(series[k][d] for k in ASSETS) / 4 for d in common}
    return series


def _record_at(dates, values, i):
    """If values[i] is the lowest (or highest) for RECORD_MIN_DAYS or more,
    return (low, since): since is the last earlier date as low (as high), or
    None if no earlier value is. Lowest is checked first."""
    for low in (True, False):
        k = i - 1
        while k >= 0 and (values[k] > values[i] if low else values[k] < values[i]):
            k -= 1
        start = dates[k] if k >= 0 else dates[0]
        if (_day(dates[i]) - _day(start)).days >= RECORD_MIN_DAYS:
            return low, (dates[k] if k >= 0 else None)
    return None


def _tier(since, day):
    """How far back a record reaches: 1 = 6 months+, 2 = 1 year+, 3 = 3 years+,
    4 = 5 years (or never as low/high in the data, which starts 5 years back)."""
    if since is None:
        return 4
    gap = (_day(day) - _day(since)).days
    return 4 if gap >= 5 * 365 - 30 else 3 if gap >= 3 * 365 else 2 if gap >= 365 else 1


def find_records(series, today, ignore_quiet=False):
    """Indices whose score today is a new extreme worth an email.

    Records cluster: in a slide the index beats its record almost every day
    (46 record emails a year with no restraint). So an episode gets one email, and
    the episode lasts while records of the same kind keep coming less than 30 days
    apart. Within an episode, a new email goes out only when the record reaches a
    new horizon: 1 year, then 3 years, then 5 years. Without that, the first and
    weakest record ("lowest in 6 months") was the only one sent, and the stocks
    5-year low of April 2025 or the gold 5-year low of June 2026 were swallowed.
    Measured over 4 years: 22 record emails a year across the five indices."""
    records = []
    for key, by_date in series.items():
        dates = sorted(d for d in by_date if d <= today)
        if not dates or dates[-1] != today:
            continue
        values = [by_date[d] for d in dates]
        # Replay the history to know the episode in progress, if any.
        last = {True: None, False: None}
        top = {True: 0, False: 0}
        decision = None
        for i in range(len(dates)):
            r = _record_at(dates, values, i)
            if not r:
                continue
            low, since = r
            t = _tier(since, dates[i])
            in_episode = last[low] is not None and (_day(dates[i]) - _day(last[low])).days <= RECORD_QUIET_DAYS
            if not in_episode:
                top[low] = 0
            send = not in_episode or t > top[low]
            if send:
                top[low] = max(top[low], t)
            last[low] = dates[i]
            if i == len(dates) - 1:
                decision = (low, since, send)
        if not decision:
            continue
        low, since, send = decision
        if not send and not ignore_quiet:
            print(f"  SKIP: {key} {'lowest' if low else 'highest'} since {since} (same episode, same horizon)")
            continue
        records.append({'key': key, 'score': values[-1], 'label': get_label(values[-1]),
                        'low': low, 'since': since})
        print(f"  RECORD: {key} {'lowest' if low else 'highest'} since {since or 'the start of the data'} ({values[-1]:.1f})")
    return records


# ---------------------------------------------------------------------------
# AI context
# ---------------------------------------------------------------------------
def load_context(today):
    """The short AI text (the tweet), only when today's run wrote it and it came
    from the model and passed its checks. The 'fallback' text is generic, and an
    email cannot be corrected once sent: no text beats a doubtful one."""
    try:
        with open('data/market-summary.json') as f:
            s = json.load(f)
    except Exception:
        return None
    if s.get('date') != today or s.get('source') != 'ai':
        return None
    tweet = (s.get('tweet') or '').strip()
    return tweet or None


# ---------------------------------------------------------------------------
# Subscribers and email
# ---------------------------------------------------------------------------
NAMES = {**{k: v['name'] for k, v in ASSETS.items()}, 'sentiment': 'Market Sentiment'}
# Subject: a dot in the colour of the zone. An asset icon misleads (a rising chart
# in front of a 20-point drop).
ZONE_DOT = {'Extreme Fear': '\U0001f534', 'Fear': '\U0001f7e0', 'Neutral': '⚪',
            'Greed': '\U0001f7e2', 'Extreme Greed': '\U0001f535'}
UNSUB_URL = 'https://onoff.markets/.netlify/functions/unsub?c={}'


def _since_text(rec):
    word = 'Lowest' if rec['low'] else 'Highest'
    if not rec['since']:
        return f"{word} in 5 years"
    return f"{word} since {_day(rec['since']).strftime('%B %Y')}"


def build_items(changes, records):
    """One line per index: a sharp move and a record on the same index share it."""
    items = {}
    for c in changes:
        d = round(c['score'] - c['prev_score']) if c.get('prev_score') is not None else None
        items[c['key']] = {'key': c['key'], 'score': c['score'], 'label': c['new_label'], 'zone_change': True,
                           'move': d, 'from': c['old_label'], 'record': None}
    for r in records:
        it = items.setdefault(r['key'], {'key': r['key'], 'score': r['score'], 'label': r['label'],
                                         'zone_change': False, 'move': None, 'from': None, 'record': None})
        it['record'] = r
    order = ['sentiment', 'gold', 'stocks', 'bonds', 'crypto']
    return sorted(items.values(), key=lambda it: order.index(it['key']) if it['key'] in order else 9)


def build_email_subject(items):
    parts = []
    for it in items:
        dot, name = ZONE_DOT.get(it['label'], ''), NAMES.get(it['key'], it['key'])
        if it['zone_change'] and it['move'] is not None:
            sign = '+' if it['move'] > 0 else '−'
            parts.append(f"{dot} {name} {sign}{abs(it['move'])} pts, now {it['label']}")
        elif it['zone_change']:
            parts.append(f"{dot} {name} now {it['label']}")
        else:
            text = _since_text(it['record'])
            parts.append(f"{dot} {name}: {text[0].lower() + text[1:]}")
    more = f" · +{len(parts) - 2} more" if len(parts) > 2 else ''
    return ' · '.join(parts[:2]) + more


def html_escape(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;'))


LINE_HTML = """  <tr><td style="padding:18px 0;border-bottom:1px solid #e4e4e7;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td><div style="font-size:16px;font-weight:700;">{title}</div>
          <div style="font-size:13px;color:#71717a;margin-top:3px;">{notes}</div></td>
      <td align="right" style="font-size:30px;font-weight:800;color:{color};">{score}</td>
    </tr></table>
  </td></tr>"""

CONTEXT_HTML = """  <tr><td style="font-size:17px;line-height:1.6;color:#27272a;">{text}</td></tr>
  <tr><td style="padding-top:8px;font-size:11px;color:#a1a1aa;">Written by AI from today's data and news.</td></tr>
  <tr><td style="height:28px;"></td></tr>"""

EMAIL_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OnOff.Markets alert</title></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#18181b;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:28px 20px 40px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">
  <tr><td style="padding-bottom:28px;"><span style="font-size:17px;font-weight:800;">On <span style="color:#d4a017;">&#9679;&#9679;</span> Off<span style="color:#a1a1aa;font-weight:600;">.Markets</span></span>
    <span style="float:right;font-size:12px;color:#a1a1aa;line-height:24px;">{date}</span></td></tr>
{context}
  <tr><td style="border-top:1px solid #e4e4e7;"></td></tr>
{lines}
  <tr><td style="padding-top:28px;"><a href="https://onoff.markets/" style="display:inline-block;background:#18181b;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:11px 20px;border-radius:8px;">See today's readings &rarr;</a></td></tr>
  <tr><td style="padding-top:40px;font-size:12px;line-height:1.7;color:#a1a1aa;">Fear &amp; greed in gold, stocks, bonds and crypto, every morning. A thermometer, not advice.<br>
    <a href="https://onoff.markets/" style="color:#71717a;">Change alerts</a> &middot; <a href="{unsub}" style="color:#71717a;">Unsubscribe</a></td></tr>
</table></td></tr></table></body></html>"""


def _line_html(it):
    name = NAMES.get(it['key'], it['key'])
    color = ZONE_STYLES.get(it['label'], {'color': '#71717a'})['color']
    arrow = '&rarr;' if it['zone_change'] else '&middot;'
    title = f'{name} <span style="color:{color};">{arrow} {it["label"]}</span>'
    notes = []
    if it['zone_change']:
        if it['move'] is not None:
            notes.append(f"{'Up' if it['move'] > 0 else 'Down'} {abs(it['move'])} points today, from {it['from']}")
        else:
            notes.append(f"Was {it['from']}")
    if it['record']:
        text = _since_text(it['record'])
        notes.append(text if not notes else text[0].lower() + text[1:])
    return LINE_HTML.format(title=title, notes=' &middot; '.join(notes), color=color, score=round(it['score']))


def build_email_html(items, context, today, unsub_url):
    d = _day(today)
    return EMAIL_HTML.format(
        date=f"{d.strftime('%b')} {d.day}, {d.year}",
        context=CONTEXT_HTML.format(text=html_escape(context)) if context else '',
        lines='\n'.join(_line_html(it) for it in items),
        unsub=unsub_url)


def fetch_subscribers():
    """All active subscribers, following pages if the list is paginated."""
    if not RESEND_AUDIENCE_ID:
        print("  RESEND_AUDIENCE_ID not set")
        return []
    url = f'https://api.resend.com/audiences/{RESEND_AUDIENCE_ID}/contacts'
    contacts, params = [], {}
    for _ in range(50):
        response = requests.get(url, params=params, headers={'Authorization': f'Bearer {RESEND_API_KEY}'})
        if response.status_code != 200:
            print(f"  ERROR fetching subscribers: {response.status_code} {response.text}")
            return []
        result = response.json()
        page = result.get('data', [])
        contacts += page
        if not result.get('has_more') or not page:
            break
        params = {'limit': 100, 'after': page[-1]['id']}
        time.sleep(0.6)

    subscribers = []
    for contact in contacts:
        if contact.get('unsubscribed'):
            continue
        prefs_str = contact.get('first_name', '')
        prefs = [p.strip() for p in prefs_str.split(',') if p.strip()] if prefs_str else []
        subscribers.append({'id': contact.get('id'), 'email': contact.get('email'), 'preferences': prefs})
    return subscribers


def filter_items_for_subscriber(items, preferences):
    if not preferences:
        return items
    return [it for it in items if it['key'] in preferences]


def mask(email):
    """The repository is public, and so are its Actions logs: never print a
    subscriber's address in full."""
    name, _, domain = (email or '').partition('@')
    return (name[:1] + '***@' + domain) if domain else '***'


def send_email(subject, html, to_email, unsub_url):
    response = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
        json={
            'from': FROM_EMAIL,
            'to': [to_email],
            'reply_to': 'contact@onoff.markets',
            'subject': subject,
            'html': html,
            # One-click unsubscribe from the mail client itself (RFC 8058).
            'headers': {'List-Unsubscribe': f'<{unsub_url}>',
                        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'},
        })
    if response.status_code == 200:
        print(f"  Email sent to {mask(to_email)}")
        return True
    print(f"  ERROR sending email: {response.status_code} {response.text}")
    return False


def main():
    test_to = (os.environ.get('ALERT_TEST_TO') or '').strip()
    print("Checking for sharp moves and new extremes..." + (f" [TEST MODE -> {mask(test_to)}]" if test_to else ''))

    if not RESEND_API_KEY:
        print("  RESEND_API_KEY not set, skipping alerts")
        return

    current = load_current_scores()
    previous_labels = load_previous_labels()
    previous_scores = load_previous_scores()

    if not previous_labels:
        print("  No previous labels found (first run). Saving current state.")
        if not test_to:
            save_current_state(current)
        return

    changes = find_changes(current, previous_labels, previous_scores)
    for c in changes:
        c['prev_score'] = previous_scores.get(c['key'])
        print(f"  CHANGE: {c['name']} {c['old_label']} -> {c['new_label']} (score: {c['score']})")

    series = load_series()
    today = max(series['gold']) if series.get('gold') else datetime.utcnow().strftime('%Y-%m-%d')
    records = find_records(series, today, ignore_quiet=bool(test_to))
    items = build_items(changes, records)

    if not items:
        print("  Nothing to send today.")
    else:
        context = load_context(datetime.utcnow().strftime('%Y-%m-%d'))
        print(f"  AI context: {'included' if context else 'none'}")
        subscribers = fetch_subscribers()
        if test_to:
            match = next((s for s in subscribers if (s['email'] or '').lower() == test_to.lower()), None)
            subscribers = [{'id': match['id'] if match else 'test', 'email': test_to, 'preferences': []}]
        if not subscribers:
            print("  No subscribers found.")
        else:
            print(f"  Sending to {len(subscribers)} subscriber(s)...")
            sent = 0
            time.sleep(2)
            for sub in subscribers:
                sub_items = filter_items_for_subscriber(items, sub['preferences'])
                if not sub_items:
                    continue
                unsub = UNSUB_URL.format(sub['id'])
                subject = ('[TEST] ' if test_to else '') + build_email_subject(sub_items)
                if send_email(subject, build_email_html(sub_items, context, today, unsub), sub['email'], unsub):
                    sent += 1
                time.sleep(2)   # Resend allows 2 requests a second
            print(f"  Done: {sent} email(s) sent.")

    if test_to:
        print("  Test mode: state not saved.")
        return
    save_current_state(current)


if __name__ == '__main__':
    main()
