#!/usr/bin/env python3
"""Pairwise co-movement between the four indices, for the "Moving With The Market" block.

Writes data/correlations-<asset>.json, one per asset page. Everything in those
files is recomputed from scratch on every run — the twelve months of frames, the
current reading, and the five-year normal — so nothing on the page is ever a
figure frozen at build time.

Reads the local history-5y-*.json only. No network call, no API key: if those
files are there, this cannot fail for an outside reason.

Run: python correlation.py
"""

import json
import math
import os
import sys
from datetime import date

ASSETS = ['gold', 'stocks', 'bonds', 'crypto']
WINDOW = 90          # trading days — about a quarter
YEAR = 253           # trading days of history drawn on the page
STEP = 2             # one frame every other day: 127 frames is plenty at this width

# Deux conventions de dates cohabitent dans history-5y-*.json. La reconstruction
# (<= fev 2026) date chaque entree du JOUR REEL de cloture. Les ajouts quotidiens
# (>= mars 2026) tournent vers 07:00 UTC et publient la cloture de la VEILLE :
# l'entree datee D y porte la seance D-1. Verifie empiriquement en correlant les
# obligations aux variations du taux 10 ans, dont on connait la reponse (~ -0.9) :
# -0.91 sans decalage sur la partie ancienne, -0.89 avec un decalage d'un jour sur
# la partie recente. Sans cette correction, la date affichee sous l'animation
# annonce une seance qui n'a pas encore eu lieu.
APPEND_ERA = '2026-03-01'


def load_prices():
    out = {}
    for a in ASSETS:
        with open(f'data/history-5y-{a}.json') as f:
            out[a] = {r['date']: r['price']
                      for r in json.load(f)['history'] if r.get('price')}
    return out


def trading_days(P):
    """Days the traditional markets actually traded.

    Crypto quotes 7/7 while gold, stocks and bonds carry Friday's price through
    the weekend. On a calendar-day axis their returns would be mechanical zeros
    against a moving crypto, which drags every correlation towards nothing.
    Holidays are caught the same way: gold and stocks both unchanged means the
    session never happened.
    """
    days = sorted(set.intersection(*[set(P[a]) for a in ASSETS]))
    out, prev = [], None
    for d in days:
        if date.fromisoformat(d).weekday() >= 5:
            continue
        if prev and P['gold'][d] == P['gold'][prev] and P['stocks'][d] == P['stocks'][prev]:
            continue
        out.append(d)
        prev = d
    return out


def log_returns(series, days):
    return [math.log(series[c] / series[p]) for p, c in zip(days, days[1:])]


def corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((v - mx) ** 2 for v in x))
    sy = math.sqrt(sum((v - my) ** 2 for v in y))
    if not sx or not sy:
        return 0.0
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def centre_gap(shared):
    """Distance between two equal circles whose intersection is `shared` of their area.

    This is what makes the drawing honest rather than illustrative: the overlap
    the reader sees IS r squared, solved for, not eyeballed.
    """
    lo, hi = 0.0, 2.0
    for _ in range(60):
        d = (lo + hi) / 2
        a = 0.0 if d >= 2 else 2 * math.acos(d / 2) - (d / 2) * math.sqrt(max(0, 4 - d * d))
        if a / math.pi > shared:
            lo = d
        else:
            hi = d
    return (lo + hi) / 2


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def usual_direction(series):
    """How to describe the normal state, in words that survive a change of regime.

    A single median sign would claim a habit the pair may not have: bonds and
    crypto sit on either side of zero almost equally often, and calling that
    "usually together" would be false a third of the time.
    """
    neg = sum(1 for r in series if r < 0) / len(series)
    if min(neg, 1 - neg) >= 1 / 3:
        return 'with no consistent direction', round(100 * neg)
    if median(series) >= 0:
        return 'also in the same direction', round(100 * neg)
    return 'usually in opposite directions', round(100 * neg)


def session_dates(days):
    """Pour chaque entree, la date de la seance qu'elle contient reellement.

    Ere recente : l'entree D porte la cloture de D-1, et si D-1 tombe un week-end
    elle porte celle du dernier jour ouvre avant. Prendre "l'entree precedente de
    la liste" serait faux : autour d'un ferie, l'entree du lendemain du ferie est
    ecartee, si bien que l'entree suivante se retrouverait etiquetee deux jours
    trop tot. On remonte donc au dernier jour ouvre du calendrier.
    """
    from datetime import timedelta
    out = {}
    for d in days:
        if d < APPEND_ERA:
            out[d] = d
            continue
        x = date.fromisoformat(d) - timedelta(days=1)
        while x.weekday() >= 5:
            x -= timedelta(days=1)
        out[d] = x.isoformat()
    return out


def pair_series(R, a, b, days):
    """Rolling correlation of a against b, one value per trading day."""
    return [corr(R[a][i - WINDOW:i], R[b][i - WINDOW:i])
            for i in range(WINDOW, len(R[a]) + 1)]


def main():
    print("Computing co-movement between the four indices...")
    P = load_prices()
    days = trading_days(P)
    dates = days[1:]
    if len(dates) < WINDOW + 2:
        raise RuntimeError(f"only {len(dates)} trading days available, need more than {WINDOW}")
    R = {a: log_returns(P[a], days) for a in ASSETS}
    sess = session_dates(days)
    print(f"  {len(dates)} trading days, sessions {sess[dates[0]]} to {sess[dates[-1]]}")

    # Tout calculer AVANT d'ecrire quoi que ce soit. En ecrivant au fil de la
    # boucle, un plantage sur le troisieme actif laisserait les deux premiers
    # fichiers a la date du jour et les deux autres a celle de la veille — un
    # melange incoherent, commite tel quel puisque l'etape est en
    # continue-on-error. Soit les quatre avancent, soit aucun.
    computed = {}
    for a in ASSETS:
        out = {}
        for b in [x for x in ASSETS if x != a]:
            S = pair_series(R, a, b, days)
            # on etiquette avec la SEANCE, pas avec la date d'entree du fichier
            stamps = [sess[dates[i - 1]] for i in range(WINDOW, len(dates) + 1)]

            # The normal is the median of what the page displays — the shared
            # share, r squared — not the square of the median correlation. The
            # two differ whenever the pair crosses zero, and squaring the median
            # understates the normal, which would make today look rarer than it is.
            ov_med = median([r * r for r in S])
            way, neg_share = usual_direction(S)

            ys, yd = S[-YEAR:][::STEP], stamps[-YEAR:][::STEP]
            if ys[-1] != S[-1]:                     # never drop the latest reading
                ys.append(S[-1])
                yd.append(stamps[-1])

            out[b] = {
                'frames': [{'d': d, 'r': round(r, 3), 'ov': round(100 * r * r, 1),
                            'gap': round(centre_gap(r * r), 4),
                            'sign': 1 if r >= 0 else -1}
                           for r, d in zip(ys, yd)],
                'ov_med': round(100 * ov_med, 1),
                'usual_way': way,
                'neg_share': neg_share,
            }
            print(f"  {a:7s} vs {b:7s}  {out[b]['frames'][-1]['ov']:5.1f}% shared"
                  f"  (usually {out[b]['ov_med']:4.1f}%, {way})")

        computed[a] = {'asset': a, 'window': WINDOW, 'updated': sess[dates[-1]], 'pairs': out}

    for a, payload in computed.items():
        path = f'data/correlations-{a}.json'
        tmp = path + '.tmp'
        # Ecriture atomique : json.dump directement dans la cible laisserait un
        # fichier tronque si l'ecriture echouait en cours, et ce JSON invalide
        # partirait au commit. allow_nan=False parce que json.dump ecrit NaN
        # sans broncher alors que JSON.parse le refuse : mieux vaut une exception
        # ici, rattrapee plus bas, qu'un fichier illisible en production.
        with open(tmp, 'w') as f:
            json.dump(payload, f, separators=(',', ':'), allow_nan=False)
        os.replace(tmp, path)
        print(f"  -> {path}")

    print("Done.")


if __name__ == '__main__':
    # Cette etape tourne AVANT le commit du workflow. Une exception ici ferait
    # echouer le job, donc aucun des quatre indices ne serait publie ce jour-la,
    # puis le veilleur relancerait et l'utilisateur recevrait un mail — tout ca
    # pour un bloc secondaire. L'etape porte `continue-on-error: true`, et on
    # sort en erreur pour que l'echec reste VISIBLE dans le journal plutot que
    # d'etre avale en silence. Les fichiers de la veille restent en place.
    try:
        main()
    except Exception as e:
        print(f"  WARNING: correlation.py failed ({type(e).__name__}: {e})")
        print("  Keeping yesterday's correlation files. The four indices are unaffected.")
        sys.exit(1)
