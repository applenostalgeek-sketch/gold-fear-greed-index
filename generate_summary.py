#!/usr/bin/env python3
"""Generate AI market summary using Claude Haiku with web search.

Called daily after the 4 index calculations. Produces a 2-3 sentence
summary explaining market catalysts. Falls back to a template if the
API is unavailable.
"""

import json
import os
from datetime import datetime, timezone


def get_label(score):
    if score >= 75: return "Extreme Greed"
    if score >= 55: return "Greed"
    if score >= 45: return "Neutral"
    if score >= 25: return "Fear"
    return "Extreme Fear"


def load_scores():
    """Load current scores and compute deltas from yesterday."""
    assets = {}
    for name, filename in [('Gold', 'gold-fear-greed.json'),
                           ('Stocks', 'stocks-fear-greed.json'),
                           ('Crypto', 'crypto-fear-greed.json'),
                           ('Bonds', 'bonds-fear-greed.json')]:
        with open(f'data/{filename}') as f:
            data = json.load(f)
        score = data['score']
        label = data['label']
        history = data.get('history', [])
        delta_1d = round(score - history[1]['score'], 1) if len(history) > 1 else 0
        delta_7d = round(score - history[6]['score'], 1) if len(history) > 6 else 0
        delta_14d = round(score - history[13]['score'], 1) if len(history) > 13 else 0
        assets[name] = {'score': score, 'label': label,
                        'delta': delta_1d, 'delta_7d': delta_7d, 'delta_14d': delta_14d}

    avg = round(sum(a['score'] for a in assets.values()) / 4, 1)
    assets['Sentiment'] = {'score': avg, 'label': get_label(avg)}
    return assets


def load_previous_summary():
    """Load yesterday's summary to avoid repetition."""
    path = 'data/market-summary.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return data.get('summary', '')
    return ''


def fallback_summary(scores):
    """Template-based fallback when API is unavailable."""
    asset_scores = {k: v for k, v in scores.items() if k != 'Sentiment'}
    highest = max(asset_scores, key=lambda k: asset_scores[k]['score'])
    lowest = min(asset_scores, key=lambda k: asset_scores[k]['score'])
    sentiment = scores['Sentiment']

    return (
        f"Markets show mixed signals with {highest} leading at "
        f"{asset_scores[highest]['score']} ({asset_scores[highest]['label']}) "
        f"while {lowest} lags at {asset_scores[lowest]['score']} "
        f"({asset_scores[lowest]['label']}). Overall sentiment sits at "
        f"{sentiment['score']}."
    )


def generate_summary():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  No ANTHROPIC_API_KEY set, using fallback")
        return fallback_summary(load_scores())

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"  Anthropic client error: {e}, using fallback")
        return fallback_summary(load_scores())

    scores = load_scores()
    previous = load_previous_summary()

    score_lines = []
    for name in ['Gold', 'Stocks', 'Crypto', 'Bonds']:
        s = scores[name]
        d1 = f"+{s['delta']}" if s['delta'] >= 0 else str(s['delta'])
        d7 = f"+{s['delta_7d']}" if s['delta_7d'] >= 0 else str(s['delta_7d'])
        d14 = f"+{s['delta_14d']}" if s['delta_14d'] >= 0 else str(s['delta_14d'])
        trend = "rising" if s['delta_7d'] > 3 else "falling" if s['delta_7d'] < -3 else "stable"
        score_lines.append(f"- {name}: {s['score']} ({s['label']}, {d1} 1d, {d7} 7d, {d14} 14d, trend: {trend})")

    sentiment = scores['Sentiment']
    score_lines.append(f"- Market Sentiment (average): {sentiment['score']} ({sentiment['label']})")
    scores_text = "\n".join(score_lines)

    system = """You write a daily 2-3 sentence market summary for onoff.markets (a Fear & Greed index site).

Rules:
- MAX 350 characters. 2-3 sentences.
- Mention all 4 markets: Gold, Stocks, Crypto, Bonds.
- Respect the trend direction provided (rising/falling/stable). Never contradict it.
- Describe current state only. No predictions, no "ahead", no "expect".
- Reference the Fear & Greed scores and labels, not asset prices.
- Use web search to find today's catalysts (macro, geopolitics, central banks).
- Be factual. No filler. Every word must add information.
- Plain text only. No emojis, no markdown.
- Vary phrasing from yesterday's summary.
- Output ONLY the summary. No preamble, no reasoning, no commentary."""

    user_msg = f"""Today's scores (0=Extreme Fear, 100=Extreme Greed):
{scores_text}

Yesterday's summary (vary from this): "{previous}"

Write the summary now."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=system,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }],
            messages=[{"role": "user", "content": user_msg}]
        )

        # Concatenate all text blocks (web search splits across multiple)
        text_blocks = [block.text.strip() for block in response.content
                       if block.type == "text" and block.text.strip()]
        if not text_blocks:
            print("  No text in response, using fallback")
            return fallback_summary(scores)

        full_text = " ".join(text_blocks).strip()

        # Strip preamble — model sometimes prefixes with reasoning
        import re

        # Remove everything before and including a colon if it starts with preamble
        full_text = re.sub(
            r'^(?:based on|here (?:is|\'s)|let me|i\'?ll search)[^:]*:\s*',
            '', full_text, flags=re.IGNORECASE
        ).strip()

        # Remove leading "I'll search..." type sentences
        full_text = re.sub(
            r"^I'?ll\s+search\s+.*?(?:\.\s+)",
            "", full_text, flags=re.IGNORECASE
        ).strip()

        # Clean trailing whitespace before punctuation
        summary = re.sub(r'\s+([.!?])', r'\1', full_text).strip()

        if not summary or len(summary) < 20:
            print("  Response too short, using fallback")
            return fallback_summary(scores)

        # Truncate if too long
        if len(summary) > 400:
            # Cut at last sentence boundary within limit
            truncated = summary[:400]
            last_period = truncated.rfind('.')
            if last_period > 200:
                summary = truncated[:last_period + 1]
            else:
                summary = truncated.rstrip() + "..."

        return summary

    except Exception as e:
        print(f"  API error: {e}, using fallback")
        return fallback_summary(scores)


def main():
    print("Generating market summary...")
    summary = generate_summary()
    scores = load_scores()

    output = {
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'summary': summary,
        'scores': {
            name.lower(): {'score': s['score'], 'label': s['label']}
            for name, s in scores.items()
        }
    }

    with open('data/market-summary.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"  Summary ({len(summary)} chars): {summary}")
    print("Done.")


if __name__ == '__main__':
    main()
