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

- **🪙 Gold** - Safe haven sentiment (6 components)
- **📊 Bonds** - Treasury market sentiment (5 components)
- **📈 Stocks** - Equity market sentiment (6 components)
- **₿ Crypto** - Cryptocurrency sentiment (5 components, calibrated vs Alternative.me)

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

### 🪙 Gold (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| GLD Price Momentum | 30% | Direct 14-day GLD ETF performance (PRIMARY) |
| Dollar Index | 20% | DXY 14-day change (inverse correlation) |
| Real Rates | 20% | 10-Year TIPS yields from FRED |
| Gold vs S&P 500 | 15% | 14-day relative performance |
| VIX | 10% | Safe haven demand indicator |
| Volatility | 5% | 14-day GLD price volatility |

**Recalibrated Jan 2026**: Increased direct GLD performance weight from 25% to 30% to better capture buying/selling sentiment.

### 📊 Bonds (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| TLT Price Momentum | 30% | Direct 14-day TLT ETF performance (PRIMARY) |
| Yield Curve | 15% | 10Y-2Y Treasury spread from FRED |
| Credit Quality | 20% | LQD vs TLT performance (credit spreads) |
| Real Rates | 10% | 10-Year TIPS yields |
| Term Premium | 25% | TLT vs SHY (long vs short treasuries) |

**Recalibrated Feb 2026**: Adjusted TLT scaling from ±5% to ±4% to reflect actual volatility (90% of moves within ±3.7%).

### 📈 Stocks (6 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Price Strength | 30% | Direct 14-day SPY performance (PRIMARY) |
| VIX | 20% | Market fear gauge (inverted) |
| Momentum | 15% | SPY RSI(14) momentum |
| Market Breadth | 15% | RSP vs SPY (equal-weight vs cap-weight) |
| Sector Rotation | 10% | XLY vs XLU (cyclical vs defensive) |
| Junk Bonds | 10% | HYG vs LQD (credit risk appetite) |

**Recalibrated Jan 2026**: Increased Price Strength from 5% to 30% to emphasize direct buying/selling sentiment.

### ₿ Crypto (5 Components)
| Component | Weight | Description |
|-----------|--------|-------------|
| Context | 35% | 30-day BTC price trend (PRIMARY) |
| Bitcoin Dominance | 25% | BTC vs ETH performance (inverted) |
| Volatility | 15% | 14-day annualized volatility (inverted) |
| Price Momentum | 15% | 14-day BTC price change |
| Momentum | 10% | BTC RSI + moving averages |

**Calibrated vs Alternative.me** with 8.3 points average error.

---

## Data Sources

All data is **100% free** and publicly accessible:

- **Yahoo Finance** (via yfinance): All price, volume, and technical data
  - ETFs: GLD, TLT, SPY, SHY, LQD, HYG, RSP, XLY, XLU, TIP
  - Indices: ^VIX, DXY
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
├── index.html                  # Homepage (market rotation)
├── gold.html / bonds.html      # Individual index pages
├── stocks.html / crypto.html
├── about.html                  # Complete methodology
├── data/
│   ├── gold-fear-greed.json    # Gold historical data (365 days)
│   ├── bonds-fear-greed.json   # Bonds historical data (365 days)
│   ├── stocks-fear-greed.json  # Stocks historical data (365 days)
│   └── crypto-fear-greed.json  # Crypto historical data (365 days)
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

- Colors: Edit CSS variables in each HTML file
- Layout: Modify HTML structure
- Charts: Canvas.js code in `<script>` sections

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
