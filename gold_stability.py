#!/usr/bin/env python3
"""How firm is today's gold reading?

Not a forecast of the market. The index is published every morning from the
previous close, so tomorrow's reading depends on one unknown — today's session.
Everything else is already fixed. Two known quantities are enough to say how
likely the headline zone is to change:

  * how far the score sits from the nearest zone boundary
  * how much the index typically moves on that day of the week

Sunday barely moves (no new close has landed), Thursday moves the most. That
spread is the strongest signal available, far stronger than any regression on
past scores, which beat "tomorrow equals today" by less than 3%.

Calibration is checked against the published record: see --check.
"""
import json, math, statistics, datetime, sys
from collections import defaultdict

PUBLISHED = 'data/gold-fear-greed.json'      # the released record: what the site actually showed
BOUNDARIES = [25.5, 45.5, 55.5, 75.5]
ZONE_NAMES = ['Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed']
DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def zone_index(score):
    s = round(score)
    return 0 if s <= 25 else 1 if s <= 45 else 2 if s <= 55 else 3 if s <= 75 else 4


def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def load_history():
    """Only the published series is usable here.

    The 5Y file's older section was recomputed after the fact, and its weekends
    behave differently from the live runs — recomputing a 2023 Saturday today
    sees the same close as the Friday, so it looks frozen when the real Saturday
    was not. Using it would understate weekend movement.
    """
    h = json.load(open(PUBLISHED))['history']
    return sorted(h, key=lambda e: e['date'])


def daily_moves_by_weekday(history):
    """Every observed move of the index, kept per day of the week.

    The moves are used as-is rather than fitted to a bell curve: the real
    distribution is far more peaked at zero than a normal, and assuming one
    overstated the odds of a boundary crossing by roughly a seventh.
    """
    moves = defaultdict(list)
    for prev, cur in zip(history, history[1:]):
        d = datetime.date.fromisoformat(cur['date'])
        if (d - datetime.date.fromisoformat(prev['date'])).days != 1:
            continue
        moves[d.weekday()].append(cur['score'] - prev['score'])
    return {w: sorted(v) for w, v in moves.items()}


def gold_sensitivity(history):
    """Index points per 1% move in gold, measured on transitions where a new
    close actually entered (the stored price changed)."""
    xs, ys = [], []
    for prev, cur in zip(history, history[1:]):
        a, b = prev.get('price'), cur.get('price')
        if a is None or b is None or abs(b - a) < 1e-9:
            continue
        xs.append((b / a - 1) * 100)
        ys.append(cur['score'] - prev['score'])
    mx, my = statistics.mean(xs), statistics.mean(ys)
    cov = sum((p - mx) * (q - my) for p, q in zip(xs, ys)) / len(xs)
    return cov / statistics.pvariance(xs), len(xs)


def assess(score, next_day, moves_by_day, sensitivity):
    """Probability that the next published reading lands in a different zone,
    read straight off the historical moves for that day of the week."""
    obs = moves_by_day.get(next_day.weekday()) or [m for v in moves_by_day.values() for m in v]
    n = len(obs)
    z = zone_index(score)
    lower = BOUNDARIES[z - 1] if z > 0 else None
    upper = BOUNDARIES[z] if z < 4 else None

    p_down = (sum(1 for m in obs if score + m < lower) / n) if lower is not None else 0.0
    p_up = (sum(1 for m in obs if score + m > upper) / n) if upper is not None else 0.0
    sigma = statistics.pstdev(obs)

    out = {
        'score': score,
        'zone': ZONE_NAMES[z],
        'next_publication': next_day.isoformat(),
        'weekday': DAY_NAMES[next_day.weekday()],
        'typical_move': round(sigma, 2),
        'sample_size': n,
        'p_change': round(min(1.0, p_down + p_up) * 100, 1),
        'p_down': round(p_down * 100, 1),
        'p_up': round(p_up * 100, 1),
        'down_zone': ZONE_NAMES[z - 1] if lower is not None else None,
        'up_zone': ZONE_NAMES[z + 1] if upper is not None else None,
        'gold_move_down': round((lower - score) / sensitivity, 2) if lower is not None else None,
        'gold_move_up': round((upper - score) / sensitivity, 2) if upper is not None else None,
    }
    dominant = 'down' if p_down >= p_up else 'up'
    out['dominant'] = dominant
    out['dominant_share'] = round(max(p_down, p_up) / (p_down + p_up) * 100) if (p_down + p_up) > 0 else 0
    return out


def check_calibration(history, moves_by_day):
    """Replay every day: what was announced against what happened."""
    buckets = defaultdict(list)
    for prev, cur in zip(history, history[1:]):
        d = datetime.date.fromisoformat(cur['date'])
        a = assess(prev['score'], d, moves_by_day, 1.0)
        changed = zone_index(cur['score']) != zone_index(prev['score'])
        buckets[min(4, int(a['p_change'] / 20))].append((a['p_change'], changed))
    print('\n  Calibration against the published record')
    print(f"  {'announced':>12} {'observed':>10} {'days':>7}")
    for b in sorted(buckets):
        v = buckets[b]
        print(f"  {statistics.mean(p for p, _ in v):>11.0f}% {sum(1 for _, c in v if c)/len(v)*100:>9.0f}% {len(v):>7}")
    allv = [x for v in buckets.values() for x in v]
    print(f"  overall: announced {statistics.mean(p for p, _ in allv):.1f}%  "
          f"observed {sum(1 for _, c in allv if c)/len(allv)*100:.1f}%  ({len(allv)} days)")


if __name__ == '__main__':
    hist = load_history()
    moves = daily_moves_by_weekday(hist)
    sens, n_sens = gold_sensitivity(hist)
    latest = hist[-1]
    nxt = datetime.date.fromisoformat(latest['date']) + datetime.timedelta(days=1)
    a = assess(latest['score'], nxt, moves, sens)

    print(f"  Latest published: {latest['date']}  score {a['score']}  ({a['zone']})")
    print(f"  Next publication: {a['next_publication']} ({a['weekday']})")
    print(f"  Typical move on a {a['weekday']}: {a['typical_move']} pts")
    print(f"  Gold sensitivity: {sens:.2f} index pts per 1% GLD  (n={n_sens})\n")
    print(f"  CHANCE OF A ZONE CHANGE: {a['p_change']}%")
    if a['down_zone']:
        print(f"    into {a['down_zone']:14} {a['p_down']:>5}%   needs {a['gold_move_down']:+.2f}% on gold")
    if a['up_zone']:
        print(f"    into {a['up_zone']:14} {a['p_up']:>5}%   needs {a['gold_move_up']:+.2f}% on gold")
    print(f"\n  Days of history used: {len(hist)}")
    for w in range(7):
        v = moves.get(w, [])
        print(f"    {DAY_NAMES[w]:10} typical move {statistics.pstdev(v):>5.2f} pts  "
              f"| median {statistics.median(abs(x) for x in v):>4.2f}  (n={len(v)})")

    if '--check' in sys.argv:
        check_calibration(hist, moves)
