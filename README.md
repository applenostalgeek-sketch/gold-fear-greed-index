# Gold Fear & Greed Index

A market sentiment indicator for gold, similar to the cryptocurrency Fear & Greed Index by Alternative.me, but adapted to the specifics of the gold market.

![Gold Fear & Greed Index](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

The Gold Fear & Greed Index aggregates 6 different market indicators into a single score (0-100) that represents market sentiment toward gold:

- **0-25**: Extreme Fear 🔴
- **26-45**: Fear 🟠
- **46-55**: Neutral 🟡
- **56-75**: Greed 🟢
- **76-100**: Extreme Greed 🟦

## Index Components

| Component | Weight | Description |
|-----------|--------|-------------|
| **Volatility** | 20% | Current 14-day volatility vs 30-day average |
| **Momentum** | 25% | Price vs MA50/MA200 + RSI(14) |
| **Gold vs Stocks** | 15% | 14-day performance: Gold vs S&P500 |
| **ETF Flows** | 20% | GLD (SPDR Gold Trust) volume & price trends |
| **VIX** | 10% | Current VIX level vs average |
| **Real Rates** | 10% | 10-Year TIPS yields |

## Data Sources

All data sources are **100% free**:
- **Yahoo Finance** (via yfinance): Gold, S&P500, VIX, GLD prices
- **FRED API** (Federal Reserve): 10-Year TIPS real rates

## Project Structure

```
gold-fear-greed-index/
├── gold_fear_greed.py          # Main calculation script
├── requirements.txt            # Python dependencies
├── index.html                  # Frontend interface
├── style.css                   # Styling
├── script.js                   # Frontend logic
├── data/
│   └── gold-fear-greed.json   # Generated index data
├── assets/                     # Optional images/icons
├── .github/
│   └── workflows/
│       └── update-index.yml   # GitHub Actions automation
├── .gitignore
└── README.md
```

## Installation & Setup

### Prerequisites

- Python 3.9 or higher
- Git
- GitHub account (for automation)
- Netlify account (for hosting)

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/gold-fear-greed-index.git
cd gold-fear-greed-index
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Get FRED API Key (Optional but Recommended)

1. Visit [FRED API Key Registration](https://fred.stlouisfed.org/docs/api/api_key.html)
2. Create a free account
3. Generate an API key
4. Set it as an environment variable:

```bash
export FRED_API_KEY="your_api_key_here"
```

Or add it to your `.env` file:

```bash
echo "FRED_API_KEY=your_api_key_here" > .env
```

### Step 4: Run the Script Locally

```bash
python gold_fear_greed.py
```

This will:
- Calculate the current Gold Fear & Greed Index
- Display component scores in the terminal
- Generate/update `data/gold-fear-greed.json`

### Step 5: Test the Frontend Locally

Open `index.html` in your browser or use a local server:

```bash
# Python 3
python -m http.server 8000

# Then visit http://localhost:8000
```

## Deployment to Netlify

### Method 1: GitHub Integration (Recommended)

1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Gold Fear & Greed Index"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/gold-fear-greed-index.git
   git push -u origin main
   ```

2. **Connect to Netlify**:
   - Go to [Netlify](https://www.netlify.com/)
   - Click "Add new site" → "Import an existing project"
   - Choose GitHub and select your repository
   - Build settings:
     - **Base directory**: (leave empty)
     - **Build command**: (leave empty - this is a static site)
     - **Publish directory**: `/` (root)
   - Click "Deploy site"

3. **Configure GitHub Secrets**:
   - Go to your GitHub repository
   - Settings → Secrets and variables → Actions
   - Add new secret:
     - Name: `FRED_API_KEY`
     - Value: Your FRED API key

### Method 2: Manual Deploy

1. Install Netlify CLI:
   ```bash
   npm install -g netlify-cli
   ```

2. Deploy:
   ```bash
   netlify deploy --prod
   ```

## Automation with GitHub Actions

The included workflow (`.github/workflows/update-index.yml`) automatically:

- Runs daily at 8:00 UTC
- Calculates the updated index
- Commits the new `data/gold-fear-greed.json`
- Triggers Netlify to redeploy

### Workflow Configuration

The workflow requires:
- `FRED_API_KEY` secret (set in GitHub repository secrets)
- Write permissions for the `GITHUB_TOKEN` (enabled by default)

To test the workflow manually:
1. Go to your GitHub repository
2. Actions → "Update Gold Fear & Greed Index"
3. Click "Run workflow"

## Customization

### Adjust Component Weights

Edit `gold_fear_greed.py` line ~264:

```python
weights = {
    'volatility': 0.20,      # Change to desired weight
    'momentum': 0.25,
    'gold_vs_spy': 0.15,
    'etf_flows': 0.20,
    'vix': 0.10,
    'real_rates': 0.10
}
```

**Note**: Weights must sum to 1.0

### Change Score Thresholds

Edit `gold_fear_greed.py` line ~288:

```python
if total_score <= 25:
    label = "Extreme Fear"
elif total_score <= 45:
    label = "Fear"
# ... modify as needed
```

### Customize Frontend Design

- **Colors**: Edit CSS variables in `style.css` (lines 8-17)
- **Gauge design**: Modify SVG in `index.html` (lines 21-36)
- **Chart style**: Update canvas drawing functions in `script.js`

## Troubleshooting

### Issue: "No data available" error

**Solution**: Check data sources
```bash
python -c "import yfinance as yf; print(yf.Ticker('GC=F').history(period='1d'))"
```

### Issue: FRED API errors

**Solution**: Verify API key
```bash
echo $FRED_API_KEY
```

If missing or invalid, the index will use a neutral score (50) for real rates.

### Issue: GitHub Actions fails

**Solution**: Check workflow logs
1. Go to Actions tab in GitHub
2. Click on the failed run
3. Review error messages
4. Ensure `FRED_API_KEY` secret is set correctly

### Issue: Netlify not updating

**Solution**:
1. Check if GitHub Actions successfully committed changes
2. Verify Netlify build hooks are configured
3. Manually trigger a redeploy from Netlify dashboard

## Data Update Schedule

- **Calculation**: Daily at 8:00 UTC (via GitHub Actions)
- **Market data**: Real-time (when script runs)
- **History retention**: Last 30 days

## API Rate Limits

| Source | Limit | Notes |
|--------|-------|-------|
| Yahoo Finance (yfinance) | Unlimited | Free tier, no registration |
| FRED API | 120 requests/minute | Free with API key |

This project uses well below these limits (6-7 API calls per day).

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

⚠️ **Important**: This index is provided for informational purposes only and does not constitute financial advice. Investments carry risks. Always consult a qualified financial advisor before making investment decisions.

The index is experimental and should not be the sole basis for trading decisions.

## Acknowledgments

- Inspired by [Alternative.me's Crypto Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/)
- Data provided by Yahoo Finance and Federal Reserve Economic Data (FRED)
- Built with Claude Code

## Contact & Support

- **Issues**: [GitHub Issues](https://github.com/YOUR-USERNAME/gold-fear-greed-index/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR-USERNAME/gold-fear-greed-index/discussions)

## Roadmap

Potential future enhancements:
- [ ] Add more data sources (sentiment analysis, social media)
- [ ] Historical backtesting against gold price movements
- [ ] API endpoint for programmatic access
- [ ] Email/SMS alerts for extreme readings
- [ ] Multiple language support
- [ ] Mobile app

---

**Star ⭐ this repository if you find it useful!**
