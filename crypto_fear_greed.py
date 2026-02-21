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
        Calculate BTC momentum score based on RSI and moving averages (20% weight)
        RSI used directly (0-100 natural range) for full granularity
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

            # RSI used directly as score (natural 0-100 range)
            # RSI 13 = 13 (extreme fear), RSI 70 = 70 (greed), RSI 85 = 85 (extreme greed)
            rsi_score = max(0, min(100, current_rsi))

            # MA component
            if current_price > ma200:
                ma_score = 80 if current_price > ma50 else 60
            else:
                ma_score = 40 if current_price > ma50 else 20

            # Weighted average (60% RSI, 40% MA)
            score = (rsi_score * 0.6) + (ma_score * 0.4)
            score = max(0, min(100, score))

            detail = f"RSI: {current_rsi:.0f}, Price vs MA200: {((current_price/ma200 - 1) * 100):+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Momentum error: {e}")
            return (50.0, "Data unavailable")

    def calculate_volatility_score(self) -> tuple:
        """
        Calculate volatility score (15% weight)
        Thresholds adapted to crypto's higher natural volatility (25-80%)
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="3mo")

            if hist.empty:
                raise ValueError("No BTC data")

            # Calculate returns
            returns = hist['Close'].pct_change().dropna()

            # Current 14-day volatility (annualized %)
            vol_14d = returns.tail(14).std() * np.sqrt(365) * 100

            # Crypto-adapted thresholds:
            # vol >= 80% = extreme fear (score 0)
            # vol <= 25% = extreme greed (score 100)
            # Linear interpolation between
            if vol_14d >= 80:
                score = 0
            elif vol_14d <= 25:
                score = 100
            else:
                score = 100 - ((vol_14d - 25) / 55) * 100

            score = max(0, min(100, score))

            detail = f"Vol 14d: {vol_14d:.1f}% annualized"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Volatility error: {e}")
            return (50.0, "Data unavailable")

    def calculate_context_score(self) -> tuple:
        """
        Calculate market context score based on 30-day trend (30% weight)
        Baseline 50, full 0-100 range
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="3mo")

            if len(hist) < 30:
                raise ValueError("Insufficient data")

            current_price = hist['Close'].iloc[-1]
            price_30d_ago = hist['Close'].iloc[-30] if len(hist) >= 30 else hist['Close'].iloc[0]

            # 30-day price change
            change_30d = ((current_price - price_30d_ago) / price_30d_ago) * 100

            # Baseline 50, multiplier 1.5, cap ±50 → full 0-100 range
            # +33% in 30d = score 100, -33% = score 0
            score = 50 + max(-50, min(50, change_30d * 2.0))
            score = max(0, min(100, score))

            detail = f"30-day change: {change_30d:+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Context error: {e}")
            return (50.0, "Data unavailable")

    def calculate_btc_dominance_score(self) -> tuple:
        """
        Calculate Bitcoin Dominance score (20% weight, INVERTED)
        BTC outperforms ETH = dominance up = fear (capital fleeing alts)
        Baseline 50, full range
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

            # INVERTED: BTC outperforms = fear (capital rotation to safety)
            # Baseline 50, multiplier 3.0 → saturates at ±16.7%
            score = 50 - (relative_perf * 3.0)
            score = max(0, min(100, score))

            detail = f"BTC {btc_return:+.1f}% vs ETH {eth_return:+.1f}% (14d)"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"BTC Dominance error: {e}")
            return (50.0, "Data unavailable")

    def calculate_volume_trend_score(self) -> tuple:
        """
        Calculate volume trend score (15% weight)
        Volume is an independent signal from price — high volume during rallies = greed,
        high volume during selloffs = fear
        Returns: (score, detail_string)
        """
        try:
            btc = yf.Ticker("BTC-USD")
            hist = btc.history(period="3mo")

            if len(hist) < 30:
                raise ValueError("Insufficient data")

            # Average volume comparison
            vol_avg_30d = hist['Volume'].tail(30).mean()
            vol_avg_7d = hist['Volume'].tail(7).mean()

            if vol_avg_30d <= 0:
                return (50.0, "No volume data")

            ratio = vol_avg_7d / vol_avg_30d

            # Determine price direction over 7 days
            price_now = hist['Close'].iloc[-1]
            price_7d_ago = hist['Close'].iloc[-7]
            price_direction = 1 if price_now > price_7d_ago else -1

            # High volume + rising price = greed (people rushing to buy)
            # High volume + falling price = fear (panic selling)
            # Low volume = neutral
            score = 50 + (ratio - 1) * 50 * price_direction
            score = max(0, min(100, score))

            direction_label = "up" if price_direction > 0 else "down"
            detail = f"Vol 7d/30d: {ratio:.2f}x, price {direction_label}"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Volume trend error: {e}")
            return (50.0, "Data unavailable")

    def calculate_index(self):
        """
        Calculate the complete Crypto Fear & Greed Index v2
        Diversified signals with full 0-100 range
        Returns: Dictionary with score, label, components
        """
        # Weights (total must equal 1.0)
        weights = {
            'context': 0.30,        # 30-day trend (highest weight)
            'momentum': 0.20,       # RSI + MA position
            'dominance': 0.20,      # BTC vs ETH (inverted)
            'volume': 0.15,         # Volume trend (price-independent)
            'volatility': 0.15      # Annualized volatility
        }

        # Calculate each component
        print("\nCalculating Crypto Fear & Greed Index v2...")

        context_score, context_detail = self.calculate_context_score()
        print(f"  Context (30%):    {context_score:>5.1f} - {context_detail}")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"  Momentum (20%):   {momentum_score:>5.1f} - {momentum_detail}")

        dominance_score, dominance_detail = self.calculate_btc_dominance_score()
        print(f"  Dominance (20%):  {dominance_score:>5.1f} - {dominance_detail}")

        volume_score, volume_detail = self.calculate_volume_trend_score()
        print(f"  Volume (15%):     {volume_score:>5.1f} - {volume_detail}")

        volatility_score, volatility_detail = self.calculate_volatility_score()
        print(f"  Volatility (15%): {volatility_score:>5.1f} - {volatility_detail}")

        # Store components
        self.components = {
            'context': {'score': context_score, 'weight': weights['context'], 'detail': context_detail},
            'momentum': {'score': momentum_score, 'weight': weights['momentum'], 'detail': momentum_detail},
            'dominance': {'score': dominance_score, 'weight': weights['dominance'], 'detail': dominance_detail},
            'volume': {'score': volume_score, 'weight': weights['volume'], 'detail': volume_detail},
            'volatility': {'score': volatility_score, 'weight': weights['volatility'], 'detail': volatility_detail}
        }

        # Calculate weighted average
        total_score = sum(
            self.components[key]['score'] * self.components[key]['weight']
            for key in self.components
        )

        self.score = round(total_score, 1)

        # Determine label from rounded integer (matches displayed value)
        rounded = round(self.score)
        if rounded <= 25:
            self.label = "Extreme Fear"
        elif rounded <= 45:
            self.label = "Fear"
        elif rounded <= 55:
            self.label = "Neutral"
        elif rounded <= 75:
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

    def calculate_simple_historical_score(self, target_date: datetime) -> tuple:
        """
        Calculate COMPLETE historical score for a past date
        Uses 5 components: Context, Momentum, Dominance, Volume, Volatility

        Args:
            target_date: The date to calculate the score for

        Returns:
            Tuple of (score 0-100, price of BTC-USD)
        """
        try:
            print(f"  Calculating for {target_date.strftime('%Y-%m-%d')}...", end=" ")

            # Fetch historical data up to target date
            end_date = target_date
            start_date = target_date - timedelta(days=250)  # Extended for MA200

            # Get historical data for ALL components
            btc = yf.Ticker("BTC-USD")
            eth = yf.Ticker("ETH-USD")

            btc_hist = btc.history(start=start_date, end=end_date + timedelta(days=1))
            eth_hist = eth.history(start=start_date, end=end_date + timedelta(days=1))

            if len(btc_hist) < 20:
                print("insufficient data")
                return 50.0, None

            # 1. CONTEXT (30% weight) - 30-day trend
            if len(btc_hist) >= 30:
                current_price = btc_hist['Close'].iloc[-1]
                price_30d_ago = btc_hist['Close'].iloc[-30]
                change_30d = ((current_price - price_30d_ago) / price_30d_ago) * 100

                context_score = 50 + max(-50, min(50, change_30d * 2.0))
                context_score = max(0, min(100, context_score))
            else:
                context_score = 50.0

            # 2. MOMENTUM (20% weight) - RSI + MA position
            close_prices = btc_hist['Close']
            if len(close_prices) >= 200:
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]

                ma50 = close_prices.rolling(window=50).mean().iloc[-1]
                ma200 = close_prices.rolling(window=200).mean().iloc[-1]
                current_price = close_prices.iloc[-1]

                # RSI used directly (natural 0-100 range)
                rsi_score = max(0, min(100, current_rsi))
                if current_price > ma200:
                    ma_score = 80 if current_price > ma50 else 60
                else:
                    ma_score = 40 if current_price > ma50 else 20

                momentum_score = (rsi_score * 0.6) + (ma_score * 0.4)
                momentum_score = max(0, min(100, momentum_score))
            else:
                momentum_score = 50.0

            # 3. DOMINANCE (20% weight) - BTC vs ETH (inverted)
            if len(btc_hist) >= 14 and len(eth_hist) >= 14:
                btc_return = ((btc_hist['Close'].iloc[-1] - btc_hist['Close'].iloc[-14]) / btc_hist['Close'].iloc[-14]) * 100
                eth_return = ((eth_hist['Close'].iloc[-1] - eth_hist['Close'].iloc[-14]) / eth_hist['Close'].iloc[-14]) * 100
                relative_perf = btc_return - eth_return

                dominance_score = 50 - (relative_perf * 3.0)
                dominance_score = max(0, min(100, dominance_score))
            else:
                dominance_score = 50.0

            # 4. VOLUME TREND (15% weight) - Volume direction
            if len(btc_hist) >= 30 and 'Volume' in btc_hist.columns:
                vol_avg_30d = btc_hist['Volume'].tail(30).mean()
                vol_avg_7d = btc_hist['Volume'].tail(7).mean()

                if vol_avg_30d > 0:
                    ratio = vol_avg_7d / vol_avg_30d
                    price_now = btc_hist['Close'].iloc[-1]
                    price_7d_ago = btc_hist['Close'].iloc[-7]
                    price_direction = 1 if price_now > price_7d_ago else -1

                    volume_score = 50 + (ratio - 1) * 50 * price_direction
                    volume_score = max(0, min(100, volume_score))
                else:
                    volume_score = 50.0
            else:
                volume_score = 50.0

            # 5. VOLATILITY (15% weight) - 14-day annualized volatility
            returns = btc_hist['Close'].pct_change().dropna()
            if len(returns) >= 14:
                vol_14d = returns.tail(14).std() * np.sqrt(365) * 100

                if vol_14d >= 80:
                    volatility_score = 0
                elif vol_14d <= 25:
                    volatility_score = 100
                else:
                    volatility_score = 100 - ((vol_14d - 25) / 55) * 100

                volatility_score = max(0, min(100, volatility_score))
            else:
                volatility_score = 50.0

            # Weighted average (5 components)
            total_score = (
                context_score * 0.30 +
                momentum_score * 0.20 +
                dominance_score * 0.20 +
                volume_score * 0.15 +
                volatility_score * 0.15
            )

            # Get BTC price for this date
            btc_price = round(float(btc_hist['Close'].iloc[-1]), 2) if len(btc_hist) > 0 else None

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1), btc_price

        except Exception as e:
            print(f"error: {e}")
            return 50.0, None

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
            history_dict = {item['date']: {'score': item['score'], 'price': item.get('price')} for item in existing_history}

            if force_rebuild:
                print("\n🔄 Force rebuilding 365-day history (this may take 2-3 minutes)...")
                history = []
                for i in range(364, -1, -1):
                    historical_date = today - timedelta(days=i)
                    historical_date_str = historical_date.strftime('%Y-%m-%d')

                    if i == 0:
                        if not self.score:
                            self.calculate_index()
                        score = self.score
                        # Fetch today's BTC price
                        try:
                            btc = yf.Ticker("BTC-USD")
                            ph = btc.history(period="5d")
                            price = round(float(ph['Close'].iloc[-1]), 2)
                        except Exception:
                            price = None
                    else:
                        score, price = self.calculate_simple_historical_score(
                            datetime.combine(historical_date, datetime.min.time())
                        )

                    entry = {'date': historical_date_str, 'score': score}
                    if price is not None:
                        entry['price'] = price
                    history.append(entry)

                    if (i + 1) % 50 == 0:
                        print(f"  Calculated {365 - i}/365 days...")
            else:
                # Incremental update: only add today's score
                print(f"📊 Updating index for {today_str}...")

                # Fetch today's BTC price
                try:
                    btc = yf.Ticker("BTC-USD")
                    ph = btc.history(period="5d")
                    today_price = round(float(ph['Close'].iloc[-1]), 2)
                except Exception:
                    today_price = None

                # Update or add today's score
                history_dict[today_str] = {'score': self.score, 'price': today_price}

                # Convert back to list and sort
                history = []
                for date, data in history_dict.items():
                    entry = {'date': date, 'score': data['score']}
                    if data.get('price') is not None:
                        entry['price'] = data['price']
                    history.append(entry)
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
