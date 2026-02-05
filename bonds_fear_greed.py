#!/usr/bin/env python3
"""
Bonds Fear & Greed Index Calculator
Calculates a sentiment index for bond market (0-100) based on 5 bond-specific components
100% bond market focused - zero overlap with stocks index
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
            fred_api_key: FRED API key for yield curve and real rates data (required for best results)
        """
        fred_key = fred_api_key or os.environ.get('FRED_API_KEY')
        self.fred_api_key = fred_key.strip() if fred_key else None
        self.components = {}
        self.score = 0
        self.label = ""

    def calculate_yield_curve_score(self) -> Tuple[float, str]:
        """
        Calculate yield curve shape component (30% weight)
        The most important bond market indicator - 2Y vs 10Y Treasury spread

        Interpretation:
        - Steep curve (+2% to +3%) = Greed (healthy growth expectations)
        - Normal (+1% to +2%) = Neutral to Greed
        - Flat (0% to +1%) = Fear (uncertainty)
        - Inverted (< 0%) = Extreme Fear (recession signal)

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("⚠️  No FRED API key - yield curve using fallback")
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

            # Scoring logic
            if spread >= 2.5:  # Very steep
                score = 90 + min(10, (spread - 2.5) * 10)
            elif spread >= 1.5:  # Steep (healthy)
                score = 70 + (spread - 1.5) * 20
            elif spread >= 0.5:  # Normal
                score = 50 + (spread - 0.5) * 20
            elif spread >= 0:  # Flat
                score = 30 + spread * 40
            else:  # Inverted (recession signal)
                score = max(0, 30 + spread * 60)

            score = max(0, min(100, score))

            detail = f"Spread 10Y-2Y: {spread:+.2f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating yield curve: {e}")
            return 50.0, "Data unavailable"

    def calculate_duration_risk_appetite(self) -> Tuple[float, str]:
        """
        Calculate duration risk appetite component (25% weight)
        Measures demand for long-term bonds via TLT momentum and volume

        High TLT demand = investors want to lock in long rates = Greed
        Low TLT demand = duration risk aversion = Fear

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")  # iShares 20+ Year Treasury Bond ETF
            hist = tlt.history(period="3mo")

            if hist.empty or len(hist) < 20:
                raise ValueError("No TLT data available")

            # 1. Price momentum (60% of component)
            close_prices = hist['Close']
            pct_change_14d = ((close_prices.iloc[-1] / close_prices.iloc[-14]) - 1) * 100

            # TLT rising = investors seeking duration = Greed
            # TLT falling = investors avoiding duration = Fear
            momentum_score = 50 + (pct_change_14d * 4)
            momentum_score = max(0, min(100, momentum_score))

            # 2. Volume trend (40% of component)
            if 'Volume' in hist.columns:
                current_volume = hist['Volume'].tail(5).mean()  # Recent 5-day avg
                baseline_volume = hist['Volume'].tail(60).mean()  # 60-day avg
                volume_ratio = current_volume / baseline_volume if baseline_volume > 0 else 1.0

                # High volume with price up = strong buying = Greed
                # High volume with price down = panic selling = Fear
                if pct_change_14d > 0:
                    volume_score = 50 + min(50, (volume_ratio - 1) * 50)
                else:
                    volume_score = 50 - min(50, (volume_ratio - 1) * 50)

                volume_score = max(0, min(100, volume_score))
            else:
                volume_score = 50.0

            # Combined score
            score = momentum_score * 0.6 + volume_score * 0.4

            detail = f"TLT 14j: {pct_change_14d:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating duration risk: {e}")
            return 50.0, "Data unavailable"

    def calculate_real_yields_score(self) -> Tuple[float, str]:
        """
        Calculate real yields component (20% weight)
        TIPS yield = nominal yield minus inflation expectations

        Positive real yields = bonds paying above inflation = Greed (attractive)
        Negative real yields = inflation destroying returns = Fear

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("⚠️  No FRED API key - real yields using fallback")
                return 50.0, "FRED API key missing"

            # Fetch 10-Year TIPS yield (real yield)
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key={self.fred_api_key}&file_type=json&sort_order=desc&limit=1"

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                raise ValueError("FRED API request failed")

            data = response.json()
            real_rate = float(data['observations'][0]['value'])

            # Scoring logic
            if real_rate >= 2.0:  # Very attractive
                score = 85 + min(15, (real_rate - 2.0) * 10)
            elif real_rate >= 1.0:  # Attractive
                score = 65 + (real_rate - 1.0) * 20
            elif real_rate >= 0:  # Neutral
                score = 45 + real_rate * 20
            elif real_rate >= -1.0:  # Negative but manageable
                score = 25 + (real_rate + 1.0) * 20
            else:  # Very negative
                score = max(0, 25 + (real_rate + 1.0) * 25)

            score = max(0, min(100, score))

            detail = f"TIPS 10Y: {real_rate:+.2f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating real yields: {e}")
            return 50.0, "Data unavailable"

    def calculate_credit_quality_spread(self) -> Tuple[float, str]:
        """
        Calculate credit quality spread component (15% weight)
        LQD (investment grade) vs TLT (Treasuries)

        Different from stocks HYG! This measures INVESTMENT GRADE appetite
        LQD outperforming = credit confidence = Greed
        LQD underperforming = credit stress = Fear

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            lqd = yf.Ticker("LQD")  # iShares iBoxx Investment Grade Corporate Bond ETF
            tlt = yf.Ticker("TLT")  # Long-term Treasuries

            lqd_hist = lqd.history(period="2mo")
            tlt_hist = tlt.history(period="2mo")

            if lqd_hist.empty or tlt_hist.empty or len(lqd_hist) < 15 or len(tlt_hist) < 15:
                raise ValueError("No LQD or TLT data available")

            # 14-day performance comparison
            lqd_change = ((lqd_hist['Close'].iloc[-1] / lqd_hist['Close'].iloc[-14]) - 1) * 100
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-14]) - 1) * 100

            # Spread: LQD outperforming = taking credit risk = Greed
            spread = lqd_change - tlt_change

            # Scoring: +3% spread = extreme greed, -3% spread = extreme fear
            score = 50 + (spread * 16.67)
            score = max(0, min(100, score))

            detail = f"LQD vs TLT: {spread:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating credit quality: {e}")
            return 50.0, "Data unavailable"

    def calculate_term_premium_demand(self) -> Tuple[float, str]:
        """
        Calculate term premium demand component (10% weight)
        TLT (long-term) vs SHY (short-term) relative performance

        TLT outperforming = investors want to lock in long rates = Greed
        SHY outperforming = rate risk aversion = Fear

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")  # 20+ Year Treasury
            shy = yf.Ticker("SHY")  # 1-3 Year Treasury

            tlt_hist = tlt.history(period="2mo")
            shy_hist = shy.history(period="2mo")

            if tlt_hist.empty or shy_hist.empty or len(tlt_hist) < 15 or len(shy_hist) < 15:
                raise ValueError("No TLT or SHY data available")

            # 14-day performance comparison
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-14]) - 1) * 100
            shy_change = ((shy_hist['Close'].iloc[-1] / shy_hist['Close'].iloc[-14]) - 1) * 100

            # Relative performance
            relative_perf = tlt_change - shy_change

            # TLT outperforming = duration demand = Greed
            # SHY outperforming = duration aversion = Fear
            score = 50 + (relative_perf * 10)
            score = max(0, min(100, score))

            detail = f"TLT vs SHY: {relative_perf:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating term premium: {e}")
            return 50.0, "Data unavailable"

    def calculate_index(self) -> Dict:
        """
        Calculate the complete Bonds Fear & Greed Index

        Returns:
            Dictionary with score, label, components, and timestamp
        """
        print("\n" + "="*60)
        print("🔵 CALCULATING BONDS FEAR & GREED INDEX")
        print("="*60)

        # Component weights (total = 100%)
        weights = {
            'yield_curve': 0.30,          # 30% - Most important
            'duration_risk': 0.25,        # 25%
            'real_yields': 0.20,          # 20%
            'credit_quality': 0.15,       # 15%
            'term_premium': 0.10          # 10%
        }

        # Calculate each component
        print("\n📊 Component Calculations:")
        print("-" * 60)

        yield_curve_score, yield_curve_detail = self.calculate_yield_curve_score()
        print(f"1. Yield Curve Shape (30%):     {yield_curve_score:5.1f} - {yield_curve_detail}")

        duration_risk_score, duration_risk_detail = self.calculate_duration_risk_appetite()
        print(f"2. Duration Risk Appetite (25%): {duration_risk_score:5.1f} - {duration_risk_detail}")

        real_yields_score, real_yields_detail = self.calculate_real_yields_score()
        print(f"3. Real Yields (20%):            {real_yields_score:5.1f} - {real_yields_detail}")

        credit_quality_score, credit_quality_detail = self.calculate_credit_quality_spread()
        print(f"4. Credit Quality Spread (15%):  {credit_quality_score:5.1f} - {credit_quality_detail}")

        term_premium_score, term_premium_detail = self.calculate_term_premium_demand()
        print(f"5. Term Premium Demand (10%):    {term_premium_score:5.1f} - {term_premium_detail}")

        # Store components
        self.components = {
            'Yield Curve': {
                'score': round(yield_curve_score, 1),
                'weight': weights['yield_curve'],
                'detail': yield_curve_detail
            },
            'Duration Risk': {
                'score': round(duration_risk_score, 1),
                'weight': weights['duration_risk'],
                'detail': duration_risk_detail
            },
            'Real Yields': {
                'score': round(real_yields_score, 1),
                'weight': weights['real_yields'],
                'detail': real_yields_detail
            },
            'Credit Quality': {
                'score': round(credit_quality_score, 1),
                'weight': weights['credit_quality'],
                'detail': credit_quality_detail
            },
            'Term Premium': {
                'score': round(term_premium_score, 1),
                'weight': weights['term_premium'],
                'detail': term_premium_detail
            }
        }

        # Calculate weighted average
        total_score = (
            yield_curve_score * weights['yield_curve'] +
            duration_risk_score * weights['duration_risk'] +
            real_yields_score * weights['real_yields'] +
            credit_quality_score * weights['credit_quality'] +
            term_premium_score * weights['term_premium']
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

        print("-" * 60)
        print(f"\n🎯 FINAL BONDS INDEX: {self.score} - {self.label}")
        print("="*60 + "\n")

        return {
            'score': self.score,
            'label': self.label,
            'components': self.components,
            'timestamp': datetime.now().isoformat(),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M UTC')
        }

    def calculate_simple_historical_score(self, target_date: datetime) -> float:
        """
        Calculate historical score for a past date using all 5 components

        Args:
            target_date: The date to calculate the score for

        Returns:
            Historical score (0-100)
        """
        try:
            print(f"  Calculating for {target_date.strftime('%Y-%m-%d')}...", end=" ")

            # Fetch historical data up to target date
            start_date = target_date - timedelta(days=90)
            end_date = target_date + timedelta(days=1)

            # Get historical data for all ETFs
            tlt = yf.Ticker("TLT")
            lqd = yf.Ticker("LQD")
            shy = yf.Ticker("SHY")

            tlt_hist = tlt.history(start=start_date, end=end_date)
            lqd_hist = lqd.history(start=start_date, end=end_date)
            shy_hist = shy.history(start=start_date, end=end_date)

            if tlt_hist.empty or len(tlt_hist) < 20:
                print("insufficient data")
                return 50.0

            # 1. YIELD CURVE (30% weight) - Using FRED API for historical accuracy
            if self.fred_api_key:
                try:
                    date_str = target_date.strftime('%Y-%m-%d')
                    url_2y = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS2&api_key={self.fred_api_key}&file_type=json&observation_start={date_str}&observation_end={date_str}"
                    url_10y = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={self.fred_api_key}&file_type=json&observation_start={date_str}&observation_end={date_str}"

                    response_2y = requests.get(url_2y, timeout=10)
                    response_10y = requests.get(url_10y, timeout=10)

                    if response_2y.status_code == 200 and response_10y.status_code == 200:
                        data_2y = response_2y.json()
                        data_10y = response_10y.json()

                        if data_2y['observations'] and data_10y['observations']:
                            yield_2y = float(data_2y['observations'][0]['value'])
                            yield_10y = float(data_10y['observations'][0]['value'])
                            spread = yield_10y - yield_2y

                            # Same scoring logic as current-day calculation
                            if spread >= 2.5:
                                yield_curve_score = 90 + min(10, (spread - 2.5) * 10)
                            elif spread >= 1.5:
                                yield_curve_score = 70 + (spread - 1.5) * 20
                            elif spread >= 0.5:
                                yield_curve_score = 50 + (spread - 0.5) * 20
                            elif spread >= 0:
                                yield_curve_score = 30 + spread * 40
                            else:
                                yield_curve_score = max(0, 30 + spread * 60)
                            yield_curve_score = max(0, min(100, yield_curve_score))
                        else:
                            yield_curve_score = 50.0
                    else:
                        yield_curve_score = 50.0
                except:
                    yield_curve_score = 50.0
            else:
                yield_curve_score = 50.0

            # 2. DURATION RISK APPETITE (25% weight) - TLT momentum + volume
            if len(tlt_hist) >= 14:
                pct_change_14d = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-14]) - 1) * 100
                momentum_score = 50 + (pct_change_14d * 4)
                momentum_score = max(0, min(100, momentum_score))

                if 'Volume' in tlt_hist.columns and len(tlt_hist) >= 60:
                    current_volume = tlt_hist['Volume'].tail(5).mean()
                    baseline_volume = tlt_hist['Volume'].tail(60).mean()
                    volume_ratio = current_volume / baseline_volume if baseline_volume > 0 else 1.0

                    if pct_change_14d > 0:
                        volume_score = 50 + min(50, (volume_ratio - 1) * 50)
                    else:
                        volume_score = 50 - min(50, (volume_ratio - 1) * 50)
                    volume_score = max(0, min(100, volume_score))
                else:
                    volume_score = 50.0

                duration_risk_score = momentum_score * 0.6 + volume_score * 0.4
            else:
                duration_risk_score = 50.0

            # 3. REAL YIELDS (20% weight) - Using FRED API for historical accuracy
            if self.fred_api_key:
                try:
                    date_str = target_date.strftime('%Y-%m-%d')
                    url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key={self.fred_api_key}&file_type=json&observation_start={date_str}&observation_end={date_str}"

                    response = requests.get(url, timeout=10)

                    if response.status_code == 200:
                        data = response.json()

                        if data['observations']:
                            real_rate = float(data['observations'][0]['value'])

                            # Same scoring logic as current-day calculation
                            if real_rate >= 2.0:
                                real_yields_score = 85 + min(15, (real_rate - 2.0) * 10)
                            elif real_rate >= 1.0:
                                real_yields_score = 65 + (real_rate - 1.0) * 20
                            elif real_rate >= 0:
                                real_yields_score = 45 + real_rate * 20
                            elif real_rate >= -1.0:
                                real_yields_score = 25 + (real_rate + 1.0) * 20
                            else:
                                real_yields_score = max(0, 25 + (real_rate + 1.0) * 25)
                            real_yields_score = max(0, min(100, real_yields_score))
                        else:
                            real_yields_score = 50.0
                    else:
                        real_yields_score = 50.0
                except:
                    real_yields_score = 50.0
            else:
                real_yields_score = 50.0

            # 4. CREDIT QUALITY SPREAD (15% weight) - LQD vs TLT
            if len(lqd_hist) >= 14 and len(tlt_hist) >= 14:
                lqd_change = ((lqd_hist['Close'].iloc[-1] / lqd_hist['Close'].iloc[-14]) - 1) * 100
                tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-14]) - 1) * 100
                spread = lqd_change - tlt_change
                credit_quality_score = 50 + (spread * 16.67)
                credit_quality_score = max(0, min(100, credit_quality_score))
            else:
                credit_quality_score = 50.0

            # 5. TERM PREMIUM DEMAND (10% weight) - TLT vs SHY
            if len(tlt_hist) >= 14 and len(shy_hist) >= 14:
                tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-14]) - 1) * 100
                shy_change = ((shy_hist['Close'].iloc[-1] / shy_hist['Close'].iloc[-14]) - 1) * 100
                relative_perf = tlt_change - shy_change
                term_premium_score = 50 + (relative_perf * 10)
                term_premium_score = max(0, min(100, term_premium_score))
            else:
                term_premium_score = 50.0

            # Weighted average with actual weights (5 components)
            total_score = (
                yield_curve_score * 0.30 +
                duration_risk_score * 0.25 +
                real_yields_score * 0.20 +
                credit_quality_score * 0.15 +
                term_premium_score * 0.10
            )

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1)

        except Exception as e:
            print(f"error: {e}")
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

        print(f"✅ Data saved to {filepath}")


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
    print("\n📋 COMPONENT BREAKDOWN:")
    print("="*60)
    for name, data in result['components'].items():
        print(f"{name:20s}: {data['score']:5.1f} (weight: {data['weight']*100:4.0f}%) - {data['detail']}")
    print("="*60)

    # Save to file
    calculator.save_to_file(args.output, force_rebuild=args.force_rebuild)


if __name__ == '__main__':
    main()
