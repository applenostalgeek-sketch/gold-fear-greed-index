#!/usr/bin/env python3
"""
Crypto Fear & Greed Index Calculator
Transparent, open-source sentiment indicator for cryptocurrency markets
Based on 6 public data sources, consistent with Gold and Stocks indices
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os


class CryptoFearGreedIndex:
    def __init__(self):
        self.score = None
        self.label = None
        self.components = {}

    def calculate_momentum_score(self) -> tuple:
        """
        Calculate BTC momentum score based on RSI and moving averages
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="1y")

            if len(hist) < 200:
                raise ValueError("Insufficient data for momentum calculation")

            close_prices = hist['Close']

            # RSI(14)
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            # Moving averages
            ma50 = close_prices.rolling(window=50).mean().iloc[-1]
            ma200 = close_prices.rolling(window=200).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

            # Score calculation
            rsi_score = current_rsi  # RSI already 0-100

            # MA position score
            if current_price > ma50 and current_price > ma200:
                ma_score = 75  # Strong bullish
            elif current_price > ma50:
                ma_score = 60  # Moderate bullish
            elif current_price > ma200:
                ma_score = 40  # Weak
            else:
                ma_score = 25  # Bearish

            # Weighted average
            score = (rsi_score * 0.6) + (ma_score * 0.4)
            score = max(0, min(100, score))

            detail = f"RSI: {current_rsi:.0f}, Price {'>' if current_price > ma50 else '<'} MA50"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Momentum error: {e}")
            return (50.0, "Data unavailable")

    def calculate_volatility_score(self) -> tuple:
        """
        Calculate volatility score (inverted - low volatility = confidence)
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="3mo")

            if hist.empty:
                raise ValueError("No BTC data")

            # Calculate returns
            returns = hist['Close'].pct_change().dropna()

            # Current 14-day volatility
            current_vol = returns.tail(14).std() * np.sqrt(365) * 100  # Annualized %

            # 30-day average volatility
            vol_30d = returns.tail(30).std() * np.sqrt(365) * 100

            # Score: lower volatility = higher score (less fear)
            ratio = current_vol / vol_30d if vol_30d > 0 else 1.0

            # Normalize: ratio of 0.5 = score 75, ratio of 1.5 = score 25
            score = 50 + (1 - ratio) * 50
            score = max(0, min(100, score))

            detail = f"Vol 14d: {current_vol:.1f}% vs avg: {vol_30d:.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Volatility error: {e}")
            return (50.0, "Data unavailable")

    def calculate_volume_score(self) -> tuple:
        """
        Calculate volume score (high volume with rising price = greed)
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="3mo")

            if len(hist) < 30:
                raise ValueError("Insufficient data")

            # Average volume last 14 days vs previous 30 days
            volume_14d = hist['Volume'].tail(14).mean()
            volume_30d = hist['Volume'].tail(30).mean()

            # Price momentum last 14 days
            price_14d_ago = hist['Close'].iloc[-14]
            current_price = hist['Close'].iloc[-1]
            price_change = ((current_price - price_14d_ago) / price_14d_ago) * 100

            # Volume ratio
            volume_ratio = volume_14d / volume_30d if volume_30d > 0 else 1.0

            # Score: high volume + rising price = greed
            volume_score = 50 + (volume_ratio - 1) * 50  # Normalized around 1.0
            price_score = 50 + (price_change * 2)  # Price momentum

            # Combined score
            score = (volume_score * 0.5) + (price_score * 0.5)
            score = max(0, min(100, score))

            detail = f"Vol: {volume_ratio:.2f}x avg, Price: {price_change:+.1f}% 14d"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Volume error: {e}")
            return (50.0, "Data unavailable")

    def calculate_btc_dominance_score(self) -> tuple:
        """
        Calculate Bitcoin Dominance score
        Rising BTC.D = flight to quality within crypto = relative fear in alts
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            eth = yf.Ticker("ETH-USD")

            btc_hist = btc.history(period="1mo")
            eth_hist = eth.history(period="1mo")

            if len(btc_hist) < 14 or len(eth_hist) < 14:
                raise ValueError("Insufficient data")

            # Calculate BTC vs ETH performance (proxy for dominance)
            btc_return = ((btc_hist['Close'].iloc[-1] - btc_hist['Close'].iloc[-14]) / btc_hist['Close'].iloc[-14]) * 100
            eth_return = ((eth_hist['Close'].iloc[-1] - eth_hist['Close'].iloc[-14]) / eth_hist['Close'].iloc[-14]) * 100

            relative_perf = btc_return - eth_return

            # If BTC outperforms ETH = dominance rising = safer sentiment in crypto
            # We score this as moderate (not extreme) since rising dominance = partial fear
            score = 50 + (relative_perf * 1.5)
            score = max(0, min(100, score))

            detail = f"BTC {btc_return:+.1f}% vs ETH {eth_return:+.1f}% (14d)"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"BTC Dominance error: {e}")
            return (50.0, "Data unavailable")

    def calculate_altcoin_season_score(self) -> tuple:
        """
        Calculate altcoin season score (alts outperform = peak greed)
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            eth = yf.Ticker("ETH-USD")
            sol = yf.Ticker("SOL-USD")

            btc_hist = btc.history(period="1mo")
            eth_hist = eth.history(period="1mo")
            sol_hist = sol.history(period="1mo")

            if len(btc_hist) < 14 or len(eth_hist) < 14 or len(sol_hist) < 14:
                raise ValueError("Insufficient data")

            # Calculate returns
            btc_return = ((btc_hist['Close'].iloc[-1] - btc_hist['Close'].iloc[-14]) / btc_hist['Close'].iloc[-14]) * 100
            eth_return = ((eth_hist['Close'].iloc[-1] - eth_hist['Close'].iloc[-14]) / eth_hist['Close'].iloc[-14]) * 100
            sol_return = ((sol_hist['Close'].iloc[-1] - sol_hist['Close'].iloc[-14]) / sol_hist['Close'].iloc[-14]) * 100

            # Average altcoin performance vs BTC
            avg_alt_return = (eth_return + sol_return) / 2
            alt_vs_btc = avg_alt_return - btc_return

            # Alts outperform = greed, BTC outperforms = fear
            score = 50 + (alt_vs_btc * 2)
            score = max(0, min(100, score))

            detail = f"Alts avg {avg_alt_return:+.1f}% vs BTC {btc_return:+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Altcoin season error: {e}")
            return (50.0, "Data unavailable")

    def calculate_market_cap_score(self) -> tuple:
        """
        Calculate market cap growth score
        Strong growth = capital inflow = greed
        Returns: (score, detail_string)
        """
        try:
            # Use BTC as proxy for total crypto market cap
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="1mo")

            if len(hist) < 14:
                raise ValueError("Insufficient data")

            # 14-day price change as proxy for market cap change
            current_price = hist['Close'].iloc[-1]
            price_14d_ago = hist['Close'].iloc[-14]
            growth = ((current_price - price_14d_ago) / price_14d_ago) * 100

            # Score: positive growth = greed
            score = 50 + (growth * 3)
            score = max(0, min(100, score))

            detail = f"Market growth: {growth:+.1f}% 14d"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Market cap error: {e}")
            return (50.0, "Data unavailable")

    def calculate_index(self):
        """
        Calculate the complete Crypto Fear & Greed Index
        Returns: Dictionary with score, label, components
        """
        # Define weights (total must equal 1.0)
        weights = {
            'momentum': 0.25,
            'volatility': 0.15,
            'volume': 0.15,
            'btc_dominance': 0.15,
            'altcoin_season': 0.15,
            'market_cap': 0.15
        }

        # Calculate each component
        print("\nCalculating Crypto Fear & Greed Index...")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"Momentum: {momentum_score} - {momentum_detail}")

        volatility_score, volatility_detail = self.calculate_volatility_score()
        print(f"Volatility: {volatility_score} - {volatility_detail}")

        volume_score, volume_detail = self.calculate_volume_score()
        print(f"Volume: {volume_score} - {volume_detail}")

        dominance_score, dominance_detail = self.calculate_btc_dominance_score()
        print(f"BTC Dominance: {dominance_score} - {dominance_detail}")

        altseason_score, altseason_detail = self.calculate_altcoin_season_score()
        print(f"Altcoin Season: {altseason_score} - {altseason_detail}")

        mcap_score, mcap_detail = self.calculate_market_cap_score()
        print(f"Market Cap: {mcap_score} - {mcap_detail}")

        # Store components
        self.components = {
            'momentum': {'score': momentum_score, 'weight': weights['momentum'], 'detail': momentum_detail},
            'volatility': {'score': volatility_score, 'weight': weights['volatility'], 'detail': volatility_detail},
            'volume': {'score': volume_score, 'weight': weights['volume'], 'detail': volume_detail},
            'btc_dominance': {'score': dominance_score, 'weight': weights['btc_dominance'], 'detail': dominance_detail},
            'altcoin_season': {'score': altseason_score, 'weight': weights['altcoin_season'], 'detail': altseason_detail},
            'market_cap': {'score': mcap_score, 'weight': weights['market_cap'], 'detail': mcap_detail}
        }

        # Calculate weighted average
        total_score = sum(
            self.components[key]['score'] * self.components[key]['weight']
            for key in self.components
        )

        self.score = round(total_score, 1)

        # Determine label
        if self.score <= 25:
            self.label = "Extreme Fear"
        elif self.score <= 45:
            self.label = "Fear"
        elif self.score <= 55:
            self.label = "Neutral"
        elif self.score <= 75:
            self.label = "Greed"
        else:
            self.label = "Extreme Greed"

        print(f"\n{'='*50}")
        print(f"CRYPTO FEAR & GREED INDEX: {self.score} - {self.label}")
        print(f"{'='*50}\n")

        return self.get_result()

    def get_result(self):
        """Get the result as a dictionary"""
        return {
            'score': self.score,
            'label': self.label,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'components': self.components
        }

    def calculate_simple_historical_score(self, target_date: datetime) -> float:
        """
        Calculate a simplified historical score for a past date
        Uses only price-based components that have reliable historical data

        Args:
            target_date: The date to calculate the score for

        Returns:
            Historical score (0-100)
        """
        try:
            print(f"  Calculating for {target_date.strftime('%Y-%m-%d')}...", end=" ")

            # Fetch historical data up to target date
            end_date = target_date
            start_date = target_date - timedelta(days=90)

            # Get historical data
            btc = yf.Ticker("BTC-USD")
            eth = yf.Ticker("ETH-USD")
            sol = yf.Ticker("SOL-USD")

            btc_hist = btc.history(start=start_date, end=end_date + timedelta(days=1))
            eth_hist = eth.history(start=start_date, end=end_date + timedelta(days=1))
            sol_hist = sol.history(start=start_date, end=end_date + timedelta(days=1))

            if len(btc_hist) < 20:
                print("insufficient data")
                return 50.0

            # Calculate Momentum (30% weight)
            close_prices = btc_hist['Close']
            if len(close_prices) >= 50:
                ma50 = close_prices.rolling(window=50).mean().iloc[-1]
                current_price = close_prices.iloc[-1]

                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]

                rsi_score = current_rsi
                ma_score = 75 if current_price > ma50 else 25
                momentum_score = (rsi_score * 0.6) + (ma_score * 0.4)
                momentum_score = max(0, min(100, momentum_score))
            else:
                momentum_score = 50

            # Calculate Market Cap Growth (40% weight)
            if len(btc_hist) >= 14:
                current_price = btc_hist['Close'].iloc[-1]
                price_14d_ago = btc_hist['Close'].iloc[-14]
                growth = ((current_price - price_14d_ago) / price_14d_ago) * 100
                mcap_score = 50 + (growth * 3)
                mcap_score = max(0, min(100, mcap_score))
            else:
                mcap_score = 50

            # Calculate Altcoin Season (30% weight)
            if len(eth_hist) >= 14 and len(sol_hist) >= 14:
                btc_return = ((btc_hist['Close'].iloc[-1] - btc_hist['Close'].iloc[-14]) / btc_hist['Close'].iloc[-14]) * 100
                eth_return = ((eth_hist['Close'].iloc[-1] - eth_hist['Close'].iloc[-14]) / eth_hist['Close'].iloc[-14]) * 100
                sol_return = ((sol_hist['Close'].iloc[-1] - sol_hist['Close'].iloc[-14]) / sol_hist['Close'].iloc[-14]) * 100

                avg_alt_return = (eth_return + sol_return) / 2
                alt_vs_btc = avg_alt_return - btc_return
                altseason_score = 50 + (alt_vs_btc * 2)
                altseason_score = max(0, min(100, altseason_score))
            else:
                altseason_score = 50

            # Weighted average (simplified for historical calculation)
            total_score = (
                momentum_score * 0.30 +
                mcap_score * 0.40 +
                altseason_score * 0.30
            )

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1)

        except Exception as e:
            print(f"error: {e}")
            return 50.0

    def save_to_file(self, filepath: str = 'data/crypto-fear-greed.json', force_rebuild: bool = False):
        """
        Save the index to JSON file with incremental history updates

        Args:
            filepath: Path to the JSON file
            force_rebuild: If True, regenerate all 365 days of history (slow)
        """
        try:
            today = datetime.utcnow().date()
            today_str = today.strftime('%Y-%m-%d')

            # Load existing history if available
            existing_history = []
            if os.path.exists(filepath) and not force_rebuild:
                try:
                    with open(filepath, 'r') as f:
                        existing_data = json.load(f)
                        existing_history = existing_data.get('history', [])
                    print(f"📂 Loaded {len(existing_history)} existing historical records")
                except Exception as e:
                    print(f"⚠️  Could not load existing history: {e}")

            # Check if today's score already exists
            history_dict = {item['date']: item['score'] for item in existing_history}

            if force_rebuild:
                print("\n🔄 Force rebuilding 365-day history (this may take 2-3 minutes)...")
                history = []
                for i in range(364, -1, -1):
                    historical_date = today - timedelta(days=i)
                    historical_date_str = historical_date.strftime('%Y-%m-%d')

                    if i == 0:
                        score = self.score
                    else:
                        score = self.calculate_simple_historical_score(
                            datetime.combine(historical_date, datetime.min.time())
                        )

                    history.append({
                        'date': historical_date_str,
                        'score': score
                    })

                    if (i + 1) % 50 == 0:
                        print(f"  Calculated {365 - i}/365 days...")
            else:
                # Incremental update: only add today's score
                print(f"📊 Updating index for {today_str}...")

                # Update or add today's score
                history_dict[today_str] = self.score

                # Convert back to list and sort
                history = [{'date': date, 'score': score} for date, score in history_dict.items()]
                history = sorted(history, key=lambda x: x['date'], reverse=True)

                # Keep only last 365 days
                if len(history) > 365:
                    history = history[:365]
                    print(f"  Trimmed history to 365 days")

            # Sort by date descending
            history = sorted(history, key=lambda x: x['date'], reverse=True)

            # Build complete data
            result = self.get_result()
            result['history'] = history

            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"\n✅ Crypto Index saved to {filepath} with {len(history)} days of history")

        except Exception as e:
            print(f"Error saving to file: {e}")


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate Crypto Fear & Greed Index')
    parser.add_argument('--force-rebuild', action='store_true',
                        help='Force rebuild all 365 days of history (slow, 2-3 minutes)')
    args = parser.parse_args()

    # Create calculator instance
    calculator = CryptoFearGreedIndex()

    # Calculate index
    calculator.calculate_index()

    # Save to file
    calculator.save_to_file('data/crypto-fear-greed.json', force_rebuild=args.force_rebuild)


if __name__ == "__main__":
    main()
