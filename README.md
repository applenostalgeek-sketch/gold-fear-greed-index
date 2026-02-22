# OnOff.Markets - Multi-Asset Fear & Greed Indices

Real-time sentiment tracking across **4 major asset classes**: Gold, Bonds, Stocks, and Crypto. Independent, transparent indices with complete methodology disclosure.

![Status](https://img.shields.io/badge/Status-Live-success)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Updated](https://img.shields.io/badge/Updated-Daily%20at%202%3A00%20UTC-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**Live Site**: [onoff.markets](https://onoff.markets)

---

## Overview

OnOff.Markets provides **transparent Fear & Greed indices** for four markets:

- **Gold** - Safe haven sentiment (5 components)
- **Bonds** - Treasury market sentiment (6 components)
- **Stocks** - Equity market sentiment (7 components)
- **Crypto** - Cryptocurrency sentiment (5 components)

Each index outputs a **0-100 score**:
- **0-25**: Extreme Fear
- **26-45**: Fear
- **46-55**: Neutral
- **56-75**: Greed
- **76-100**: Extreme Greed

The homepage features a **Market Sentiment Indicator** that compares risk assets (Stocks + Crypto) versus safe havens (Bonds + Gold) to show the overall market mood.

---

## Philosophy

Every sentiment tool claims to measure "fear & greed," but none explain *how*. Vague methodology. Hidden calculations. "Proprietary algorithms."

OnOff.Markets was built on the opposite principle:

- **Complete transparency** - All formulas published on each asset page
- **Open methodology** - Every component weight disclosed
- **Free data sources** - Yahoo Finance + FRED API only
- **Daily updates** - Automated via GitHub Actions
- **No subscriptions** - Free forever

Each index measures **sentiment TOWARDS that market** (whether people are buying or selling), following Alternative.me's philosophy for crypto.

If you can't verify it, you can't trust it.

---

## Market Sentiment Indicator

The homepage score combines all 4 indices into a single risk-on / risk-off reading:

```
Greed Side  = (Stocks Score + Crypto Score) / 2
Fear Side   = (Bonds Score + Gold Score) / 2
Sentiment   = Greed Side - Fear Side
Position    = ((Sentiment + 100) / 200) x 100
```

Below 50 = fear dominates (investors prefer safe havens). Above 50 = greed dominates (investors chase risk).

---

## Index Components

### Gold (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| GLD Price Momentum | 30% | Direct 14-day GLD ETF performance (PRIMARY) |
| RSI & Moving Averages | 25% | Proportional distance-based MA50/MA200 + RSI signal |
| Dollar Index | 20% | DXY 14-day change with x15 multiplier (inverse correlation) |
| Real Rates | 15% | 10-Year TIPS yields from FRED (x18.75 scoring) |
| VIX | 10% | Z-score vs 3-month average (safe haven demand) |

### Bonds (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Yield Curve Shape | 20% | 10Y-2Y Treasury spread from FRED (structural signal) |
| Duration Risk / TLT | 20% | Direct 14-day TLT ETF performance |
| Credit Quality | 20% | LQD vs TLT performance (credit spreads) |
| Real Rates | 15% | 10-Year TIPS yields (x10 multiplier) |
| Bond Volatility | 15% | 5-day vs 30-day TLT vol (MOVE proxy, x75) |
| Equity vs Bonds | 10% | TLT vs SPY relative performance (x8) |

### Stocks (7 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Price Strength | 20% | Direct 14-day SPY performance (x8 multiplier) |
| VIX | 20% | Continuous linear formula: 90 - (VIX-10) x 3.2 |
| Momentum | 15% | SPY RSI(14) 70% + MA50 position 30% |
| Market Participation | 15% | RSP vs SPY (x18 multiplier, equal vs cap-weight) |
| Junk Bonds | 10% | HYG vs TLT (credit risk appetite) |
| Safe Haven | 10% | TLT momentum inverted (flight-to-safety signal) |
| Sector Rotation | 10% | QQQ vs XLP (tech vs defensive, x5 multiplier) |

### Crypto (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Context | 30% | 30-day BTC price trend (x2.0 multiplier, centered at 50) |
| RSI & Moving Averages | 20% | BTC RSI direct (60%) + MA position (40%) |
| Bitcoin Dominance | 20% | BTC vs ETH performance (inverted, x3.0) |
| Volume Trend | 15% | 7d vs 30d volume ratio, direction-adjusted (x50) |
| Volatility | 15% | 14-day annualized vol (inverted, 40-80% thresholds) |

Full methodology with detailed explanations available on each asset page ([Gold](https://onoff.markets/gold.html), [Bonds](https://onoff.markets/bonds.html), [Stocks](https://onoff.markets/stocks.html), [Crypto](https://onoff.markets/crypto.html)).

---

## Data Sources

All data is **100% free** and publicly accessible:

- **Yahoo Finance** (via yfinance): All price, volume, and technical data
  - ETFs: GLD, TLT, SPY, SHY, LQD, HYG, RSP, QQQ, XLP, TIP
  - Indices: ^VIX, DX-Y.NYB (DXY), ^TNX, ^IRX
  - Crypto: BTC-USD, ETH-USD

- **FRED API** (Federal Reserve): Treasury yields and TIPS
  - DGS2, DGS10 (2Y/10Y Treasury yields)
  - DFII10 (10-Year TIPS real yields)

**Fallback Strategy**: FRED > Yahoo Finance for weekend/holiday protection (never defaults to neutral 50.0).

---

## Architecture

### Project Structure

```
gold-fear-greed-index/
├── gold_fear_greed.py          # Gold index calculator
├── bonds_fear_greed.py         # Bonds index calculator
├── stocks_fear_greed.py        # Stocks index calculator
├── crypto_fear_greed.py        # Crypto index calculator
├── generate_insights.py        # 5-year insights generator
├── rebuild_5y.py               # 5-year history rebuild
├── index.html                  # Homepage (market sentiment + cross-asset chart)
├── gold.html                   # Gold index page (score + methodology + FAQ schema)
├── bonds.html                  # Bonds index page
├── stocks.html                 # Stocks index page
├── crypto.html                 # Crypto index page
├── about.html                  # Story, data sources, FAQ
├── shared.css                  # Shared styles (nav, footer, mobile menu)
├── chart.css                   # Chart styles (toolbar, tooltip, canvas)
├── asset.css                   # Asset page styles (hero, bar, components, methodology)
├── shared.js                   # Shared utilities (chart helpers, mobile menu, logo dots)
├── asset-chart.js              # Asset page chart logic (parameterized via ASSET_CONFIG)
├── data/
│   ├── *-fear-greed.json       # Daily F&G data (365 days x 4 assets)
│   ├── history-5y-*.json       # 5-year aligned score+price history
│   └── insights-5y-*.json     # Pre-computed correlation & stats
├── .github/
│   └── workflows/
│       └── update-index.yml    # Daily automation (2:00 UTC)
└── README.md
```

### Frontend Architecture

The frontend uses a **shared component system** to avoid code duplication across 7 HTML pages:

- **`shared.css`** + **`chart.css`** + **`asset.css`**: Layered CSS loaded by each page as needed
- **`shared.js`**: Common utilities (`getColor()`, `scoreToY()`, zones, mobile menu, `updateLogoDots()`)
- **`asset-chart.js`**: Full asset page logic (data loading, chart rendering, tooltips) parameterized via `window.ASSET_CONFIG`

Each asset page only defines its unique config:

```html
<script>
    window.ASSET_CONFIG = {
        color: '#FFD700',
        name: 'Gold',
        dataUrl: 'data/gold-fear-greed.json',
        phrases: { extremeFear: '...', fear: '...', neutral: '...', greed: '...', extremeGreed: '...' }
    };
</script>
<script src="shared.js"></script>
<script src="asset-chart.js"></script>
```

### SEO

Each asset page includes:
- Full meta tags (Open Graph, Twitter Card)
- JSON-LD `WebApplication` structured data
- JSON-LD `FAQPage` schema with 3 targeted questions per asset
- Complete methodology section for crawlability

The about page includes a JSON-LD `FAQPage` schema with 6 general questions.

---

## Installation & Local Development

### Prerequisites

- Python 3.9+
- Git
- GitHub account (for automation)

### Step 1: Clone & Install

```bash
git clone https://github.com/applenostalgeek-sketch/gold-fear-greed-index.git
cd gold-fear-greed-index
pip install -r requirements.txt
```

### Step 2: Get FRED API Key

1. Visit [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html)
2. Create free account & generate API key
3. Set environment variable:

```bash
export FRED_API_KEY="your_api_key_here"
```

### Step 3: Run Locally

```bash
# Individual indices
python gold_fear_greed.py
python bonds_fear_greed.py --FRED_API_KEY="your_key"
python stocks_fear_greed.py
python crypto_fear_greed.py

# Force rebuild 365-day history
python gold_fear_greed.py --force-rebuild
```

### Step 4: Test Frontend

```bash
python -m http.server 8080
# Visit http://localhost:8080
```

---

## Deployment (GitHub Pages)

The site auto-deploys to GitHub Pages from the `main` branch.

### Setup

1. Go to repo Settings > Pages
2. Source: Deploy from branch `main`
3. Folder: `/ (root)`
4. Add `FRED_API_KEY` to Settings > Secrets and variables > Actions

### Automation

GitHub Actions runs **daily at 2:00 UTC**:

1. Calculates all 4 indices
2. Generates/updates JSON files in `data/`
3. Commits changes to `main`
4. GitHub Pages auto-redeploys

**Manual trigger**: Actions tab > "Update Fear & Greed Indices" > Run workflow

---

## Data Update Schedule

- **Calculation**: Daily at 2:00 AM UTC (3:00 AM Paris / 9:00 PM ET)
- **Market data**: Real-time when script runs
- **History retention**: 365 days rolling window + 5-year rebuilt history
- **Methodology**: Documented on each asset page and on [about.html](https://onoff.markets/about.html)

| Source | Limit | Usage |
|--------|-------|-------|
| Yahoo Finance | Unlimited | ~15-20 calls/day |
| FRED API | 120 req/min | ~5 calls/day |

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Disclaimer

This project is provided for informational purposes only and does not constitute financial advice. Investments carry risks. Consult a qualified financial advisor before making investment decisions.

These indices are analytical tools designed to complement, not replace, fundamental analysis and risk management.

---

## Acknowledgments

- Inspired by [Alternative.me's Crypto Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/)
- Data: Yahoo Finance & Federal Reserve Economic Data (FRED)
- Built with Claude Code
- Hosted on GitHub Pages

---

## Contact

- **Live Site**: [onoff.markets](https://onoff.markets)
- **Email**: contact@onoff.markets
- **Issues**: [GitHub Issues](https://github.com/applenostalgeek-sketch/gold-fear-greed-index/issues)
