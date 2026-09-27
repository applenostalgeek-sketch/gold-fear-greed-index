#!/usr/bin/env python3
"""Incidents the daily job noticed, gathered into one mail to the owner.

The index scripts call record() when something needed a fallback — a price
taken from the second provider, a price held from yesterday, two providers
disagreeing. The workflow then runs this file once, which sends a single mail
listing everything and clears the log. No incident, no mail.

It never fails the run. Without RESEND_API_KEY or WATCHDOG_EMAIL the incidents
still reach the job log (as GitHub warnings), just not the inbox.

Run directly to send what has been recorded:
    python incidents.py
"""

import html
import json
import os
import tempfile
from datetime import datetime, timezone

# RUNNER_TEMP lives for exactly one job, so incidents from the four index
# steps reach the report step and never leak into the next day's run.
LOG = os.path.join(os.environ.get('RUNNER_TEMP') or tempfile.gettempdir(),
                   'onoff-incidents.jsonl')

FROM_EMAIL = 'OnOff.Markets <newsletter@onoff.markets>'


def record(asset, message, detail=''):
    """Note one incident. Never raises: reporting must not break publishing."""
    print(f"::warning::{asset}: {message}")
    try:
        with open(LOG, 'a') as f:
            f.write(json.dumps({'asset': asset, 'message': message, 'detail': detail,
                                'at': datetime.now(timezone.utc).strftime('%H:%M UTC')}) + '\n')
    except Exception as e:
        print(f"  (incident not saved for the mail: {e})")


def _read():
    try:
        with open(LOG) as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def _send(subject, rows):
    key = os.environ.get('RESEND_API_KEY')
    to = os.environ.get('WATCHDOG_EMAIL')
    if not key or not to:
        print("  No mail sent: RESEND_API_KEY or WATCHDOG_EMAIL is missing.")
        return False
    import requests
    body = ''.join(
        f'<p style="line-height:1.6;font-size:0.95rem;color:#333;">'
        f'<strong>{html.escape(r["asset"])}</strong> — {html.escape(r["message"])}'
        + (f'<br><span style="font-size:0.8rem;color:#999;">{html.escape(r["detail"])} · {r["at"]}</span>'
           if r.get('detail') else '')
        + '</p>'
        for r in rows)
    try:
        res = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={
                'from': FROM_EMAIL,
                'to': [to],
                'subject': subject,
                'html': (f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
                         f'max-width:520px;margin:0 auto;padding:32px;">{body}'
                         f'<p style="margin-top:24px;font-size:0.8rem;color:#999;">'
                         f'Envoyé par le robot quotidien (incidents.py). Le site a été publié normalement.</p></div>'),
            },
            timeout=20,
        )
        if res.status_code == 200:
            print(f"  Incident mail sent ({len(rows)} line(s)).")
            return True
        print(f"  Incident mail failed: Resend HTTP {res.status_code} {res.text[:200]}")
    except Exception as e:
        print(f"  Incident mail failed: {e}")
    return False


def main():
    rows = _read()
    if not rows:
        print("No incident today.")
        return
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    n = len(rows)
    subject = f"OnOff.Markets — {n} incident{'s' if n > 1 else ''} sur les données du {day}"
    print(subject)
    for r in rows:
        print(f"  {r['asset']}: {r['message']}" + (f" [{r['detail']}]" if r.get('detail') else ''))
    _send(subject, rows)
    # The job log keeps the list either way; a leftover file would only
    # resurface in a later local run.
    try:
        os.remove(LOG)
    except OSError:
        pass


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Incident report crashed, run unaffected: {e}")
