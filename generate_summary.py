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
        prev_score = data['history'][1]['score'] if len(data['history']) > 1 else score
        delta = round(score - prev_score, 1)
        assets[name] = {'score': score, 'label': label, 'delta': delta}

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
        delta_str = f"+{s['delta']}" if s['delta'] >= 0 else str(s['delta'])
        score_lines.append(f"- {name}: {s['score']} ({s['label']}, {delta_str} vs yesterday)")

    sentiment = scores['Sentiment']
    score_lines.append(f"- Market Sentiment (average): {sentiment['score']} ({sentiment['label']})")
    scores_text = "\n".join(score_lines)

    prompt = f"""You write the daily "What's happening" summary for onoff.markets, a multi-asset Fear & Greed index site tracking Gold, Stocks, Crypto, and Bonds.

Today's Fear & Greed scores (0 = Extreme Fear, 100 = Extreme Greed):
{scores_text}

Instructions:
- Write 2-3 sentences, MAX 350 characters total
- ALL FOUR markets (Gold, Stocks, Crypto, Bonds) must be referenced — do not skip any
- Focus on the Fear & Greed SCORES and LABELS, not on asset prices or returns
- Use web search to identify today's key market catalysts (macro data, geopolitics, central bank decisions, earnings, etc.)
- Be factual: describe observed correlations ("amid rising tensions"), not definitive causation ("because of")
- Mention specific catalysts when clear (e.g. "jobs report", "Fed meeting", "oil spike")
- If scores barely moved, focus on what's keeping markets in their current state
- Vary your phrasing — avoid repeating yesterday's structure
- No emojis, no markdown, plain text only
- Write in English
- Do NOT start with "Markets" — vary sentence openings

Yesterday's summary (do not repeat similar phrasing):
"{previous}"

Write the summary now. Output ONLY the summary text, nothing else."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }],
            messages=[{"role": "user", "content": prompt}]
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
        # Remove everything up to and including known preamble endings
        for pattern in [r"here'?s the summary:\s*",
                        r"here is the summary:\s*",
                        r"based on my research[^:]*:\s*"]:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                full_text = full_text[match.end():].strip()

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
