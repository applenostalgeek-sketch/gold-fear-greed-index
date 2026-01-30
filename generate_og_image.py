#!/usr/bin/env python3
"""
Generate OpenGraph image for social media sharing
1200x630 px recommended size
"""

from PIL import Image, ImageDraw, ImageFont
import os


def create_og_image():
    """Create OpenGraph image"""
    # Image dimensions (OpenGraph recommended size)
    width = 1200
    height = 630

    # Create image with dark background
    img = Image.new('RGB', (width, height), color='#0f0f23')
    draw = ImageDraw.Draw(img)

    # Try to use system fonts, fallback to default
    try:
        font_title = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 80)
        font_subtitle = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 40)
        font_text = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 32)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # Draw gradient-like effect (simulate with rectangles)
    for i in range(height):
        alpha = int(255 * (1 - i / height) * 0.2)
        color = (15 + alpha // 3, 15 + alpha // 3, 35 + alpha // 3)
        draw.rectangle([(0, i), (width, i + 1)], fill=color)

    # Draw gold accent bars at top and bottom
    draw.rectangle([(0, 0), (width, 8)], fill='#FFD700')
    draw.rectangle([(0, height - 8), (width, height)], fill='#FFD700')

    # Draw icon/logo circle
    circle_x = 150
    circle_y = height // 2
    circle_radius = 100

    # Gradient circle effect
    for r in range(circle_radius, 0, -2):
        color_factor = r / circle_radius
        color = (
            int(255 * color_factor),
            int(215 * color_factor),
            int(0 * color_factor)
        )
        draw.ellipse(
            [(circle_x - r, circle_y - r), (circle_x + r, circle_y + r)],
            fill=color
        )

    # Draw gold bar in circle
    bar_width = 80
    bar_height = 50
    bar_x = circle_x - bar_width // 2
    bar_y = circle_y - bar_height // 2
    draw.rounded_rectangle(
        [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
        radius=5,
        fill='#0f0f23'
    )
    draw.rounded_rectangle(
        [(bar_x + 5, bar_y + 5), (bar_x + bar_width - 5, bar_y + bar_height - 5)],
        radius=3,
        fill='#FFD700'
    )

    # Add shine effect
    draw.rectangle(
        [(bar_x + 10, bar_y + 10), (bar_x + 15, bar_y + bar_height - 10)],
        fill='#FFFFFF'
    )

    # Draw text
    text_x = 320
    title_y = 180
    subtitle_y = 280
    features_y = 380

    # Title
    draw.text((text_x, title_y), "Gold Fear & Greed Index", fill='#FFD700', font=font_title)

    # Subtitle
    draw.text((text_x, subtitle_y), "Market Sentiment Indicator for Gold", fill='#FFFFFF', font=font_subtitle)

    # Features
    features = [
        "✓ 100% Transparent & Open Source",
        "✓ Real-time Data from 7 Indicators",
        "✓ Daily Updates via GitHub Actions"
    ]

    for i, feature in enumerate(features):
        draw.text((text_x, features_y + i * 50), feature, fill='#A0A0C0', font=font_text)

    # Save image
    output_path = 'og-image.png'
    img.save(output_path, 'PNG', quality=95)
    print(f"✅ OpenGraph image created: {output_path}")
    print(f"   Size: {width}x{height}px")
    print(f"   File size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == "__main__":
    create_og_image()
