# 🐦 Tweet Generator - OnOff.Markets

Simple script to generate formatted tweets for daily market sentiment updates.

## Usage

Run this script each morning to generate a ready-to-post tweet:

```bash
# From anywhere on your system
python3 /Users/admin/gold-fear-greed-index/generate_tweet.py

# Or from the project directory
cd /Users/admin/gold-fear-greed-index
python3 generate_tweet.py
```

**The script uses absolute paths, so it works from any directory!**

## Output Example

```
📊 Market Sentiment - 04 Feb 2026

📊 Bonds: 49 (Neutral)
🪙 Gold: 67 (Greed)
📈 Stocks: 52 (Neutral)
₿ Crypto: 12 (Extreme Fear)

Market: Risk-Off (37.0%)
💡 Gold 🟢 | Bonds ⚪ | Stocks ⚪ | Crypto 🔴

→ onoff.markets
```

**Visual indicators:**
- 🟢 Greed (high sentiment)
- ⚪ Neutral
- 🔴 Fear (low sentiment)

## How It Works

1. Reads the latest data from `data/*.json` files
2. Calculates market rotation (Risk-On vs Risk-Off)
3. Formats a tweet with all 4 indices + rotation
4. Displays the tweet in your terminal

**Simply copy-paste the output to Twitter!** 📋

## Why Not Automated?

Twitter's API now requires a **$100/month subscription** to post tweets programmatically. For an indie project, manual posting is more practical.

## Frequency

Post daily at **09:00 Paris time** (or whenever you want) to share the latest sentiment analysis with your audience.
