#!/usr/bin/env python3
"""Generate dynamic OG share card (1200x630) with current Fear & Greed scores.
Uses 2x supersampling for smooth circles and crisp text."""

import json
import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
SCALE = 2  # Supersampling factor
BG = (10, 10, 10)           # #0a0a0a
WHITE = (255, 255, 255)
GRAY = (102, 102, 102)      # #666
LIGHT_GRAY = (153, 153, 153)

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


def generate():
    scores = load_scores()
    sentiment = round(sum(scores.values()) / len(scores))

    S = SCALE
    img = Image.new('RGB', (WIDTH * S, HEIGHT * S), BG)
    draw = ImageDraw.Draw(img)

    # Fonts (sizes are already multiplied by SCALE in get_font)
    font_logo = get_font('bold', 24)
    font_logo_gray = get_font('medium', 24)
    font_date = get_font('regular', 18)
    font_subtitle = get_font('regular', 16)
    font_big_score = get_font('bold', 96)
    font_big_label = get_font('bold', 22)
    font_circle_score = get_font('bold', 28)
    font_circle_label = get_font('regular', 11)
    font_asset_name = get_font('medium', 14)
    font_url = get_font('medium', 16)

    # --- Header: Logo left, Date right ---
    header_y = 36 * S
    draw.text((60 * S, header_y), "On", fill=WHITE, font=font_logo)
    on_w = draw.textbbox((0, 0), "On", font=font_logo)[2]
    draw.text((60 * S + on_w, header_y + 2 * S), "··", fill=GRAY, font=font_date)
    dots_w = draw.textbbox((0, 0), "··", font=font_date)[2]
    draw.text((60 * S + on_w + dots_w, header_y), "Off", fill=WHITE, font=font_logo)
    off_w = draw.textbbox((0, 0), "Off", font=font_logo)[2]
    draw.text((60 * S + on_w + dots_w + off_w + 6 * S, header_y), ".Markets", fill=GRAY, font=font_logo_gray)

    # Date (right-aligned)
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    date_bbox = draw.textbbox((0, 0), date_str, font=font_date)
    date_w = date_bbox[2] - date_bbox[0]
    draw.text((WIDTH * S - 60 * S - date_w, header_y + 4 * S), date_str, fill=GRAY, font=font_date)

    # --- Center: MARKET SENTIMENT + big score + label ---
    center_y = 140 * S
    subtitle_text = "MARKET SENTIMENT"
    bbox = draw.textbbox((0, 0), subtitle_text, font=font_subtitle)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH * S // 2 - tw // 2, center_y), subtitle_text, fill=GRAY, font=font_subtitle)

    sentiment_color = score_color(sentiment)
    sentiment_label = score_label(sentiment).upper()

    score_text = str(sentiment)
    bbox = draw.textbbox((0, 0), score_text, font=font_big_score)
    tw = bbox[2] - bbox[0]
    score_y = center_y + 34 * S
    draw.text((WIDTH * S // 2 - tw // 2, score_y), score_text, fill=sentiment_color, font=font_big_score)

    bbox = draw.textbbox((0, 0), sentiment_label, font=font_big_label)
    tw = bbox[2] - bbox[0]
    draw.text((WIDTH * S // 2 - tw // 2, score_y + 100 * S), sentiment_label, fill=sentiment_color, font=font_big_label)

    # --- Asset circles row ---
    circle_y = 440 * S
    radius = 48 * S
    n_assets = 4
    total_width = n_assets * (radius * 2) + (n_assets - 1) * 80 * S
    start_x = WIDTH * S // 2 - total_width // 2 + radius

    for i, asset in enumerate(ASSETS):
        cx = start_x + i * (radius * 2 + 80 * S)
        draw_circle_score(draw, cx, circle_y, radius, scores[asset],
                         font_circle_score, font_circle_label)

        name = ASSET_LABELS[asset]
        bbox = draw.textbbox((0, 0), name, font=font_asset_name)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, circle_y + radius + 14 * S), name, fill=LIGHT_GRAY, font=font_asset_name)

    # --- Footer: URL bottom right ---
    url_text = "onoff.markets"
    bbox = draw.textbbox((0, 0), url_text, font=font_url)
    url_w = bbox[2] - bbox[0]
    draw.text((WIDTH * S - 60 * S - url_w, HEIGHT * S - 45 * S), url_text, fill=GRAY, font=font_url)

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
