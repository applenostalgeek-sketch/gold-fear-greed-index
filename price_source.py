#!/usr/bin/env python3
"""Second provider for the price each index publishes.

The four scripts publish one price a day — the figure under the gauge, the
Historical Trend chart, and the series `correlation.py` reads. Until now that
price had a single source: Yahoo. If Yahoo returned nothing, the entry was
written without a price at all.

This module gives it a cascade:

    1. Yahoo        (yfinance, as before)
    2. Alpha Vantage (same ticker, different provider)
    3. yesterday's published price, frozen

Measured on 2026-09-18 over the last 60 sessions, the two providers agree on
the traded price to the cent for GLD, SPY and TLT, and to 0.072% at worst for
BTC. So the substitution needs no conversion and no rescaling: it is the same
instrument quoted by someone else.

Two measured traps, both of which made the providers look like they disagreed:

  - TLT pays a monthly distribution. Yahoo back-adjusts its whole history at
    every ex-dividend date; Alpha Vantage returns the raw close. Compared raw
    to raw the two match exactly (60/60). Today's close is never adjusted —
    the adjustment only rewrites the past — so a same-day substitution is
    safe, but any comparison of PAST prices between the two is meaningless.
  - BTC quotes around the clock, so the running day is a snapshot taken at
    whatever moment each provider looked. That day alone differed by 1.7%,
    against 0.072% for every settled day. The robot runs at ~07:00 UTC and
    publishes the previous session, so it never reads a running day — but a
    cross-check must still skip it.

Run directly to see what both providers say right now:
    python price_source.py
"""

import json
import math
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

AV_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
AV_URL = 'https://www.alphavantage.co/query?'

# Alpha Vantage splits equities and crypto across two different functions, and
# names the crypto symbol without its quote currency.
ASSETS = {
    'gold':   {'ticker': 'GLD',     'av_fn': 'TIME_SERIES_DAILY',     'av_sym': 'GLD'},
    'stocks': {'ticker': 'SPY',     'av_fn': 'TIME_SERIES_DAILY',     'av_sym': 'SPY'},
    'bonds':  {'ticker': 'TLT',     'av_fn': 'TIME_SERIES_DAILY',     'av_sym': 'TLT'},
    'crypto': {'ticker': 'BTC-USD', 'av_fn': 'DIGITAL_CURRENCY_DAILY', 'av_sym': 'BTC'},
}

# Above this gap between the two providers on the same settled session, one of
# them is wrong. Over 60 sessions the widest observed gap was 0.072% (BTC);
# equities and gold matched to the cent. 0.5% is seven times the worst
# observation — wide enough never to have fired on the measured history, narrow
# enough to catch a corrupted quote. Revisit once real daily pairs accumulate.
CROSSCHECK_PCT = 0.5

# Measured from a Mac, Alpha Vantage answered in 0.13-0.46 s on 2026-09-27 and
# 0.3-3.6 s on 2026-09-29. But from GitHub on 2026-09-29, all four calls hit a
# 10 s limit, and a cut-off call cannot say whether the answer was 2 s or two
# minutes away. The same afternoon, from the Mac, eight calls took 3.0-25.8 s.
# 45 s clears the slowest one seen, and lets the log record how long Alpha
# Vantage really takes from the runner. It costs at most three minutes on a
# day it hangs, which nothing waits on: the tweet simply follows later.
TIMEOUT = 45

# Why the last Alpha Vantage call for each asset gave what it gave, and how
# long it took — for the log line only, never for a decision.
_av_diag = {}


def _av_series(asset):
    """{'YYYY-MM-DD': close} from Alpha Vantage, or None if it cannot be had.

    Never raises: a missing key, a rate limit, a network failure and a renamed
    field all mean the same thing to the caller — no second opinion today.
    Which of them it was goes to _av_diag, so the log can tell them apart.
    """
    if not AV_KEY:
        return None
    cfg = ASSETS[asset]
    if cfg['av_fn'] == 'DIGITAL_CURRENCY_DAILY':
        url = f"{AV_URL}function={cfg['av_fn']}&symbol={cfg['av_sym']}&market=USD&apikey={AV_KEY}"
    else:
        url = f"{AV_URL}function={cfg['av_fn']}&symbol={cfg['av_sym']}&apikey={AV_KEY}"
    start = time.monotonic()

    def fail(reason):
        # The reason never includes the URL: it carries the API key.
        _av_diag[asset] = (reason, time.monotonic() - start)
        return None

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'onoff.markets'})
        body = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode()
    except urllib.error.HTTPError as e:
        return fail(f'HTTP {e.code}')
    except (socket.timeout, TimeoutError):
        return fail('timeout')
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            return fail('timeout')
        return fail(f'network error: {type(e.reason).__name__}')
    except Exception as e:
        return fail(f'error: {type(e).__name__}')
    try:
        payload = json.loads(body)
    except ValueError:
        return fail('unreadable reply')
    # The free tier answers a rate limit with HTTP 200 and an "Information"
    # note instead of the series, so a missing key matters more than a status.
    keys = [k for k in payload if 'Time Series' in k or 'Digital Currency' in k]
    if not keys:
        if 'Information' in payload or 'Note' in payload:
            return fail('rate limit or plan notice')
        if 'Error Message' in payload:
            return fail('rejected: ' + str(payload['Error Message'])[:60])
        return fail('no series in reply')
    out = {}
    for day, fields in payload[keys[0]].items():
        close = [v for k, v in fields.items() if 'close' in k.lower()]
        if close:
            try:
                out[day] = float(close[0])
            except (TypeError, ValueError):
                pass
    if not out:
        return fail('empty series')
    _av_diag[asset] = ('ok', time.monotonic() - start)
    return out


def _yahoo_series(asset):
    """{'YYYY-MM-DD': close} from Yahoo, or None. Never raises.

    Yahoo's chart API sometimes returns the last close as NaN. The scripts'
    clean_hist() recovers it from the quote API (it did on ~2 days in 91), so
    this does the same before anything else: without it, a NaN on a day Alpha
    Vantage is also down would publish yesterday's price where the old code
    had today's.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(ASSETS[asset]['ticker'])
        hist = ticker.history(period='1mo')
        if hist.empty or 'Close' not in hist.columns:
            return None
        if math.isnan(float(hist['Close'].iloc[-1])):
            try:
                quote = ticker.info.get('regularMarketPrice')
                if quote is not None:
                    hist.loc[hist.index[-1], 'Close'] = float(quote)
            except Exception:
                pass
        out = {}
        for stamp, value in hist['Close'].items():
            v = float(value)
            if not math.isnan(v):
                out[stamp.strftime('%Y-%m-%d')] = v
        return out or None
    except Exception:
        return None


def _frozen_price(asset):
    """Yesterday's published price, read back from what the site already serves."""
    try:
        with open(f'data/{asset}-fear-greed.json') as f:
            for entry in json.load(f)['history']:
                if entry.get('price'):
                    return float(entry['price']), entry['date']
    except Exception:
        pass
    return None, None


def _running_day(asset):
    """The session a provider may still be in the middle of.

    Only crypto has one: it quotes 7/7, so today's row is a snapshot rather
    than a close. Equities and gold only ever publish settled sessions.
    """
    if asset != 'crypto':
        return None
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def published_price(asset):
    """Today's price to publish, and where it came from.

    Returns a dict:
        price     float or None
        source    'yahoo' | 'alphavantage' | 'frozen' | None
        session   the date the price belongs to, or None
        status    'ok' | 'fallback' | 'frozen' | 'unavailable'
        note      one line for the log and for the alert mail, or ''
    """
    if asset not in ASSETS:
        raise ValueError(f'unknown asset {asset!r}')

    y = _yahoo_series(asset)
    av = _av_series(asset)
    skip = _running_day(asset)

    y_last = max(y) if y else None
    av_last = max(av) if av else None

    # What the second provider said, for the log only. Without it, a day where
    # Alpha Vantage silently stopped answering reads exactly like a day where
    # it agreed: in both cases there is no note.
    reason, took = _av_diag.get(asset, ('', None))
    took = f' ({took:.1f} s)' if took is not None else ''
    if not AV_KEY:
        alpha = 'Alpha Vantage: no key'
    elif not av:
        alpha = f"Alpha Vantage: no answer{' — ' + reason if reason else ''}{took}"
    else:
        alpha = f'Alpha Vantage: answered up to {av_last}{took}'

    # Yahoo answered, and is not behind the second provider.
    if y_last and (av_last is None or y_last >= av_last):
        note = ''
        # Cross-check, on a settled session both providers carry. Yahoo's own
        # value is kept either way: a disagreement says one of them is wrong,
        # not which, and silently preferring the newcomer would be worse.
        if av:
            common = sorted(set(y) & set(av) - ({skip} if skip else set()))
            if common:
                d = common[-1]
                gap = 100 * abs(y[d] - av[d]) / av[d] if av[d] else 0.0
                alpha = f'Alpha Vantage: {av[d]:.2f} on {d}, {gap:.2f}% apart{took}'
                if gap > CROSSCHECK_PCT:
                    note = (f'providers disagree on {d}: Yahoo {y[d]:.2f} vs '
                            f'Alpha Vantage {av[d]:.2f} ({gap:.2f}%)')
        return {'price': round(y[y_last], 2), 'source': 'yahoo', 'session': y_last,
                'status': 'ok', 'note': note, 'alpha': alpha}

    # Yahoo is missing or stale while the second provider has moved on.
    if av_last:
        why = 'Yahoo returned nothing' if not y_last else f'Yahoo stopped at {y_last}'
        return {'price': round(av[av_last], 2), 'source': 'alphavantage',
                'session': av_last, 'status': 'fallback',
                'note': f'{why}, used Alpha Vantage ({av_last})', 'alpha': alpha}

    # Neither answered.
    price, when = _frozen_price(asset)
    if price is not None:
        return {'price': price, 'source': 'frozen', 'session': when, 'status': 'frozen',
                'note': f'both providers failed, held the price of {when}', 'alpha': alpha}

    return {'price': None, 'source': None, 'session': None, 'status': 'unavailable',
            'note': 'both providers failed and no previous price was on file', 'alpha': alpha}


NAMES_FR = {'gold': 'Or', 'stocks': 'Actions', 'bonds': 'Obligations', 'crypto': 'Crypto'}


def price_for_today(asset, yahoo_only):
    """The price a script publishes today, with incidents sent to the owner.

    `yahoo_only` is the script's own Yahoo-only fetch — the code that ran
    before this module existed. When the cascade ends on a held or missing
    price, that fetch gets one more try: a second call can succeed where the
    first failed, and the old code would have had that chance. So this can
    never publish less than the old code did.
    """
    r = published_price(asset)
    name = NAMES_FR.get(asset, asset)

    if r['status'] in ('frozen', 'unavailable'):
        retry = yahoo_only()
        if retry is not None:
            print(f"  💲 {asset}: {retry} from Yahoo on the second try — {r.get('alpha', '')}")
            return retry

    # The mail is a courtesy: whatever goes wrong while reporting, the price
    # found above is still the one published.
    try:
        import incidents
        if r['status'] == 'fallback':
            incidents.record(name, f"Yahoo défaillant, prix pris chez Alpha Vantage : "
                                   f"{r['price']} (séance du {r['session']}).", r['note'])
        elif r['status'] == 'frozen':
            incidents.record(name, f"Yahoo ET Alpha Vantage en panne, prix de la veille gardé : "
                                   f"{r['price']} (du {r['session']}).", r['note'])
        elif r['status'] == 'unavailable':
            incidents.record(name, "Aucune source et aucun prix précédent : journée publiée SANS prix.",
                             r['note'])
        elif r['note']:
            incidents.record(name, f"Yahoo et Alpha Vantage ne donnent pas le même prix. "
                                   f"Celui de Yahoo est publié ({r['price']}) — à vérifier.", r['note'])
    except Exception as e:
        print(f"  (incident not reported: {e})")

    print(f"  💲 {asset}: {r['price']} from {r['source']} ({r['session']}) — {r.get('alpha', '')}")
    return r['price']


if __name__ == '__main__':
    print(f"Alpha Vantage key: {'present' if AV_KEY else 'ABSENT — second source disabled'}\n")
    for name in ASSETS:
        r = published_price(name)
        flag = {'ok': 'OK  ', 'fallback': 'FALL', 'frozen': 'FROZ', 'unavailable': 'FAIL'}[r['status']]
        print(f"  [{flag}] {name:7s} {str(r['price']):>12}  {r['source'] or '-':13s} {r['session'] or '-'}  {r['alpha']}")
        if r['note']:
            print(f"         -> {r['note']}")
