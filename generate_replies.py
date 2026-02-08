#!/usr/bin/env python3
"""
Daily briefing: key numbers + talking points for X engagement.
Run each morning: python3 generate_replies.py
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def load_data():
    markets = {}
    for name in ['gold', 'bonds', 'stocks', 'crypto']:
        path = os.path.join(DATA_DIR, f'{name}-fear-greed.json')
        with open(path) as f:
            markets[name] = json.load(f)
    return markets

def get_facts(data):
    """Get all interesting facts, not just one."""
    facts = []
    history = data.get('history', [])
    score = data['score']

    if len(history) >= 30:
        scores30 = [h['score'] for h in history[:30]]
        if score >= max(scores30) - 1:
            facts.append('Highest in 30 days')
        if score <= min(scores30) + 1:
            facts.append('Lowest in 30 days')

    if len(history) >= 7:
        diff = round(score - history[6]['score'])
        if abs(diff) > 3:
            facts.append(f"{'Up' if diff > 0 else 'Down'} {abs(diff)} pts this week")

    if len(history) >= 3:
        d = 1 if history[0]['score'] > history[1]['score'] else -1
        streak = 1
        for i in range(1, len(history) - 1):
            if d > 0 and history[i]['score'] > history[i+1]['score']:
                streak += 1
            elif d < 0 and history[i]['score'] < history[i+1]['score']:
                streak += 1
            else:
                break
        if streak >= 4:
            facts.append(f"{'Rising' if d > 0 else 'Falling'} {streak} days straight")

    return facts

def get_components_summary(data):
    """Get readable component details."""
    components = data.get('components', {})
    lines = []
    for name, comp in components.items():
        detail = comp.get('detail', '')
        score = round(comp['score'])
        if detail:
            lines.append(f"  {name}: {score} — {detail}")
    return lines

def generate():
    m = load_data()

    markets = [
        ('GOLD', 'gold', m['gold'], 'onoff.markets/gold'),
        ('BONDS', 'bonds', m['bonds'], 'onoff.markets/bonds'),
        ('STOCKS', 'stocks', m['stocks'], 'onoff.markets/stocks'),
        ('CRYPTO', 'crypto', m['crypto'], 'onoff.markets/crypto'),
    ]

    # Find the story
    scores = [(name, round(d['score']), d['label']) for name, _, d, _ in markets]
    highest = max(scores, key=lambda x: x[1])
    lowest = min(scores, key=lambda x: x[1])
    gap = highest[1] - lowest[1]

    timestamp = m['crypto'].get('timestamp', 'unknown')

    print()
    print("=" * 55)
    print(f"  DAILY BRIEFING — {timestamp[:10]}")
    print("=" * 55)

    # Quick overview line
    summary = " | ".join(f"{name} {score}" for name, score, _ in scores)
    print(f"\n  {summary}")

    # Each market
    for display_name, key, data, link in markets:
        score = round(data['score'])
        label = data['label']
        facts = get_facts(data)
        components = get_components_summary(data)

        # Highlight extreme readings
        marker = ""
        if score <= 25 or score >= 75:
            marker = " <<<"

        print(f"\n{'─' * 55}")
        print(f"  {display_name}: {score} ({label}){marker}")
        if facts:
            print(f"  {' · '.join(facts)}")
        for line in components:
            print(line)
        print(f"  {link}")

    # Today's story
    print(f"\n{'━' * 55}")
    print(f"  TODAY'S STORY")
    print(f"{'━' * 55}")

    extremes = [s for s in scores if s[1] <= 25 or s[1] >= 75]
    if len(extremes) >= 2:
        names = ", ".join(f"{s[0]} at {s[1]}" for s in extremes)
        print(f"  Multiple extremes: {names}")
    elif extremes:
        e = extremes[0]
        print(f"  {e[0]} stands out at {e[1]} ({e[2]})")

    if gap >= 30:
        print(f"  {highest[0]} ({highest[1]}) vs {lowest[0]} ({lowest[1]}) = {gap} pts apart")
    elif gap < 15:
        print(f"  All 4 markets clustered within {gap} pts — no clear direction")

    # Search links
    print(f"\n{'─' * 55}")
    print(f"  FIND CONVERSATIONS:")
    print(f"  x.com/search?q=%22fear%20and%20greed%22&f=live")
    print(f"  x.com/search?q=%22gold%20sentiment%22&f=live")
    print(f"  x.com/search?q=%22crypto%20fear%22&f=live")
    print(f"  x.com/search?q=%22market%20sentiment%22&f=live")
    print(f"{'─' * 55}")
    print()

if __name__ == '__main__':
    generate()
