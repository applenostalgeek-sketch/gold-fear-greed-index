#!/usr/bin/env python3
"""
Generate favicon in multiple sizes from SVG
"""
from PIL import Image, ImageDraw
import os

def create_favicon(size, filename):
    """Create a favicon with two white dots on black background"""
    # Create image with black background
    img = Image.new('RGB', (size, size), color='#0a0a0a')
    draw = ImageDraw.Draw(img)

    # Calculate dot positions and size
    dot_radius = int(size * 0.12)  # 12% of image size
    left_x = int(size * 0.35)
    right_x = int(size * 0.65)
    center_y = int(size * 0.5)

    # Draw two white circles
    draw.ellipse(
        [left_x - dot_radius, center_y - dot_radius,
         left_x + dot_radius, center_y + dot_radius],
        fill='#ffffff'
    )
    draw.ellipse(
        [right_x - dot_radius, center_y - dot_radius,
         right_x + dot_radius, center_y + dot_radius],
        fill='#ffffff'
    )

    img.save(filename)
    print(f"✓ Created {filename} ({size}x{size})")

# Generate different sizes
sizes = [
    (16, 'favicon-16x16.png'),
    (32, 'favicon-32x32.png'),
    (180, 'apple-touch-icon.png'),
    (192, 'android-chrome-192x192.png'),
    (512, 'android-chrome-512x512.png'),
]

for size, filename in sizes:
    create_favicon(size, filename)

# Create favicon.ico with multiple sizes
img_16 = Image.open('favicon-16x16.png')
img_32 = Image.open('favicon-32x32.png')
img_16.save('favicon.ico', format='ICO', sizes=[(16, 16), (32, 32)], append_images=[img_32])
print("✓ Created favicon.ico (16x16, 32x32)")

print("\n✅ All favicons generated successfully!")
