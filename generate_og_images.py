"""Generate minimalist OG images (1200x630) matching OnOff.Markets site style."""

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = (10, 10, 10)          # #0a0a0a
DARK = (26, 26, 26)        # #1a1a1a
WHITE = (255, 255, 255)
GRAY = (102, 102, 102)     # #666
LIGHT_GRAY = (153, 153, 153)  # #999

# Fear -> Greed gradient colors (matching site exactly)
COLORS = {
    'extreme_fear': (239, 68, 68),    # #ef4444
    'fear':         (245, 158, 11),   # #f59e0b
    'neutral':      (255, 255, 255),  # #ffffff
    'greed':        (34, 197, 94),    # #22c55e
    'extreme_greed':(6, 182, 212),    # #06b6d4
}

# Per-page accent
ACCENTS = {
    'home':   WHITE,
    'gold':   (234, 179, 8),     # #eab308
    'bonds':  (59, 130, 246),    # #3b82f6
    'stocks': (34, 197, 94),     # #22c55e
    'crypto': (249, 115, 22),    # #f97316
    'about':  LIGHT_GRAY,
}

FONT_BOLD = '/Library/Fonts/SF-Compact-Display-Bold.otf'
FONT_SEMI = '/Library/Fonts/SF-Compact-Display-Semibold.otf'
FONT_MED  = '/Library/Fonts/SF-Compact-Display-Medium.otf'
FONT_REG  = '/Library/Fonts/SF-Compact-Display-Regular.otf'

OUT = '/Users/admin/gold-fear-greed-index'


def draw_gradient_bar(draw, x, y, w, h):
    """Draw the thin horizontal gradient bar matching the site's progress bar."""
    segments = [
        COLORS['extreme_fear'],
        COLORS['fear'],
        COLORS['neutral'],
        COLORS['greed'],
        COLORS['extreme_greed'],
    ]
    seg_w = w // len(segments)
    for i, color in enumerate(segments):
        sx = x + i * seg_w
        sw = seg_w if i < len(segments) - 1 else (w - i * seg_w)
        draw.rounded_rectangle([sx, y, sx + sw, y + h], radius=h // 2, fill=color)


def draw_bar_smooth(draw, x, y, w, h):
    """Draw a smooth gradient bar by interpolating between segment colors."""
    segments = [
        COLORS['extreme_fear'],
        COLORS['fear'],
        COLORS['neutral'],
        COLORS['greed'],
        COLORS['extreme_greed'],
    ]
    n = len(segments)
    for px in range(w):
        t = px / max(w - 1, 1)
        pos = t * (n - 1)
        idx = int(pos)
        frac = pos - idx
        if idx >= n - 1:
            idx = n - 2
            frac = 1.0
        c1 = segments[idx]
        c2 = segments[idx + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * frac)
        g = int(c1[1] + (c2[1] - c1[1]) * frac)
        b = int(c1[2] + (c2[2] - c1[2]) * frac)
        draw.line([(x + px, y), (x + px, y + h - 1)], fill=(r, g, b))


def generate(page_key, title, subtitle, filename):
    img = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    accent = ACCENTS[page_key]

    # --- Logo: "OnOff ●● .Markets" ---
    logo_y = 80
    font_logo = ImageFont.truetype(FONT_BOLD, 28)
    font_logo_gray = ImageFont.truetype(FONT_MED, 28)
    font_dots = ImageFont.truetype(FONT_REG, 16)

    # "OnOff"
    draw.text((80, logo_y), "OnOff", fill=WHITE, font=font_logo)
    onoff_w = draw.textbbox((0, 0), "OnOff", font=font_logo)[2]
    # "●●"
    draw.text((80 + onoff_w + 8, logo_y + 7), "●●", fill=GRAY, font=font_dots)
    dots_w = draw.textbbox((0, 0), "●●", font=font_dots)[2]
    # ".Markets"
    draw.text((80 + onoff_w + 8 + dots_w + 8, logo_y), ".Markets", fill=GRAY, font=font_logo_gray)

    # --- Title ---
    font_title = ImageFont.truetype(FONT_BOLD, 72)
    title_y = 180
    draw.text((80, title_y), title, fill=accent, font=font_title)

    # --- Subtitle ---
    font_sub = ImageFont.truetype(FONT_REG, 26)
    sub_y = title_y + 90
    draw.text((80, sub_y), subtitle, fill=GRAY, font=font_sub)

    # --- Gradient bar (matching site) ---
    bar_x = 80
    bar_y = sub_y + 70
    bar_w = WIDTH - 160
    bar_h = 6
    draw_bar_smooth(draw, bar_x, bar_y, bar_w, bar_h)

    # --- Bar labels ---
    font_label = ImageFont.truetype(FONT_REG, 16)
    label_y = bar_y + 16
    draw.text((bar_x, label_y), "EXTREME FEAR", fill=GRAY, font=font_label)
    # Center "NEUTRAL"
    neutral_w = draw.textbbox((0, 0), "NEUTRAL", font=font_label)[2]
    draw.text((bar_x + bar_w // 2 - neutral_w // 2, label_y), "NEUTRAL", fill=GRAY, font=font_label)
    # Right "EXTREME GREED"
    greed_w = draw.textbbox((0, 0), "EXTREME GREED", font=font_label)[2]
    draw.text((bar_x + bar_w - greed_w, label_y), "EXTREME GREED", fill=GRAY, font=font_label)

    # --- URL bottom right ---
    font_url = ImageFont.truetype(FONT_MED, 18)
    url = "onoff.markets"
    url_w = draw.textbbox((0, 0), url, font=font_url)[2]
    draw.text((WIDTH - 80 - url_w, HEIGHT - 60), url, fill=GRAY, font=font_url)

    path = f"{OUT}/{filename}"
    img.save(path, 'PNG', optimize=True)
    print(f"OK: {path}")


pages = [
    ('home',   'Market Sentiment',        'Real-time Fear & Greed across Gold, Bonds, Stocks & Crypto',  'og-home.png'),
    ('gold',   'Gold Fear & Greed',        'Real-time sentiment indicator for the gold market',           'og-gold.png'),
    ('bonds',  'Bonds Fear & Greed',       'Real-time sentiment indicator for the bond market',           'og-bonds.png'),
    ('stocks', 'Stocks Fear & Greed',      'Real-time sentiment indicator for the stock market',          'og-stocks.png'),
    ('crypto', 'Crypto Fear & Greed',      'Real-time sentiment indicator for crypto markets',            'og-crypto.png'),
    ('about',  'About & Methodology',      'Transparent calculations behind our Fear & Greed indices',    'og-about.png'),
]

for p in pages:
    generate(*p)

print("\nDone.")
