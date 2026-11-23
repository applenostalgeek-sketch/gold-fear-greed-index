# OnOff.Markets - Multi-Asset Fear & Greed Indices

Daily fear & greed scores across **4 major asset classes**: Gold, Bonds, Stocks, and Crypto. Independent, transparent indices with complete methodology disclosure.

![Status](https://img.shields.io/badge/Status-Live-success)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Updated](https://img.shields.io/badge/Updated-Daily%20at%2004%3A07%20UTC-blue)
![License](https://img.shields.io/badge/License-MIT-green)

**Live Site**: [onoff.markets](https://onoff.markets)

---

## Overview

OnOff.Markets provides **transparent Fear & Greed indices** for four markets:

- **Gold** - Safe haven sentiment (6 components)
- **Bonds** - Treasury market sentiment (6 components)
- **Stocks** - Equity market sentiment (7 components)
- **Crypto** - Cryptocurrency sentiment (5 components)

Each index outputs a **0-100 score**:
- **0-25**: Extreme Fear
- **26-45**: Fear
- **46-55**: Neutral
- **56-75**: Greed
- **76-100**: Extreme Greed

The homepage features a **Market Sentiment Indicator** — the simple average of all four indices — showing the overall market mood at a glance.

---

## Philosophy

Every sentiment tool claims to measure "fear & greed," but none explain *how*. Vague methodology. Hidden calculations. "Proprietary algorithms."

OnOff.Markets was built on the opposite principle:

- **Complete transparency** - All formulas published on each asset page
- **Open methodology** - Every component weight disclosed
- **Free data sources** - Yahoo Finance + FRED (Alpha Vantage as a backup for prices)
- **Daily updates** - Automated via GitHub Actions
- **No subscriptions** - Free forever

Each index measures **sentiment TOWARDS that market** (whether people are buying or selling), following Alternative.me's philosophy for crypto.

If you can't verify it, you can't trust it.

---

## Market Sentiment Indicator

The homepage score is the simple average of all 4 individual indices:

```
Sentiment = (Gold + Stocks + Crypto + Bonds) / 4
```

Below 50 = fear dominates across markets. Above 50 = optimism prevails.

---

## Open Data (free, no key)

Every number on the site comes from public JSON files, refreshed daily. No account, no key; cross-origin requests are allowed.

| File | Contents |
|------|----------|
| [`/data/gold-fear-greed.json`](https://onoff.markets/data/gold-fear-greed.json) | Today's score, label, each component (score, weight, detail) and 365 days of history. Same for `bonds`, `stocks`, `crypto` |
| [`/data/history-5y-gold.json`](https://onoff.markets/data/history-5y-gold.json) | 5 years of daily `date`, `score`, `label`, `price`. Same for `bonds`, `stocks`, `crypto` |
| [`/data/market-summary.json`](https://onoff.markets/data/market-summary.json) | The five scores of the day and the short daily context |

Notes:
- Values before early 2026 were **reconstructed** with the same formulas; they were not published live at the time.
- Dates: in the live part (since early 2026) an entry dated D describes the close of D-1, since the calculation runs before the market opens; in the reconstructed part it describes the close of D.
- These scores describe the present. They are not forecasts: tested on 5 years, they do not reliably predict the next move.

If you use the data, a link to [onoff.markets](https://onoff.markets) is appreciated.

---

## Index Components

### Gold (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| GLD Price | 25% | 14-day GLD ETF performance |
| Momentum | 20% | RSI(14) and position against the 50-day average |
| Gold vs Stocks | 20% | GLD vs SPY over 14 days |
| VIX | 15% | Z-score vs its recent average (stock-market fear counts in gold's favor) |
| Dollar Index | 10% | DXY 14-day change and position vs its 30-day average (inverse) |
| Real Rates | 10% | 10-Year TIPS yield from FRED vs its average (inverse) |

### Bonds (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Duration Risk / TLT | 30% | Direct 14-day TLT ETF performance (x12 multiplier) |
| Yield Curve Shape | 20% | 10Y-2Y Treasury spread from FRED (structural signal) |
| Credit Quality | 20% | HYG vs LQD performance (credit spreads) |
| Real Rates | 15% | 10-Year TIPS yields from FRED (x10 multiplier) |
| Bond Volatility | 10% | 5-day vs 30-day TLT vol (MOVE proxy, x60) |
| Equity vs Bonds | 5% | TLT vs SPY relative performance (x8) |

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

All data is **free** and publicly accessible:

- **Yahoo Finance** (via yfinance): prices, volumes and technical data
  - ETFs: GLD, TLT, SPY, SHY, LQD, HYG, RSP, QQQ, XLP
  - Indices and futures: ^VIX, ^TNX, DX-Y.NYB (dollar index), GC=F
  - Crypto: BTC-USD, ETH-USD
- **FRED** (Federal Reserve): DGS2, DGS10 (yield curve), DFII10 (10-Year TIPS real yield)
- **Alpha Vantage**: backup source for the published price when Yahoo fails

**When a source fails**: real rates fall back from FRED to Yahoo (^TNX), and the published price falls back to Alpha Vantage. A component whose data cannot be fetched at all scores 50 (neutral) for that day, keeping its weight.

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
│   ├── *-fear-greed.json       # Today's score, components and 365 days of history
│   ├── history-5y-*.json       # 5-year aligned score+price history
│   └── insights-5y-*.json     # Pre-computed correlation & stats
├── .github/
│   └── workflows/
│       └── update-index.yml    # Daily automation (04:07 UTC)
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

## Deployment & Automation

The site is static and hosted on **Netlify**, which redeploys on every push to `main`.

Once a day at **04:07 UTC**, a Netlify scheduled function starts the GitHub Actions workflow (`update-index.yml`); a GitHub cron at 04:37 UTC is a backup and stands down if the day is already published. The workflow:

1. Calculates the 4 indices (and their published prices)
2. Appends the day to the 5-year history and recomputes cross-asset correlations
3. Writes a short daily context with Claude (labelled as AI-generated on the site)
4. Emails subscribers when an index swings sharply or hits a new 6-month high or low
5. Commits the JSON files to `main`, which triggers the Netlify deploy

**Manual trigger**: Actions tab > "Update Gold, Stocks, Crypto & Bonds Fear & Greed Indices" > Run workflow

---

## Data Update Schedule

- **Calculation**: daily at 04:07 UTC, on the previous session's close
- **History**: 365 days in each `*-fear-greed.json`, 5 years in `history-5y-*.json`
- **Methodology**: documented on each asset page and on [about.html](https://onoff.markets/about.html)

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
- Hosted on Netlify

---

## Contact

- **Live Site**: [onoff.markets](https://onoff.markets)
- **Email**: contact@onoff.markets
- **Issues**: [GitHub Issues](https://github.com/applenostalgeek-sketch/gold-fear-greed-index/issues)
