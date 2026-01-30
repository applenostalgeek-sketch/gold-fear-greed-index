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

    def calculate_index(self):
        """
        Calculate the complete Stocks Fear & Greed Index
        Returns: Dictionary with score, label, components
        """
        # Define weights (total must equal 1.0)
        weights = {
            'momentum': 0.25,
            'vix': 0.20,
            'market_breadth': 0.15,
            'junk_bonds': 0.15,
            'safe_haven': 0.15,
            'price_strength': 0.10
        }

        # Calculate each component
        print("\nCalculating Stocks Fear & Greed Index...")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"Momentum: {momentum_score} - {momentum_detail}")

        vix_score, vix_detail = self.calculate_vix_score()
        print(f"VIX: {vix_score} - {vix_detail}")

        breadth_score, breadth_detail = self.calculate_market_breadth_score()
        print(f"Market Breadth: {breadth_score} - {breadth_detail}")

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

    def save_to_file(self, filepath: str = 'data/stocks-fear-greed.json'):
        """
        Save the index to JSON file
        Args:
            filepath: Path to the JSON file
        """
        try:
            # Build data
            result = self.get_result()

            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"\n✅ Stocks Index saved to {filepath}")

        except Exception as e:
            print(f"Error saving to file: {e}")


def main():
    """Main execution function"""
    # Create calculator instance
    calculator = StocksFearGreedIndex()

    # Calculate index
    calculator.calculate_index()

    # Save to file
    calculator.save_to_file('data/stocks-fear-greed.json')


if __name__ == "__main__":
    main()
