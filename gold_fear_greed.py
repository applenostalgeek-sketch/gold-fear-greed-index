#!/usr/bin/env python3
"""
Gold Fear & Greed Index Calculator
Calculates a sentiment index for gold market (0-100) based on 6 components
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import requests
import os
from typing import Dict, Tuple, Optional


class GoldFearGreedIndex:
    """Main class to calculate the Gold Fear & Greed Index"""

    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize the calculator

        Args:
            fred_api_key: FRED API key for real rates data (optional)
        """
        self.fred_api_key = fred_api_key or os.environ.get('FRED_API_KEY')
        self.components = {}
        self.score = 0
        self.label = ""

    def calculate_volatility_score(self) -> Tuple[float, str]:
        """
        Calculate volatility component (20% weight)
        Compares current 14-day volatility to 30-day average

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            # Fetch gold data (XAU/USD)
            gold = yf.Ticker("GC=F")  # Gold Futures
            hist = gold.history(period="3mo")

            if hist.empty:
                raise ValueError("No gold price data available")

            # Calculate returns
            returns = hist['Close'].pct_change().dropna()

            # Current 14-day volatility
            current_vol = returns.tail(14).std() * np.sqrt(252) * 100  # Annualized %

            # 30-day average volatility
            vol_30d = returns.tail(30).std() * np.sqrt(252) * 100

            # Score: lower volatility = higher score (less fear)
            # If current vol < average: greed, if higher: fear
            ratio = current_vol / vol_30d if vol_30d > 0 else 1.0

            # Normalize: ratio of 0.5 = score 75, ratio of 1.5 = score 25
            score = 50 + (1 - ratio) * 50
            score = max(0, min(100, score))

            detail = f"Vol 14j: {current_vol:.1f}% vs moy 30j: {vol_30d:.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating volatility: {e}")
            return 50.0, "Data unavailable"

    def calculate_momentum_score(self) -> Tuple[float, str]:
        """
        Calculate momentum component (25% weight)
        Based on price vs MA50/MA200 and RSI

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            gold = yf.Ticker("GC=F")
            hist = gold.history(period="1y")

            if len(hist) < 200:
                raise ValueError("Insufficient data for momentum calculation")

            close_prices = hist['Close']
            current_price = close_prices.iloc[-1]

            # Moving averages
            ma50 = close_prices.rolling(window=50).mean().iloc[-1]
            ma200 = close_prices.rolling(window=200).mean().iloc[-1]

            # RSI calculation
            delta = close_prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            # Scoring
            ma_score = 0
            if current_price > ma50:
                ma_score += 40
            if current_price > ma200:
                ma_score += 30

            # RSI contribution (30 points)
            # RSI > 70 = overbought (greed), RSI < 30 = oversold (fear)
            rsi_score = current_rsi * 0.3  # Simple normalization

            total_score = ma_score + rsi_score

            ma_status = "Prix > MM50" if current_price > ma50 else "Prix < MM50"
            detail = f"RSI: {current_rsi:.0f}, {ma_status}"

            return total_score, detail

        except Exception as e:
            print(f"Error calculating momentum: {e}")
            return 50.0, "Data unavailable"

    def calculate_gold_vs_spy_score(self) -> Tuple[float, str]:
        """
        Calculate Gold vs S&P500 ratio (15% weight)
        Compares 14-day performance

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            gold = yf.Ticker("GC=F")
            spy = yf.Ticker("SPY")

            gold_hist = gold.history(period="1mo")
            spy_hist = spy.history(period="1mo")

            if len(gold_hist) < 14 or len(spy_hist) < 14:
                raise ValueError("Insufficient data")

            # 14-day returns
            gold_return = (gold_hist['Close'].iloc[-1] / gold_hist['Close'].iloc[-14] - 1) * 100
            spy_return = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-14] - 1) * 100

            # If gold outperforms stocks = greed for gold (everyone wants gold) = higher score
            # If stocks outperform gold = fear for gold (nobody wants gold) = lower score
            relative_perf = gold_return - spy_return

            # Normalize: +10% difference = score 100, -10% = score 0
            score = 50 + (relative_perf * 2.5)
            score = max(0, min(100, score))

            detail = f"Gold {gold_return:+.1f}% vs SPY {spy_return:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating gold vs SPY: {e}")
            return 50.0, "Data unavailable"

    def calculate_etf_flows_score(self) -> Tuple[float, str]:
        """
        Calculate ETF flows component (20% weight)
        Based on GLD (SPDR Gold Trust) holdings change

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            gld = yf.Ticker("GLD")

            # Get shares outstanding (proxy for holdings)
            # Note: yfinance doesn't provide direct holdings data
            # We'll use volume and price trends as proxy
            hist = gld.history(period="1mo")

            if len(hist) < 14:
                raise ValueError("Insufficient GLD data")

            # Calculate average volume trend
            recent_vol = hist['Volume'].tail(7).mean()
            previous_vol = hist['Volume'].iloc[-14:-7].mean()

            # Calculate price trend (as proxy for holdings interest)
            recent_price_change = (hist['Close'].iloc[-1] / hist['Close'].iloc[-14] - 1) * 100

            # Score: increasing volume + price = greed, decreasing = fear
            vol_change = (recent_vol / previous_vol - 1) * 100 if previous_vol > 0 else 0

            # Combine volume and price trends
            score = 50 + (vol_change * 2) + (recent_price_change * 2)
            score = max(0, min(100, score))

            detail = f"GLD volume {vol_change:+.1f}%, price {recent_price_change:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating ETF flows: {e}")
            return 50.0, "Data unavailable"

    def calculate_vix_score(self) -> Tuple[float, str]:
        """
        Calculate VIX component (10% weight)
        High VIX = market fear = people buy gold = greed for gold = high score
        Low VIX = market confidence = less gold demand = fear for gold = low score

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="3mo")

            if hist.empty:
                raise ValueError("No VIX data available")

            current_vix = hist['Close'].iloc[-1]
            avg_vix = hist['Close'].mean()

            # Score: higher VIX = higher score (more demand for gold as safe haven)
            # VIX at 10 = 0, VIX at 40 = 100
            score = (current_vix - 10) * 3.33
            score = max(0, min(100, score))

            detail = f"VIX: {current_vix:.1f} vs avg: {avg_vix:.1f}"

            return score, detail

        except Exception as e:
            print(f"Error calculating VIX: {e}")
            return 50.0, "Data unavailable"

    def calculate_real_rates_score(self) -> Tuple[float, str]:
        """
        Calculate real rates component (10% weight)
        Based on 10Y TIPS yields via FRED API

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("Warning: No FRED API key provided")
                return 50.0, "API key required"

            # FRED series for 10Y TIPS
            url = f"https://api.stlouisfed.org/fred/series/observations"
            params = {
                'series_id': 'DFII10',  # 10-Year Treasury Inflation-Indexed Security
                'api_key': self.fred_api_key,
                'file_type': 'json',
                'sort_order': 'desc',
                'limit': 30
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'observations' not in data or len(data['observations']) == 0:
                raise ValueError("No TIPS data available")

            # Get latest value
            latest_obs = data['observations'][0]
            tips_rate = float(latest_obs['value'])

            # Calculate average
            valid_obs = [float(obs['value']) for obs in data['observations']
                        if obs['value'] != '.']
            avg_tips = np.mean(valid_obs) if valid_obs else tips_rate

            # Score: lower real rates = higher gold appeal = higher score
            # Real rate at -1% = 100, at 3% = 0
            score = 75 - (tips_rate * 18.75)
            score = max(0, min(100, score))

            detail = f"TIPS 10Y: {tips_rate:.2f}% (moy: {avg_tips:.2f}%)"

            return score, detail

        except Exception as e:
            print(f"Error calculating real rates: {e}")
            return 50.0, "Data unavailable"

    def calculate_index(self) -> Dict:
        """
        Calculate the complete Gold Fear & Greed Index

        Returns:
            Dictionary with score, label, components, and history
        """
        # Define weights
        weights = {
            'volatility': 0.20,
            'momentum': 0.25,
            'gold_vs_spy': 0.15,
            'etf_flows': 0.20,
            'vix': 0.10,
            'real_rates': 0.10
        }

        # Calculate each component
        print("Calculating Gold Fear & Greed Index...")

        vol_score, vol_detail = self.calculate_volatility_score()
        print(f"Volatility: {vol_score:.1f} - {vol_detail}")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"Momentum: {momentum_score:.1f} - {momentum_detail}")

        gold_spy_score, gold_spy_detail = self.calculate_gold_vs_spy_score()
        print(f"Gold vs SPY: {gold_spy_score:.1f} - {gold_spy_detail}")

        etf_score, etf_detail = self.calculate_etf_flows_score()
        print(f"ETF Flows: {etf_score:.1f} - {etf_detail}")

        vix_score, vix_detail = self.calculate_vix_score()
        print(f"VIX: {vix_score:.1f} - {vix_detail}")

        real_rates_score, real_rates_detail = self.calculate_real_rates_score()
        print(f"Real Rates: {real_rates_score:.1f} - {real_rates_detail}")

        # Calculate weighted average
        total_score = (
            vol_score * weights['volatility'] +
            momentum_score * weights['momentum'] +
            gold_spy_score * weights['gold_vs_spy'] +
            etf_score * weights['etf_flows'] +
            vix_score * weights['vix'] +
            real_rates_score * weights['real_rates']
        )

        # Determine label
        if total_score <= 25:
            label = "Extreme Fear"
        elif total_score <= 45:
            label = "Fear"
        elif total_score <= 55:
            label = "Neutral"
        elif total_score <= 75:
            label = "Greed"
        else:
            label = "Extreme Greed"

        # Build components dictionary
        components = {
            'volatility': {
                'score': round(vol_score, 1),
                'weight': weights['volatility'],
                'detail': vol_detail
            },
            'momentum': {
                'score': round(momentum_score, 1),
                'weight': weights['momentum'],
                'detail': momentum_detail
            },
            'gold_vs_spy': {
                'score': round(gold_spy_score, 1),
                'weight': weights['gold_vs_spy'],
                'detail': gold_spy_detail
            },
            'etf_flows': {
                'score': round(etf_score, 1),
                'weight': weights['etf_flows'],
                'detail': etf_detail
            },
            'vix': {
                'score': round(vix_score, 1),
                'weight': weights['vix'],
                'detail': vix_detail
            },
            'real_rates': {
                'score': round(real_rates_score, 1),
                'weight': weights['real_rates'],
                'detail': real_rates_detail
            }
        }

        self.score = round(total_score, 1)
        self.label = label
        self.components = components

        print(f"\n{'='*50}")
        print(f"GOLD FEAR & GREED INDEX: {self.score} - {self.label}")
        print(f"{'='*50}\n")

        return self.get_result()

    def get_result(self) -> Dict:
        """
        Get the result in the expected JSON format

        Returns:
            Dictionary with complete index data
        """
        return {
            'score': self.score,
            'label': self.label,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'components': self.components
        }

    def save_to_file(self, filepath: str = 'data/gold-fear-greed.json'):
        """
        Save the index to JSON file and maintain history

        Args:
            filepath: Path to the JSON file
        """
        try:
            # Load existing data if it exists
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    existing_data = json.load(f)
                    history = existing_data.get('history', [])
            else:
                history = []

            # Add current score to history
            today = datetime.utcnow().strftime('%Y-%m-%d')

            # Update history (keep last 30 days)
            history = [h for h in history if h['date'] != today]  # Remove today if exists
            history.append({
                'date': today,
                'score': self.score
            })
            history = sorted(history, key=lambda x: x['date'], reverse=True)[:30]

            # Build complete data
            result = self.get_result()
            result['history'] = history

            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(result, f, indent=2)

            print(f"Index saved to {filepath}")

        except Exception as e:
            print(f"Error saving to file: {e}")


def main():
    """Main execution function"""
    # Get FRED API key from environment
    fred_key = os.environ.get('FRED_API_KEY')

    if not fred_key:
        print("Warning: FRED_API_KEY not found in environment variables")
        print("Real rates component will return neutral score")
        print("Get a free API key at: https://fred.stlouisfed.org/docs/api/api_key.html\n")

    # Create calculator instance
    calculator = GoldFearGreedIndex(fred_api_key=fred_key)

    # Calculate index
    calculator.calculate_index()

    # Save to file
    calculator.save_to_file('data/gold-fear-greed.json')


if __name__ == "__main__":
    main()
