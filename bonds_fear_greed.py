#!/usr/bin/env python3
"""
Bonds Fear & Greed Index Calculator
Calculates a sentiment index for bond market (0-100) based on 7 components
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import requests
import os
from typing import Dict, Tuple, Optional


class BondsFearGreedIndex:
    """Main class to calculate the Bonds Fear & Greed Index"""

    def __init__(self, fred_api_key: Optional[str] = None):
        """
        Initialize the calculator

        Args:
            fred_api_key: FRED API key for yield curve and real rates data (optional)
        """
        self.fred_api_key = fred_api_key or os.environ.get('FRED_API_KEY')
        self.components = {}
        self.score = 0
        self.label = ""

    def calculate_price_momentum_score(self) -> Tuple[float, str]:
        """
        Calculate price momentum component (25% weight)
        TLT price movement - INVERTED (rising bonds = fear)

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")  # Long-term Treasury Bonds
            hist = tlt.history(period="3mo")

            if hist.empty:
                raise ValueError("No TLT data available")

            close_prices = hist['Close']

            # 14-day price change
            pct_change_14d = ((close_prices.iloc[-1] / close_prices.iloc[-15]) - 1) * 100

            # INVERTED: TLT rising = fear (flight to safety), falling = greed
            # +10% TLT = extreme fear (score 10)
            # -10% TLT = extreme greed (score 90)
            score = 50 - (pct_change_14d * 4)
            score = max(0, min(100, score))

            detail = f"TLT 14j: {pct_change_14d:+.1f}% (inverse)"

            return score, detail

        except Exception as e:
            print(f"Error calculating price momentum: {e}")
            return 50.0, "Data unavailable"

    def calculate_credit_spreads_score(self) -> Tuple[float, str]:
        """
        Calculate credit spreads component (20% weight)
        HYG (junk bonds) vs TLT (safe Treasuries)

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            hyg = yf.Ticker("HYG")  # High Yield Corporate Bonds
            tlt = yf.Ticker("TLT")  # Long-term Treasuries

            hyg_hist = hyg.history(period="2mo")
            tlt_hist = tlt.history(period="2mo")

            if hyg_hist.empty or tlt_hist.empty:
                raise ValueError("No HYG or TLT data available")

            # 14-day performance
            hyg_change = ((hyg_hist['Close'].iloc[-1] / hyg_hist['Close'].iloc[-15]) - 1) * 100
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100

            # Spread: HYG outperforming = risk appetite = greed
            spread = hyg_change - tlt_change

            # +5% spread = extreme greed, -5% spread = extreme fear
            score = 50 + (spread * 10)
            score = max(0, min(100, score))

            detail = f"HYG vs TLT: {spread:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating credit spreads: {e}")
            return 50.0, "Data unavailable"

    def calculate_yield_curve_score(self) -> Tuple[float, str]:
        """
        Calculate yield curve component (15% weight)
        2-Year vs 10-Year Treasury spread via FRED

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("No FRED API key - using fallback")
                return 50.0, "FRED API key missing"

            # Fetch 2Y and 10Y yields from FRED
            url_2y = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&api_key={self.fred_api_key}&file_type=json&sort_order=desc&limit=1"
            url_10y = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={self.fred_api_key}&file_type=json&sort_order=desc&limit=1"

            response_2y = requests.get(url_2y, timeout=10)
            response_10y = requests.get(url_10y, timeout=10)

            if response_2y.status_code != 200 or response_10y.status_code != 200:
                raise ValueError("FRED API request failed")

            data_2y = response_2y.json()
            data_10y = response_10y.json()

            yield_2y = float(data_2y['observations'][0]['value'])
            yield_10y = float(data_10y['observations'][0]['value'])

            # Yield curve spread (10Y - 2Y)
            spread = yield_10y - yield_2y

            # Normal curve (+1.5% to +2.5%) = greed (healthy growth)
            # Flat curve (0% to +0.5%) = neutral
            # Inverted curve (< 0%) = extreme fear (recession signal)
            if spread >= 1.5:
                score = 70 + min(30, (spread - 1.5) * 30)  # Up to 100
            elif spread >= 0:
                score = 40 + (spread / 1.5) * 30  # 40 to 70
            else:  # Inverted
                score = max(0, 40 + (spread * 80))  # Down to 0 for -0.5% inversion

            score = max(0, min(100, score))

            detail = f"Courbe: {spread:+.2f}% (10Y-2Y)"

            return score, detail

        except Exception as e:
            print(f"Error calculating yield curve: {e}")
            return 50.0, "Data unavailable"

    def calculate_bond_volatility_score(self) -> Tuple[float, str]:
        """
        Calculate bond volatility component (15% weight)
        TLT volatility as proxy for MOVE index

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")
            hist = tlt.history(period="3mo")

            if hist.empty:
                raise ValueError("No TLT data available")

            returns = hist['Close'].pct_change().dropna()

            # 14-day volatility
            vol_14d = returns.tail(14).std() * np.sqrt(252) * 100  # Annualized %

            # 30-day average volatility
            vol_30d_avg = returns.tail(30).std() * np.sqrt(252) * 100

            # High volatility = fear, low volatility = greed
            ratio = vol_14d / vol_30d_avg if vol_30d_avg > 0 else 1.0

            # ratio > 1.5 = extreme fear, ratio < 0.5 = extreme greed
            score = 50 + (1 - ratio) * 50
            score = max(0, min(100, score))

            detail = f"Vol TLT: {vol_14d:.1f}% vs {vol_30d_avg:.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating bond volatility: {e}")
            return 50.0, "Data unavailable"

    def calculate_safe_haven_flows_score(self) -> Tuple[float, str]:
        """
        Calculate safe haven flows component (10% weight)
        TLT volume spikes indicate flight to safety

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")
            hist = tlt.history(period="2mo")

            if hist.empty or 'Volume' not in hist.columns:
                raise ValueError("No TLT volume data available")

            current_volume = hist['Volume'].iloc[-1]
            avg_volume_30d = hist['Volume'].tail(30).mean()

            # Volume spike = fear (panic buying), low volume = greed
            ratio = current_volume / avg_volume_30d if avg_volume_30d > 0 else 1.0

            # ratio > 2 = extreme fear, ratio < 0.5 = extreme greed
            score = 50 + (1 - ratio) * 50
            score = max(0, min(100, score))

            detail = f"Volume TLT: {ratio:.2f}x vs moy 30j"

            return score, detail

        except Exception as e:
            print(f"Error calculating safe haven flows: {e}")
            return 50.0, "Data unavailable"

    def calculate_real_rates_score(self) -> Tuple[float, str]:
        """
        Calculate real rates component (10% weight)
        TIPS yield from FRED

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("No FRED API key - using fallback")
                return 50.0, "FRED API key missing"

            # Fetch 10-Year TIPS yield
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key={self.fred_api_key}&file_type=json&sort_order=desc&limit=1"

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                raise ValueError("FRED API request failed")

            data = response.json()
            real_rate = float(data['observations'][0]['value'])

            # Positive real rates = bonds attractive = greed
            # Negative real rates = inflation destroying returns = fear
            # +2% real = score 80, 0% = score 50, -2% = score 20
            score = 50 + (real_rate * 25)
            score = max(0, min(100, score))

            detail = f"TIPS 10Y: {real_rate:+.2f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating real rates: {e}")
            return 50.0, "Data unavailable"

    def calculate_equity_vs_bonds_score(self) -> Tuple[float, str]:
        """
        Calculate equity vs bonds component (5% weight)
        SPY vs TLT relative performance

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            spy = yf.Ticker("SPY")  # S&P 500
            tlt = yf.Ticker("TLT")  # Treasuries

            spy_hist = spy.history(period="2mo")
            tlt_hist = tlt.history(period="2mo")

            if spy_hist.empty or tlt_hist.empty:
                raise ValueError("No SPY or TLT data available")

            # 14-day performance
            spy_change = ((spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-15]) - 1) * 100
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100

            # SPY outperforming = risk-on = greed (bonds unloved)
            # TLT outperforming = risk-off = fear (defensive rotation)
            relative_perf = spy_change - tlt_change

            # +10% SPY outperformance = extreme greed
            # -10% (TLT outperforming) = extreme fear
            score = 50 + (relative_perf * 5)
            score = max(0, min(100, score))

            detail = f"SPY vs TLT: {relative_perf:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating equity vs bonds: {e}")
            return 50.0, "Data unavailable"

    def calculate_index(self) -> Dict:
        """
        Calculate the complete Bonds Fear & Greed Index

        Returns:
            Dictionary with score, label, components, and timestamp
        """
        print("Calculating Bonds Fear & Greed Index...")

        # Component weights
        weights = {
            'price_momentum': 0.25,      # 25%
            'credit_spreads': 0.20,      # 20%
            'yield_curve': 0.15,         # 15%
            'bond_volatility': 0.15,     # 15%
            'safe_haven_flows': 0.10,    # 10%
            'real_rates': 0.10,          # 10%
            'equity_vs_bonds': 0.05      # 5%
        }

        # Calculate each component
        price_momentum_score, price_momentum_detail = self.calculate_price_momentum_score()
        credit_spreads_score, credit_spreads_detail = self.calculate_credit_spreads_score()
        yield_curve_score, yield_curve_detail = self.calculate_yield_curve_score()
        bond_volatility_score, bond_volatility_detail = self.calculate_bond_volatility_score()
        safe_haven_flows_score, safe_haven_flows_detail = self.calculate_safe_haven_flows_score()
        real_rates_score, real_rates_detail = self.calculate_real_rates_score()
        equity_vs_bonds_score, equity_vs_bonds_detail = self.calculate_equity_vs_bonds_score()

        # Store components
        self.components = {
            'price_momentum': {
                'score': round(price_momentum_score, 1),
                'weight': weights['price_momentum'],
                'detail': price_momentum_detail
            },
            'credit_spreads': {
                'score': round(credit_spreads_score, 1),
                'weight': weights['credit_spreads'],
                'detail': credit_spreads_detail
            },
            'yield_curve': {
                'score': round(yield_curve_score, 1),
                'weight': weights['yield_curve'],
                'detail': yield_curve_detail
            },
            'bond_volatility': {
                'score': round(bond_volatility_score, 1),
                'weight': weights['bond_volatility'],
                'detail': bond_volatility_detail
            },
            'safe_haven_flows': {
                'score': round(safe_haven_flows_score, 1),
                'weight': weights['safe_haven_flows'],
                'detail': safe_haven_flows_detail
            },
            'real_rates': {
                'score': round(real_rates_score, 1),
                'weight': weights['real_rates'],
                'detail': real_rates_detail
            },
            'equity_vs_bonds': {
                'score': round(equity_vs_bonds_score, 1),
                'weight': weights['equity_vs_bonds'],
                'detail': equity_vs_bonds_detail
            }
        }

        # Calculate weighted average
        total_score = (
            price_momentum_score * weights['price_momentum'] +
            credit_spreads_score * weights['credit_spreads'] +
            yield_curve_score * weights['yield_curve'] +
            bond_volatility_score * weights['bond_volatility'] +
            safe_haven_flows_score * weights['safe_haven_flows'] +
            real_rates_score * weights['real_rates'] +
            equity_vs_bonds_score * weights['equity_vs_bonds']
        )

        self.score = round(total_score, 1)

        # Determine label
        if self.score < 25:
            self.label = "Extreme Fear"
        elif self.score < 45:
            self.label = "Fear"
        elif self.score < 55:
            self.label = "Neutral"
        elif self.score < 75:
            self.label = "Greed"
        else:
            self.label = "Extreme Greed"

        print(f"Bonds Index calculated: {self.score} ({self.label})")

        return {
            'score': self.score,
            'label': self.label,
            'components': self.components,
            'timestamp': datetime.now().isoformat(),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M UTC')
        }

    def calculate_simple_historical_score(self, target_date: datetime) -> float:
        """
        Calculate a simplified historical score for a specific date
        Uses only TLT price data (most reliable historical component)
        """
        try:
            # Fetch historical data around target date
            start_date = target_date - timedelta(days=60)
            end_date = target_date + timedelta(days=1)

            tlt = yf.Ticker("TLT")
            hist = tlt.history(start=start_date, end=end_date)

            if hist.empty or len(hist) < 15:
                return 50.0  # Neutral fallback

            # Find the closest date to target
            hist.index = hist.index.tz_localize(None)
            time_diffs = (hist.index - target_date).to_series().abs()
            closest_idx = time_diffs.argmin()

            if closest_idx < 14:
                return 50.0

            # Calculate 14-day momentum (inverted for bonds)
            close_14d_ago = hist['Close'].iloc[closest_idx - 14]
            close_now = hist['Close'].iloc[closest_idx]
            pct_change = ((close_now / close_14d_ago) - 1) * 100

            # Inverted: rising bonds = fear
            score = 50 - (pct_change * 5)
            return max(0, min(100, score))

        except Exception as e:
            print(f"Warning: Could not calculate historical score for {target_date.date()}: {e}")
            return 50.0

    def save_to_file(self, filepath: str = 'data/bonds-fear-greed.json', force_rebuild: bool = False):
        """
        Save the index data to a JSON file with historical tracking

        Args:
            filepath: Path to save the JSON file
            force_rebuild: If True, rebuild 365 days of history from scratch
        """
        # Ensure data directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        today = datetime.now().strftime('%Y-%m-%d')

        if force_rebuild:
            print("\n🔄 Force rebuilding 365-day history (this may take 2-3 minutes)...")
            history = []

            for i in range(364, -1, -1):
                historical_date = datetime.now() - timedelta(days=i)
                date_str = historical_date.strftime('%Y-%m-%d')

                if i == 0:
                    # Use today's calculated score
                    score = self.score
                    label = self.label
                else:
                    # Calculate simplified historical score
                    score = self.calculate_simple_historical_score(historical_date)
                    if score < 25:
                        label = "Extreme Fear"
                    elif score < 45:
                        label = "Fear"
                    elif score < 55:
                        label = "Neutral"
                    elif score < 75:
                        label = "Greed"
                    else:
                        label = "Extreme Greed"

                history.append({
                    'date': date_str,
                    'score': round(score, 1),
                    'label': label
                })

                if (365 - i) % 50 == 0:
                    print(f"  Progress: {365 - i}/365 days calculated...")

            print("✅ Historical rebuild complete!")

        else:
            # Load existing data if file exists
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    existing_data = json.load(f)
            else:
                existing_data = {'history': []}

            # Update or append to history
            history = existing_data.get('history', [])

            # Remove today's entry if it exists (update)
            history = [entry for entry in history if entry['date'] != today]

            # Add new entry
            history.append({
                'date': today,
                'score': self.score,
                'label': self.label
            })

            # Keep only last 365 days
            history = sorted(history, key=lambda x: x['date'])[-365:]

        # Prepare final data
        final_data = {
            'score': self.score,
            'label': self.label,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'components': self.components,
            'history': history
        }

        # Save to file
        with open(filepath, 'w') as f:
            json.dump(final_data, f, indent=2)

        print(f"Data saved to {filepath}")


def main():
    """Main function to run the calculator"""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate Bonds Fear & Greed Index')
    parser.add_argument('--output', default='data/bonds-fear-greed.json',
                       help='Output JSON file path')
    parser.add_argument('--fred-api-key', help='FRED API key (or set FRED_API_KEY env var)')
    parser.add_argument('--force-rebuild', action='store_true',
                       help='Rebuild complete 365-day history from scratch (slow)')

    args = parser.parse_args()

    # Initialize calculator
    calculator = BondsFearGreedIndex(fred_api_key=args.fred_api_key)

    # Calculate index
    result = calculator.calculate_index()

    # Print results
    print("\n=== Bonds Fear & Greed Index ===")
    print(f"Score: {result['score']}")
    print(f"Label: {result['label']}")
    print(f"Timestamp: {result['last_update']}")
    print("\nComponents:")
    for name, data in result['components'].items():
        print(f"  {name}: {data['score']} (weight: {data['weight']*100}%) - {data['detail']}")

    # Save to file
    calculator.save_to_file(args.output, force_rebuild=args.force_rebuild)


if __name__ == '__main__':
    main()
