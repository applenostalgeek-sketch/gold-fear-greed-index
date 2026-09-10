#!/usr/bin/env python3
"""One-off announcement: Neutral no longer triggers an email alert.

Written for the 2026-09-10 rule change in send_alerts.py (SILENT_ZONES).
It is not part of the daily workflow — it is run by hand, once, from the
"Announce alert rule change" workflow.

Audience: everyone who could have received the Bonds -> Neutral alert that
went out on the morning of 2026-09-10. That means subscribers with 'bonds'
among their preferences AND subscribers with no preferences at all, since an
empty preference list means "send me everything" (see
filter_changes_for_subscriber in send_alerts.py). Leaving the second group
out would be the worst outcome: they got the alert and not the explanation.

Dry run unless --send is passed. A dry run makes no write call to Resend:
it lists the recipients and stops.

Run:  python announce_alert_change.py            # list recipients, send nothing
      python announce_alert_change.py --send     # actually send
Env:  RESEND_API_KEY, RESEND_AUDIENCE_ID
"""

import sys
import time

from send_alerts import RESEND_API_KEY, fetch_subscribers, send_email

SUBJECT = "Why Bonds alerted this morning — and why it won't again"

BODY_BLOCKS = [
    ("You received an alert this morning: the Bonds index had slipped back to "
     "Neutral. It fired exactly as designed. The design was wrong."),

    ("<b>Neutral isn't a market mood.</b> Fear, Greed and their extremes each "
     "tell you something. Neutral tells you there's nothing in particular to "
     "report — and an alert that says “nothing is happening” isn't "
     "worth your inbox."),

    ("It also fires far more often than it should. Neutral is the narrowest "
     "band on the scale: 46 to 55, ten points wide, against twenty each for "
     "Fear and Greed. Anything drifting through the middle keeps crossing its "
     "edges. Bonds is the clearest case — it sits in Neutral 39% of the time "
     "and crosses in or out 53 times a year."),

    ("So I replayed five years of history through the alert rule before "
     "changing anything. Neutral turned out to be the destination of 73 of 181 "
     "alerts — 40% of everything the system would ever have sent — and the "
     "least reliable of them: five days on, the index was still there only 43% "
     "of the time, against 68% for both Fear and Greed."),

    ("<b>As of today, alerts about an index turning Neutral are switched "
     "off.</b> Nothing else changed. You'll still hear from me when Bonds "
     "enters Fear, Greed or either extreme — including when it passes through "
     "Neutral on the way there. For Bonds that's roughly 5 alerts a year "
     "instead of 10; across all four indices, 22 instead of 36."),

    ("One consequence worth knowing: you may now go weeks without an email. "
     "That's the intended behaviour, not a fault."),

    ("OnOff.Markets is young and gets adjusted in the open. When a change "
     "affects what lands in your inbox, I'll tell you."),
]


def build_html():
    """Same shell as the alert emails, with 'Service note' in place of
    'Sentiment Alert' so it does not read as a zone change."""
    body = "\n".join(
        f'    <p style="font-size: 15px; line-height: 1.65; color: #333; '
        f'margin: 0 0 18px 0;">{b}</p>'
        for b in BODY_BLOCKS
    )
    return f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 20px;">
  <div style="text-align: center; margin-bottom: 8px;">
    <span style="font-size: 17px; font-weight: 700; color: #111;">On<span style="color: #999;">●●</span>Off<span style="color: #666; font-weight: 400;">.Markets</span></span>
  </div>
  <div style="text-align: center; margin-bottom: 32px;">
    <span style="font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 0.15em;">Service note</span>
  </div>

{body}

  <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid #eee; text-align: center;">
    <a href="https://onoff.markets" style="color: #888; text-decoration: none; font-size: 12px;">onoff.markets</a>
    <span style="color: #ccc; font-size: 12px;"> &nbsp;|&nbsp; </span>
    <span style="font-size: 12px; color: #aaa;">Real-time market sentiment</span>
    <br><br>
    <span style="font-size: 11px; color: #bbb;">To unsubscribe, visit <a href="https://onoff.markets" style="color: #999;">onoff.markets</a> and click Alerts.</span>
  </div>
</div>"""


def concerned(sub):
    """Did this subscriber get the Bonds alert? Empty preferences = everything."""
    prefs = sub.get('preferences') or []
    return (not prefs) or ('bonds' in prefs)


def main():
    send = '--send' in sys.argv

    if not RESEND_API_KEY:
        print("RESEND_API_KEY not set — cannot reach the audience.")
        sys.exit(1)

    subscribers = fetch_subscribers()
    if not subscribers:
        print("No subscribers returned. Nothing to do.")
        return

    targets = [s for s in subscribers if concerned(s)]
    skipped = [s for s in subscribers if not concerned(s)]

    print(f"Audience: {len(subscribers)} active subscriber(s)")
    print(f"  concerned by the Bonds alert: {len(targets)}")
    print(f"  not concerned (no bonds in their preferences): {len(skipped)}")
    print()
    for s in targets:
        prefs = ', '.join(s['preferences']) if s['preferences'] else 'all assets'
        print(f"  -> {s['email']}  [{prefs}]")

    if not send:
        print()
        print(f"DRY RUN — nothing sent. {len(targets)} email(s) would go out.")
        print("Re-run with --send (or tick 'confirm' in the workflow) to send.")
        return

    print()
    print(f"Sending to {len(targets)} subscriber(s)...")
    sent = 0
    for s in targets:
        if send_email(SUBJECT, build_html(), s['email']):
            sent += 1
        time.sleep(2)          # Resend allows max 2 req/s
    print(f"Done: {sent} email(s) sent, {len(targets) - sent} failed.")


if __name__ == '__main__':
    main()
