#!/usr/bin/env python3
"""Generate AI market context using Claude Haiku from component data only.

Called daily after the 4 index calculations. Produces a 2-3 sentence
context explaining WHY scores are what they are, based ONLY on component
data (RSI, VIX, DXY, yields, etc.) — no web search, no external catalysts.
Falls back to a template if the API is unavailable.
"""

import json
import os
from datetime import datetime, timezone


COMPONENT_NAMES = {
    'Gold': {
        'gld_price': 'GLD Price',
        'momentum': 'Momentum',
        'gold_vs_spy': 'Gold vs SPY',
        'dollar_index': 'Dollar Index',
        'real_rates': 'Real Rates',
        'vix': 'VIX',
    },
    'Stocks': {
        'price_strength': 'Price Strength',
        'vix': 'VIX',
        'momentum': 'Momentum',
        'market_participation': 'Breadth',
        'junk_bonds': 'Credit Spread',
        'safe_haven': 'Safe Haven',
        'sector_rotation': 'Sector Rotation',
    },
    'Crypto': {
        'context': 'BTC Price',
        'momentum': 'Momentum',
        'dominance': 'BTC Dominance',
        'volume': 'Volume',
        'volatility': 'Volatility',
    },
    'Bonds': {
        'yield_curve': 'Yield Curve',
        'duration_risk': 'Duration Risk',
        'credit_quality': 'Credit Quality',
        'real_rates': 'Real Rates',
        'bond_volatility': 'Bond Volatility',
        'equity_vs_bonds': 'Equity vs Bonds',
    },
}


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
        assets[name] = {'score': score, 'label': label,
                        'delta': delta_1d, 'delta_7d': delta_7d}

    avg = round(sum(a['score'] for a in assets.values()) / 4, 1)
    assets['Sentiment'] = {'score': avg, 'label': get_label(avg)}
    return assets


def load_components():
    """Load component details from each asset JSON."""
    result = {}
    for name, filename in [('Gold', 'gold-fear-greed.json'),
                           ('Stocks', 'stocks-fear-greed.json'),
                           ('Crypto', 'crypto-fear-greed.json'),
                           ('Bonds', 'bonds-fear-greed.json')]:
        with open(f'data/{filename}') as f:
            data = json.load(f)
        result[name] = data.get('components', {})
    return result


def format_components(scores, components):
    """Format component data as text for the prompt."""
    lines = []
    for name in ['Gold', 'Stocks', 'Crypto', 'Bonds']:
        s = scores[name]
        d1 = f"+{s['delta']}" if s['delta'] >= 0 else str(s['delta'])
        d7 = f"+{s['delta_7d']}" if s['delta_7d'] >= 0 else str(s['delta_7d'])
        lines.append(f"{name} ({s['score']} — {s['label']}, {d1} 1d, {d7} 7d):")

        names_map = COMPONENT_NAMES.get(name, {})
        for key, comp in components.get(name, {}).items():
            label = names_map.get(key, key)
            weight_pct = int(comp['weight'] * 100)
            lines.append(f"  - {label} ({weight_pct}%): {comp['score']} — {comp['detail']}")
        lines.append("")

    sentiment = scores['Sentiment']
    lines.append(f"Market Sentiment (avg): {sentiment['score']} ({sentiment['label']})")
    return "\n".join(lines)


def load_previous_summary():
    """Load yesterday's summary to avoid repetition."""
    path = 'data/market-summary.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        return data.get('summary', '')
    return ''


def fallback_summary(scores, components):
    """Interpretive fallback when API is unavailable."""
    parts = []

    # Detect VIX stress (shared between gold and stocks)
    gold_vix = components.get('Gold', {}).get('vix', {})
    stocks_vix = components.get('Stocks', {}).get('vix', {})
    vix_score = gold_vix.get('score', 50)
    if vix_score >= 80:
        parts.append("Market stress is elevated, boosting safe-haven demand.")
    elif vix_score <= 20:
        parts.append("Low volatility signals investor complacency.")

    # Detect gold-dollar divergence
    gold_dollar = components.get('Gold', {}).get('dollar_index', {})
    gold_price = components.get('Gold', {}).get('gld_price', {})
    if gold_dollar.get('score', 50) < 30 and gold_price.get('score', 50) > 60:
        parts.append("Gold is rallying despite dollar strength, suggesting strong underlying demand.")

    # Detect weak equity momentum
    stocks_mom = components.get('Stocks', {}).get('momentum', {})
    stocks_breadth = components.get('Stocks', {}).get('market_participation', {})
    if stocks_mom.get('score', 50) < 40 and stocks_breadth.get('score', 50) < 40:
        parts.append("Stocks show weak momentum with narrow market participation.")
    elif stocks_mom.get('score', 50) > 60 and stocks_breadth.get('score', 50) > 60:
        parts.append("Broad equity participation supports the current stock rally.")

    # Detect crypto volatility
    crypto_vol = components.get('Crypto', {}).get('volatility', {})
    if crypto_vol.get('score', 50) <= 25:
        parts.append("Crypto volatility remains extreme, weighing on sentiment.")

    # Detect bond signals
    yield_curve = components.get('Bonds', {}).get('yield_curve', {})
    if yield_curve.get('score', 50) > 70:
        parts.append("A steep yield curve points to economic optimism in bond markets.")
    elif yield_curve.get('score', 50) < 30:
        parts.append("A flat or inverted yield curve signals economic caution.")

    if not parts:
        # Generic fallback
        asset_scores = {k: v for k, v in scores.items() if k != 'Sentiment'}
        highest = max(asset_scores, key=lambda k: asset_scores[k]['score'])
        lowest = min(asset_scores, key=lambda k: asset_scores[k]['score'])
        parts.append(
            f"Risk appetite favors {highest} over {lowest}, "
            f"with overall sentiment near {scores['Sentiment']['label'].lower()} territory."
        )

    return " ".join(parts[:3]), None


def generate_summary():
    scores = load_scores()
    components = load_components()

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("  No ANTHROPIC_API_KEY set, using fallback")
        return fallback_summary(scores, components)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"  Anthropic client error: {e}, using fallback")
        return fallback_summary(scores, components)

    previous = load_previous_summary()
    components_text = format_components(scores, components)

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    system = f"""You write market context for a multi-asset Fear & Greed dashboard. Today is {today}.

Use web search to find this week's main market catalysts. Connect them to the sentiment data.

Rules:
- Name the 1-2 biggest catalysts this week (Fed, jobs data, tariffs, geopolitics, etc.) and explain how they affect markets.
- Write like a dashboard subtitle, not a research note. Be concise and direct.
- ONLY cite facts found in your search results. Never invent data.
- Only reference events that have already happened or are happening TODAY ({today}). Never reference upcoming events.
- Do NOT restate scores or indicators the user already sees.
- Do NOT predict. Current state only.
- Plain text. No emojis, no markdown.
- Vary from yesterday's context.

Output format (strictly follow this, no other text):
SUMMARY: [2-3 sentences, under 450 characters. For the website. Must end on a complete sentence — never cut mid-clause.]
TWEET: [1 punchy sentence, under 220 characters. Same idea, shorter.]"""

    user_msg = f"""Dashboard data:

{components_text}

Yesterday's context (vary): "{previous}"

What are the 1-2 key catalysts driving these markets this week?"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=350,
            system=system,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }],
            messages=[{"role": "user", "content": user_msg}]
        )

        # Web search splits response across multiple text blocks
        import re
        text_parts = [block.text for block in response.content
                      if block.type == "text" and block.text.strip()]
        raw = " ".join(part.strip() for part in text_parts).strip()
        raw = re.sub(r'\s+([,.;:!?])', r'\1', raw)
        raw = re.sub(r'\s{2,}', ' ', raw)

        # Parse SUMMARY: and TWEET: format
        # Clean markdown bold markers and HTML tags the model sometimes adds
        raw = re.sub(r'\*{1,2}', '', raw)
        raw = re.sub(r'<br\s*/?>', ' ', raw)
        summary = raw
        tweet = None
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?=\s*TWEET:|\Z)', raw, re.DOTALL)
        tweet_match = re.search(r'TWEET:\s*(.+)', raw, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()
        if tweet_match:
            tweet = tweet_match.group(1).strip()

        if not summary or len(summary) < 20:
            print("  Response too short, using fallback")
            return fallback_summary(scores, components)

        # Truncate summary if too long — cut at sentence boundary, not decimal point
        if len(summary) > 450:
            truncated = summary[:450]
            # Find last sentence end: period/!/? followed by space or end of string
            matches = list(re.finditer(r'[.!?](?=\s|$)', truncated))
            if matches and matches[-1].start() > 100:
                summary = truncated[:matches[-1].start() + 1]
            else:
                # Cut at last word boundary, strip trailing continuation punctuation
                last_space = truncated.rfind(' ')
                cut = truncated[:last_space].rstrip(' ,;:—-') if last_space > 100 else truncated.rstrip(' ,;:—-')
                summary = cut + '.'

        # Truncate tweet if too long
        if tweet and len(tweet) > 220:
            truncated = tweet[:220]
            last_space = truncated.rfind(' ')
            if last_space > 100:
                tweet = truncated[:last_space] + "..."
            else:
                tweet = truncated.rstrip() + "..."

        return summary, tweet

    except Exception as e:
        print(f"  API error: {e}, using fallback")
        return fallback_summary(scores, components)  # returns (summary, None)


def main():
    print("Generating AI context summary...")
    summary, tweet = generate_summary()
    scores = load_scores()

    output = {
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'summary': summary,
        'tweet': tweet,
        'scores': {
            name.lower(): {'score': s['score'], 'label': s['label']}
            for name, s in scores.items()
        }
    }

    with open('data/market-summary.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"  Summary ({len(summary)} chars): {summary}")
    if tweet:
        print(f"  Tweet ({len(tweet)} chars): {tweet}")
    print("Done.")


if __name__ == '__main__':
    main()
