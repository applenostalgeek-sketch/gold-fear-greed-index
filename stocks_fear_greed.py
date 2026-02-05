#!/usr/bin/env python3
"""
Stocks Fear & Greed Index Calculator
Transparent, open-source sentiment indicator for US stocks
Based on 7 public data sources, inspired by CNN F&G but fully transparent
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time


class StocksFearGreedIndex:
    def __init__(self):
        self.score = None
        self.label = None
        self.components = {}

    def calculate_momentum_score(self) -> tuple:
        """
        Calculate SPY momentum score based on RSI and moving averages
        Returns: (score, detail_string)
        """
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1y")

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

    def calculate_vix_score(self) -> tuple:
        """
        Calculate VIX score (INVERTED - high VIX = fear = low score)
        Returns: (score, detail_string)
        """
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="3mo")

            if hist.empty:
                raise ValueError("No VIX data")

            current_vix = hist['Close'].iloc[-1]
            avg_vix = hist['Close'].mean()

            # VIX interpretation (inverted):
            # VIX < 12: Extreme complacency (greed) = 80+
            # VIX 12-20: Normal (neutral) = 40-70
            # VIX 20-30: Elevated (fear) = 20-40
            # VIX > 30: Panic (extreme fear) = 0-20

            if current_vix < 12:
                score = 85
            elif current_vix < 15:
                score = 70
            elif current_vix < 20:
                score = 55
            elif current_vix < 25:
                score = 40
            elif current_vix < 30:
                score = 25
            else:
                score = 10

            detail = f"VIX: {current_vix:.1f} vs avg: {avg_vix:.1f}"

            return (float(score), detail)

        except Exception as e:
            print(f"VIX error: {e}")
            return (50.0, "Data unavailable")

    def calculate_market_breadth_score(self) -> tuple:
        """
        Calculate market breadth using RSP (equal weight) vs SPY (cap weight)
        When equal-weight outperforms cap-weight = broader participation = greed
        Returns: (score, detail_string)
        """
        try:
            spy = yf.Ticker("SPY")
            rsp = yf.Ticker("RSP")  # Equal weight S&P 500

            spy_hist = spy.history(period="1mo")
            rsp_hist = rsp.history(period="1mo")

            if len(spy_hist) < 14 or len(rsp_hist) < 14:
                raise ValueError("Insufficient data")

            # 14-day performance
            spy_return = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-14]) / spy_hist['Close'].iloc[-14]) * 100
            rsp_return = ((rsp_hist['Close'].iloc[-1] - rsp_hist['Close'].iloc[-14]) / rsp_hist['Close'].iloc[-14]) * 100

            # If equal weight outperforms = broader participation = higher score
            relative_perf = rsp_return - spy_return

            # Score: RSP outperforms = greed, SPY outperforms = fear (large caps defensive)
            score = 50 + (relative_perf * 20)
            score = max(0, min(100, score))

            detail = f"RSP {rsp_return:+.1f}% vs SPY {spy_return:+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Market breadth error: {e}")
            return (50.0, "Data unavailable")

    def calculate_junk_bond_score(self) -> tuple:
        """
        Calculate high yield spread score (HYG vs TLT)
        When junk bonds outperform treasuries = risk-on = greed
        Returns: (score, detail_string)
        """
        try:
            hyg = yf.Ticker("HYG")  # High yield bonds
            tlt = yf.Ticker("TLT")  # Long-term treasuries

            hyg_hist = hyg.history(period="1mo")
            tlt_hist = tlt.history(period="1mo")

            if len(hyg_hist) < 14 or len(tlt_hist) < 14:
                raise ValueError("Insufficient data")

            # 14-day performance
            hyg_return = ((hyg_hist['Close'].iloc[-1] - hyg_hist['Close'].iloc[-14]) / hyg_hist['Close'].iloc[-14]) * 100
            tlt_return = ((tlt_hist['Close'].iloc[-1] - tlt_hist['Close'].iloc[-14]) / tlt_hist['Close'].iloc[-14]) * 100

            # If HYG outperforms TLT = risk-on = greed
            spread = hyg_return - tlt_return

            score = 50 + (spread * 10)
            score = max(0, min(100, score))

            detail = f"HYG {hyg_return:+.1f}% vs TLT {tlt_return:+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Junk bond error: {e}")
            return (50.0, "Data unavailable")

    def calculate_safe_haven_score(self) -> tuple:
        """
        Calculate safe haven demand (TLT flows)
        When treasuries surge = fear, when they drop = greed
        Returns: (score, detail_string)
        """
        try:
            tlt = yf.Ticker("TLT")
            hist = tlt.history(period="3mo")

            if len(hist) < 30:
                raise ValueError("Insufficient data")

            # Compare current to 30-day average
            current_price = hist['Close'].iloc[-1]
            ma30 = hist['Close'].rolling(window=30).mean().iloc[-1]

            # 14-day momentum
            price_14d_ago = hist['Close'].iloc[-14]
            momentum_14d = ((current_price - price_14d_ago) / price_14d_ago) * 100

            # Score: TLT down = greed (risk-on), TLT up = fear (risk-off)
            # Inverted relationship
            score = 50 - (momentum_14d * 5)
            score = max(0, min(100, score))

            detail = f"TLT {momentum_14d:+.1f}% 14d"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Safe haven error: {e}")
            return (50.0, "Data unavailable")

    def calculate_price_strength_score(self) -> tuple:
        """
        Calculate SPY price strength (14-day momentum)
        Returns: (score, detail_string)
        """
        try:
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1mo")

            if len(hist) < 14:
                raise ValueError("Insufficient data")

            current_price = hist['Close'].iloc[-1]
            price_14d_ago = hist['Close'].iloc[-14]

            momentum = ((current_price - price_14d_ago) / price_14d_ago) * 100

            # Score: positive momentum = greed, negative = fear
            score = 50 + (momentum * 5)
            score = max(0, min(100, score))

            detail = f"SPY {momentum:+.1f}% 14d"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Price strength error: {e}")
            return (50.0, "Data unavailable")

    def calculate_sector_rotation_score(self) -> tuple:
        """
        Calculate sector rotation score (Tech vs Defensive)
        QQQ (tech-heavy Nasdaq) vs XLP (Consumer Staples defensive)
        High score = Tech outperforming (Risk-On)
        Low score = Defensive outperforming (Risk-Off)
        Returns: (score, detail_string)
        """
        try:
            qqq = yf.Ticker("QQQ")  # Nasdaq-100 (tech-heavy)
            xlp = yf.Ticker("XLP")  # Consumer Staples (defensive)

            qqq_hist = qqq.history(period="1mo")
            xlp_hist = xlp.history(period="1mo")

            if len(qqq_hist) < 14 or len(xlp_hist) < 14:
                raise ValueError("Insufficient data")

            # 14-day performance
            qqq_return = ((qqq_hist['Close'].iloc[-1] - qqq_hist['Close'].iloc[-14]) / qqq_hist['Close'].iloc[-14]) * 100
            xlp_return = ((xlp_hist['Close'].iloc[-1] - xlp_hist['Close'].iloc[-14]) / xlp_hist['Close'].iloc[-14]) * 100

            # Relative outperformance
            # QQQ outperforms = Risk-On (tech leadership) = high score
            # XLP outperforms = Risk-Off (defensive rotation) = low score
            outperformance = qqq_return - xlp_return

            # Score calculation
            # +5% outperformance = 75 (strong risk-on)
            # 0% = 50 (neutral)
            # -5% underperformance = 25 (strong risk-off)
            score = 50 + (outperformance * 5)
            score = max(0, min(100, score))

            detail = f"QQQ {qqq_return:+.1f}% vs XLP {xlp_return:+.1f}%"

            return (round(score, 1), detail)

        except Exception as e:
            print(f"Sector rotation error: {e}")
            return (50.0, "Data unavailable")

    def calculate_index(self):
        """
        Calculate the complete Stocks Fear & Greed Index
        Returns: Dictionary with score, label, components
        """
        # Define weights (total must equal 1.0)
        weights = {
            'momentum': 0.20,           # Reduced from 0.25
            'vix': 0.20,                # Unchanged
            'market_breadth': 0.15,     # Unchanged
            'sector_rotation': 0.15,    # NEW: Tech vs Defensive rotation
            'junk_bonds': 0.15,         # Unchanged
            'safe_haven': 0.10,         # Reduced from 0.15
            'price_strength': 0.05      # Reduced from 0.10
        }

        # Calculate each component
        print("\nCalculating Stocks Fear & Greed Index...")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"Momentum: {momentum_score} - {momentum_detail}")

        vix_score, vix_detail = self.calculate_vix_score()
        print(f"VIX: {vix_score} - {vix_detail}")

        breadth_score, breadth_detail = self.calculate_market_breadth_score()
        print(f"Market Breadth: {breadth_score} - {breadth_detail}")

        rotation_score, rotation_detail = self.calculate_sector_rotation_score()
        print(f"Sector Rotation: {rotation_score} - {rotation_detail}")

        junk_score, junk_detail = self.calculate_junk_bond_score()
        print(f"Junk Bonds: {junk_score} - {junk_detail}")

        haven_score, haven_detail = self.calculate_safe_haven_score()
        print(f"Safe Haven: {haven_score} - {haven_detail}")

        strength_score, strength_detail = self.calculate_price_strength_score()
        print(f"Price Strength: {strength_score} - {strength_detail}")

        # Store components
        self.components = {
            'momentum': {'score': momentum_score, 'weight': weights['momentum'], 'detail': momentum_detail},
            'vix': {'score': vix_score, 'weight': weights['vix'], 'detail': vix_detail},
            'market_breadth': {'score': breadth_score, 'weight': weights['market_breadth'], 'detail': breadth_detail},
            'sector_rotation': {'score': rotation_score, 'weight': weights['sector_rotation'], 'detail': rotation_detail},
            'junk_bonds': {'score': junk_score, 'weight': weights['junk_bonds'], 'detail': junk_detail},
            'safe_haven': {'score': haven_score, 'weight': weights['safe_haven'], 'detail': haven_detail},
            'price_strength': {'score': strength_score, 'weight': weights['price_strength'], 'detail': strength_detail}
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
        print(f"STOCKS FEAR & GREED INDEX: {self.score} - {self.label}")
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
        Calculate COMPLETE historical score for a past date
        Uses ALL 7 components with accurate weights for professional-grade historical data

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

            # Get historical data for ALL components
            spy = yf.Ticker("SPY")
            vix = yf.Ticker("^VIX")
            rsp = yf.Ticker("RSP")
            qqq = yf.Ticker("QQQ")  # For sector rotation
            xlp = yf.Ticker("XLP")  # For sector rotation
            hyg = yf.Ticker("HYG")  # For junk bonds
            tlt = yf.Ticker("TLT")  # For safe haven & junk bonds

            spy_hist = spy.history(start=start_date, end=end_date + timedelta(days=1))
            vix_hist = vix.history(start=start_date, end=end_date + timedelta(days=1))
            rsp_hist = rsp.history(start=start_date, end=end_date + timedelta(days=1))
            qqq_hist = qqq.history(start=start_date, end=end_date + timedelta(days=1))
            xlp_hist = xlp.history(start=start_date, end=end_date + timedelta(days=1))
            hyg_hist = hyg.history(start=start_date, end=end_date + timedelta(days=1))
            tlt_hist = tlt.history(start=start_date, end=end_date + timedelta(days=1))

            if len(spy_hist) < 20:
                print("insufficient data")
                return 50.0

            # 1. Calculate Momentum (20% weight)
            close_prices = spy_hist['Close']
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

            # 2. Calculate VIX (20% weight)
            if len(vix_hist) > 0:
                current_vix = vix_hist['Close'].iloc[-1]
                if current_vix < 12:
                    vix_score = 85
                elif current_vix < 15:
                    vix_score = 70
                elif current_vix < 20:
                    vix_score = 55
                elif current_vix < 25:
                    vix_score = 40
                elif current_vix < 30:
                    vix_score = 25
                else:
                    vix_score = 10
            else:
                vix_score = 50

            # 3. Calculate Market Breadth (15% weight)
            if len(rsp_hist) >= 14 and len(spy_hist) >= 14:
                spy_return = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-14]) / spy_hist['Close'].iloc[-14]) * 100
                rsp_return = ((rsp_hist['Close'].iloc[-1] - rsp_hist['Close'].iloc[-14]) / rsp_hist['Close'].iloc[-14]) * 100
                relative_perf = rsp_return - spy_return
                breadth_score = 50 + (relative_perf * 20)
                breadth_score = max(0, min(100, breadth_score))
            else:
                breadth_score = 50

            # 4. Calculate Sector Rotation (15% weight) - NEW!
            if len(qqq_hist) >= 14 and len(xlp_hist) >= 14:
                qqq_return = ((qqq_hist['Close'].iloc[-1] - qqq_hist['Close'].iloc[-14]) / qqq_hist['Close'].iloc[-14]) * 100
                xlp_return = ((xlp_hist['Close'].iloc[-1] - xlp_hist['Close'].iloc[-14]) / xlp_hist['Close'].iloc[-14]) * 100
                outperformance = qqq_return - xlp_return
                rotation_score = 50 + (outperformance * 5)
                rotation_score = max(0, min(100, rotation_score))
            else:
                rotation_score = 50

            # 5. Calculate Junk Bond Demand (15% weight)
            if len(hyg_hist) >= 14 and len(tlt_hist) >= 14:
                hyg_return = ((hyg_hist['Close'].iloc[-1] - hyg_hist['Close'].iloc[-14]) / hyg_hist['Close'].iloc[-14]) * 100
                tlt_return = ((tlt_hist['Close'].iloc[-1] - tlt_hist['Close'].iloc[-14]) / tlt_hist['Close'].iloc[-14]) * 100
                spread = hyg_return - tlt_return
                junk_score = 50 + (spread * 10)
                junk_score = max(0, min(100, junk_score))
            else:
                junk_score = 50

            # 6. Calculate Safe Haven Demand (10% weight)
            if len(tlt_hist) >= 30:
                current_tlt = tlt_hist['Close'].iloc[-1]
                if len(tlt_hist) >= 14:
                    price_14d_ago = tlt_hist['Close'].iloc[-14]
                    momentum_14d = ((current_tlt - price_14d_ago) / price_14d_ago) * 100
                    haven_score = 50 - (momentum_14d * 5)
                    haven_score = max(0, min(100, haven_score))
                else:
                    haven_score = 50
            else:
                haven_score = 50

            # 7. Calculate Price Strength (5% weight)
            if len(spy_hist) >= 14:
                current_price = spy_hist['Close'].iloc[-1]
                price_14d_ago = spy_hist['Close'].iloc[-14]
                momentum = ((current_price - price_14d_ago) / price_14d_ago) * 100
                strength_score = 50 + (momentum * 5)
                strength_score = max(0, min(100, strength_score))
            else:
                strength_score = 50

            # Weighted average with REAL weights (7 components)
            total_score = (
                momentum_score * 0.20 +
                vix_score * 0.20 +
                breadth_score * 0.15 +
                rotation_score * 0.15 +
                junk_score * 0.15 +
                haven_score * 0.10 +
                strength_score * 0.05
            )

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1)

        except Exception as e:
            print(f"error: {e}")
            return 50.0

    def save_to_file(self, filepath: str = 'data/stocks-fear-greed.json', force_rebuild: bool = False):
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

                    # Rate limiting: pause between API calls
                    if i > 0:  # Don't sleep after the last iteration
                        time.sleep(0.5)
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

            print(f"\n✅ Stocks Index saved to {filepath} with {len(history)} days of history")

        except Exception as e:
            print(f"Error saving to file: {e}")


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate Stocks Fear & Greed Index')
    parser.add_argument('--force-rebuild', action='store_true',
                        help='Force rebuild all 365 days of history (slow, 2-3 minutes)')
    args = parser.parse_args()

    # Create calculator instance
    calculator = StocksFearGreedIndex()

    # Calculate index
    calculator.calculate_index()

    # Save to file
    calculator.save_to_file('data/stocks-fear-greed.json', force_rebuild=args.force_rebuild)


if __name__ == "__main__":
    main()
