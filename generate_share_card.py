#!/usr/bin/env python3
"""Generate dynamic OG share card (1200x630) with current Fear & Greed scores.
Design matches share-card-preview.html. Uses 2x supersampling for quality."""

import json
import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
SCALE = 2  # Supersampling factor
WHITE = (255, 255, 255)
GRAY = (102, 102, 102)      # #666
LIGHT_GRAY = (153, 153, 153) # #999
AMBER = (245, 158, 11)      # #f59e0b (dot color from prototype)
DARK_GRAY = (85, 85, 85)    # #555

ASSETS = ['gold', 'bonds', 'stocks', 'crypto']
ASSET_LABELS = {'gold': 'Gold', 'bonds': 'Bonds', 'stocks': 'Stocks', 'crypto': 'Crypto'}


def score_color(score):
    s = round(score)
    if s <= 25:
        return (239, 68, 68)      # #ef4444 extreme fear
    elif s <= 45:
        return (245, 158, 11)     # #f59e0b fear
    elif s <= 55:
        return (255, 255, 255)    # #ffffff neutral
    elif s <= 75:
        return (34, 197, 94)      # #22c55e greed
    else:
        return (6, 182, 212)      # #06b6d4 extreme greed


def score_label(score):
    s = round(score)
    if s <= 25:
        return "Extreme Fear"
    elif s <= 45:
        return "Fear"
    elif s <= 55:
        return "Neutral"
    elif s <= 75:
        return "Greed"
    else:
        return "Extreme Greed"


def get_font(style, size):
    """Load font with fallback for GitHub Actions (Ubuntu)."""
    fonts = {
        'bold': [
            '/Library/Fonts/SF-Compact-Display-Bold.otf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        ],
        'medium': [
            '/Library/Fonts/SF-Compact-Display-Medium.otf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ],
        'regular': [
            '/Library/Fonts/SF-Compact-Display-Regular.otf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ],
    }
    for path in fonts.get(style, fonts['regular']):
        if os.path.exists(path):
            return ImageFont.truetype(path, size * SCALE)
    return ImageFont.load_default()


def load_scores():
    """Load current scores from the 4 JSON files."""
    scores = {}
    for asset in ASSETS:
        path = f'data/{asset}-fear-greed.json'
        with open(path, 'r') as f:
            data = json.load(f)
        scores[asset] = round(data['score'])
    return scores


def draw_gradient_bg(img):
    """Draw diagonal gradient background matching the prototype."""
    # Prototype: linear-gradient(145deg, #13111a 0%, #1a1825 50%, #13111a 100%)
    w, h = img.size
    pixels = img.load()
    c1 = (19, 17, 26)   # #13111a
    c2 = (26, 24, 37)   # #1a1825
    for y in range(h):
        for x in range(w):
            # Diagonal gradient (145deg approximation)
            t = (x / w * 0.42 + y / h * 0.58)
            if t < 0.5:
                f = t / 0.5
                r = int(c1[0] + (c2[0] - c1[0]) * f)
                g = int(c1[1] + (c2[1] - c1[1]) * f)
                b = int(c1[2] + (c2[2] - c1[2]) * f)
            else:
                f = (t - 0.5) / 0.5
                r = int(c2[0] + (c1[0] - c2[0]) * f)
                g = int(c2[1] + (c1[1] - c2[1]) * f)
                b = int(c2[2] + (c1[2] - c2[2]) * f)
            pixels[x, y] = (r, g, b)


def draw_circle_score(draw, cx, cy, radius, score, font_score, font_label_small):
    """Draw a circle with score and label for an asset."""
    color = score_color(score)
    label = score_label(score)

    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=color, width=3 * SCALE
    )

    score_text = str(round(score))
    bbox = draw.textbbox((0, 0), score_text, font=font_score)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 8 * SCALE), score_text, fill=color, font=font_score)

    bbox = draw.textbbox((0, 0), label, font=font_label_small)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, cy + 18 * SCALE), label, fill=color, font=font_label_small)


def center_text(draw, y, text, font, fill):
    """Draw text centered horizontally."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH * SCALE // 2 - tw // 2, y), text, fill=fill, font=font)
    return bbox[3] - bbox[1]  # return text height


def generate():
    scores = load_scores()
    # Market Sentiment — simple average of all 4 indices
    sentiment = round((scores['gold'] + scores['stocks'] + scores['crypto'] + scores['bonds']) / 4)

    S = SCALE
    img = Image.new('RGB', (WIDTH * S, HEIGHT * S), (19, 17, 26))
    draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_logo = get_font('bold', 20)
    font_logo_dot = get_font('medium', 20)
    font_date = get_font('regular', 14)
    font_subtitle = get_font('regular', 14)
    font_big_score = get_font('bold', 80)
    font_big_label = get_font('bold', 18)
    font_circle_score = get_font('bold', 26)
    font_circle_label = get_font('regular', 11)
    font_asset_name = get_font('medium', 13)
    font_url = get_font('medium', 14)

    # --- Header: centered logo + date ---
    header_y = 40 * S

    # Logo: "On··Off .Markets" — centered
    parts = [
        ("On", WHITE, font_logo),
        ("..", AMBER, font_logo_dot),
        ("Off ", WHITE, font_logo),
        (".Markets", AMBER, font_logo_dot),
    ]
    total_logo_w = sum(draw.textbbox((0, 0), t, font=f)[2] for t, _, f in parts)
    logo_x = WIDTH * S // 2 - total_logo_w // 2
    for text, color, font in parts:
        draw.text((logo_x, header_y), text, fill=color, font=font)
        logo_x += draw.textbbox((0, 0), text, font=font)[2]

    # Date centered below logo
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    center_text(draw, header_y + 34 * S, date_str, font_date, GRAY)

    # --- Center: MARKET SENTIMENT + big score + label ---
    center_y = 155 * S
    center_text(draw, center_y, "MARKET SENTIMENT", font_subtitle, GRAY)

    sentiment_color = score_color(sentiment)
    sentiment_label = score_label(sentiment).upper()

    # Big score
    score_text = str(sentiment)
    bbox = draw.textbbox((0, 0), score_text, font=font_big_score)
    tw = bbox[2] - bbox[0]
    score_y = center_y + 30 * S
    draw.text((WIDTH * S // 2 - tw // 2, score_y), score_text, fill=sentiment_color, font=font_big_score)

    # Label
    center_text(draw, score_y + 88 * S, sentiment_label, font_big_label, sentiment_color)

    # --- Asset circles row ---
    circle_y = 420 * S
    radius = 48 * S
    n_assets = 4
    gap = 56 * S
    total_width = n_assets * (radius * 2) + (n_assets - 1) * gap
    start_x = WIDTH * S // 2 - total_width // 2 + radius

    for i, asset in enumerate(ASSETS):
        cx = start_x + i * (radius * 2 + gap)
        draw_circle_score(draw, cx, circle_y, radius, scores[asset],
                         font_circle_score, font_circle_label)

        name = ASSET_LABELS[asset]
        bbox = draw.textbbox((0, 0), name, font=font_asset_name)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, circle_y + radius + 14 * S), name, fill=LIGHT_GRAY, font=font_asset_name)

    # --- Footer: URL centered ---
    url_text = "onoff.markets"
    center_text(draw, HEIGHT * S - 42 * S, url_text, font_url, DARK_GRAY)

    # Downsample to final size (LANCZOS for smooth result)
    img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

    # Save
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'og-home.png')
    img.save(output_path, 'PNG', optimize=True)
    print(f"Share card generated: {output_path}")
    print(f"Sentiment: {sentiment} ({score_label(sentiment)})")
    for asset in ASSETS:
        print(f"  {ASSET_LABELS[asset]}: {scores[asset]} ({score_label(scores[asset])})")


if __name__ == '__main__':
    generate()
