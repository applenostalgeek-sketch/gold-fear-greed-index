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

- **🪙 Gold** - Safe haven sentiment (5 components)
- **📊 Bonds** - Treasury market sentiment (6 components)
- **📈 Stocks** - Equity market sentiment (7 components)
- **₿ Crypto** - Cryptocurrency sentiment (5 components)

Each index outputs a **0-100 score**:
- **0-25**: Extreme Fear 🔴
- **26-45**: Fear 🟠
- **46-55**: Neutral 🟡
- **56-75**: Greed 🟢
- **76-100**: Extreme Greed 🟦

**Unique Feature**: Market Rotation Indicator showing Risk-On vs Risk-Off capital flows across all 4 asset classes.

---

## Philosophy

Unlike black-box proprietary indices:
- ✅ **Complete transparency** - All formulas published on about.html
- ✅ **Open methodology** - Every component weight disclosed
- ✅ **Free data sources** - Yahoo Finance + FRED API only
- ✅ **Daily updates** - Automated via GitHub Actions
- ✅ **No subscriptions** - Free forever

Each index measures **sentiment TOWARDS that market** (whether people are buying or selling), following Alternative.me's philosophy for crypto.

---

## Index Components

### 🪙 Gold (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| GLD Price Momentum | 30% | Direct 14-day GLD ETF performance (PRIMARY) |
| RSI & Moving Averages | 25% | Proportional distance-based MA50/MA200 + RSI signal |
| Dollar Index | 20% | DXY 14-day change with ×15 multiplier (inverse correlation) |
| Real Rates | 15% | 10-Year TIPS yields from FRED (×18.75 scoring) |
| VIX | 10% | Z-score vs 3-month average (safe haven demand) |

**Recalibrated Feb 2026**: Removed Gold vs S&P 500 and Volatility (redundant/insignificant). Added RSI/MA mean-reversion signal. VIX uses z-score normalization.

### 📊 Bonds (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Yield Curve Shape | 20% | 10Y-2Y Treasury spread from FRED (structural signal) |
| Duration Risk / TLT | 20% | Direct 14-day TLT ETF performance |
| Credit Quality | 20% | LQD vs TLT performance (credit spreads) |
| Real Rates | 15% | 10-Year TIPS yields (×10 multiplier) |
| Bond Volatility | 15% | 5-day vs 30-day TLT vol (MOVE proxy, ×75) |
| Equity vs Bonds | 10% | TLT vs SPY relative performance (×8) |

**Recalibrated Feb 2026**: Removed Term Premium (redundant with TLT). Added Bond Volatility and Equity vs Bonds rotation signals. Rebalanced weights for better crisis detection.

### 📈 Stocks (7 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Price Strength | 20% | Direct 14-day SPY performance (×8 multiplier) |
| VIX | 20% | Continuous linear formula: 90 - (VIX-10) × 3.2 |
| Momentum | 15% | SPY RSI(14) 70% + MA50 position 30% |
| Market Participation | 15% | RSP vs SPY (×18 multiplier, equal vs cap-weight) |
| Junk Bonds | 10% | HYG vs TLT (credit risk appetite) |
| Safe Haven | 10% | TLT momentum inverted (flight-to-safety signal) |
| Sector Rotation | 10% | QQQ vs XLP (tech vs defensive, ×5 multiplier) |

**Recalibrated Feb 2026**: Added Safe Haven signal. VIX uses continuous formula (no step cliffs). Reduced Price Strength to 20% for better signal diversity.

### ₿ Crypto (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Context | 30% | 30-day BTC price trend (×2.0 multiplier, centered at 50) |
| RSI & Moving Averages | 20% | BTC RSI direct (60%) + MA position (40%) |
| Bitcoin Dominance | 20% | BTC vs ETH performance (inverted, ×3.0) |
| Volume Trend | 15% | 7d vs 30d volume ratio, direction-adjusted (×50) |
| Volatility | 15% | 14-day annualized vol (inverted, 40-80% thresholds) |

**Recalibrated Feb 2026**: Removed Price Momentum (redundant with Context). Added Volume Trend as price-independent signal. Recentered all baselines to 50. Adapted volatility thresholds for crypto (40-80% vs old 20-40%).

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

**Fallback Strategy**: FRED → Yahoo Finance for weekend/holiday protection (never defaults to neutral 50.0).

---

## Project Structure

```
gold-fear-greed-index/
├── gold_fear_greed.py          # Gold index calculator
├── bonds_fear_greed.py         # Bonds index calculator
├── stocks_fear_greed.py        # Stocks index calculator
├── crypto_fear_greed.py        # Crypto index calculator
├── generate_insights.py        # 5-year insights generator
├── generate_prices.py          # Price history generator
├── rebuild_5y.py               # 5-year history rebuild
├── index.html                  # Homepage (market rotation)
├── gold.html / bonds.html      # Individual index pages
├── stocks.html / crypto.html
├── compare.html                # F&G vs Price comparison (5Y data)
├── about.html                  # Complete methodology
├── shared.css                  # Shared styles (nav, footer, mobile)
├── chart.css                   # Chart styles (toolbar, tooltip)
├── asset.css                   # Asset page styles (hero, bar, components)
├── shared.js                   # Shared utilities (chart helpers, mobile menu)
├── asset-chart.js              # Asset page chart logic (parameterized)
├── data/
│   ├── *-fear-greed.json       # Daily F&G data (365 days × 4 assets)
│   ├── history-5y-*.json       # 5-year aligned score+price history
│   └── insights-5y-*.json     # Pre-computed correlation & stats
├── .github/
│   └── workflows/
│       └── update-index.yml    # Daily automation (2:00 UTC)
└── README.md
```

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

Calculate all 4 indices:
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

### Setup GitHub Pages

1. Go to repo Settings → Pages
2. Source: Deploy from branch `main`
3. Folder: `/ (root)`
4. Save

### Configure Secrets

Add to Settings → Secrets and variables → Actions:
- `FRED_API_KEY`: Your FRED API key

### Automation

GitHub Actions workflow runs **daily at 2:00 UTC**:

1. Calculates all 4 indices
2. Generates/updates JSON files in `data/`
3. Commits changes to `main`
4. GitHub Pages auto-redeploys

**Manual trigger**: Actions tab → "Update Fear & Greed Indices" → Run workflow

---

## Customization

### Adjust Component Weights

Edit the Python files (e.g., `gold_fear_greed.py` line ~365):

```python
weights = {
    'gld_price': 0.30,      # Modify as needed
    'dollar_index': 0.20,
    # ... ensure total = 1.0
}
```

### Modify Scoring Thresholds

Change extreme fear/greed boundaries:

```python
if score <= 25:
    label = "Extreme Fear"
elif score <= 45:
    label = "Fear"
# etc.
```

### Frontend Design

- Shared styles: `shared.css` (nav, footer), `chart.css` (charts), `asset.css` (asset pages)
- Shared JS: `shared.js` (utilities), `asset-chart.js` (parameterized via `window.ASSET_CONFIG`)
- Page-specific logic: Inline `<style>` and `<script>` blocks in each HTML file

---

## Troubleshooting

### "No data available" errors

Check Yahoo Finance connection:
```bash
python -c "import yfinance as yf; print(yf.Ticker('GLD').history(period='1d'))"
```

### FRED API errors

Verify API key:
```bash
echo $FRED_API_KEY
```

Falls back to Yahoo Finance (TIP ETF) if FRED unavailable.

### GitHub Actions fails

1. Check Actions tab for error logs
2. Verify `FRED_API_KEY` secret is set
3. Ensure repo has write permissions for `GITHUB_TOKEN`

---

## Data Update Schedule

- **Calculation**: Daily at 2:00 AM UTC (3:00 AM Paris / 9:00 PM ET)
- **Market data**: Real-time when script runs
- **History retention**: 365 days rolling window
- **Methodology**: Fully documented at [onoff.markets/about.html](https://onoff.markets/about.html)

---

## API Rate Limits

| Source | Limit | Usage |
|--------|-------|-------|
| Yahoo Finance | Unlimited | ~15-20 calls/day |
| FRED API | 120 req/min | ~5 calls/day |

Well within free tier limits.

---

## Philosophy & Transparency

**Why this project exists:**

Every sentiment tool claims to measure "fear & greed," but none explain *how*. Vague methodology. Hidden calculations. "Proprietary algorithms."

OnOff.Markets was built on the opposite principle:
- **Complete transparency** - Every formula published
- **Open source approach** - All calculations verifiable
- **No black boxes** - Full methodology on about.html
- **Free forever** - No subscriptions, no paywalls

If you can't verify it, you can't trust it.

---

## License

MIT License - See [LICENSE](LICENSE) file

---

## Disclaimer

⚠️ **Important**: This index is provided for informational purposes only and does not constitute financial advice. Investments carry risks. Consult a qualified financial advisor before making investment decisions.

These indices are analytical tools designed to complement—not replace—fundamental analysis and risk management.

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

---

**⭐ Star this repository if you find it useful!**
