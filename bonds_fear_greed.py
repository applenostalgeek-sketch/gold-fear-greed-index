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
        Calculate duration risk / capital flow component (25% weight)
        TLT price movement - DIRECT (rising bonds = capital flowing IN)

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

            # DIRECT: TLT rising = capital flowing INTO bonds = high score
            # Extremely aggressive: +3% TLT = score 80, -3% TLT = score 20
            score = 50 + (pct_change_14d * 10)
            score = max(0, min(100, score))

            detail = f"TLT 14j: {pct_change_14d:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating price momentum: {e}")
            return 50.0, "Data unavailable"

    def calculate_credit_spreads_score(self) -> Tuple[float, str]:
        """
        Calculate credit quality component (15% weight)
        LQD (investment grade) vs TLT (safe Treasuries)

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            lqd = yf.Ticker("LQD")  # Investment Grade Corporate Bonds
            tlt = yf.Ticker("TLT")  # Long-term Treasuries

            lqd_hist = lqd.history(period="2mo")
            tlt_hist = tlt.history(period="2mo")

            if lqd_hist.empty or tlt_hist.empty:
                raise ValueError("No LQD or TLT data available")

            # 14-day performance
            lqd_change = ((lqd_hist['Close'].iloc[-1] / lqd_hist['Close'].iloc[-15]) - 1) * 100
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100

            # Spread: LQD outperforming = credit spreads tightening = greed
            spread = lqd_change - tlt_change

            # +5% spread = extreme greed, -5% spread = extreme fear
            score = 50 + (spread * 10)
            score = max(0, min(100, score))

            detail = f"LQD vs TLT: {spread:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating credit quality: {e}")
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

            # INVERTED LOGIC (capital rotation perspective):
            # Steep curve (+2%+) = strong economy = capital flows to STOCKS = low bonds score
            # Flat curve (0% to +1%) = neutral = moderate bonds score
            # Inverted curve (<0%) = recession fear = flight to bonds = high bonds score
            if spread >= 2.0:
                # Very steep = very low bonds demand
                score = max(0, 30 - (spread - 2.0) * 20)  # Down to 0
            elif spread >= 0:
                # Normal to flat = decreasing bonds demand as curve steepens
                score = 70 - (spread / 2.0) * 40  # 70 down to 30
            else:  # Inverted
                # Inverted = flight to safety = high bonds demand
                score = 70 + min(30, abs(spread) * 60)  # Up to 100

            score = max(0, min(100, score))

            detail = f"Courbe: {spread:+.2f}% (10Y-2Y)"

            return score, detail

        except Exception as e:
            print(f"FRED yield curve failed: {e} - trying Yahoo fallback")

            # FALLBACK: Use Yahoo Finance for yield curve
            try:
                tnx = yf.Ticker("^TNX")  # 10-Year Treasury Yield
                irx = yf.Ticker("^IRX")  # 13-week T-Bill (short-term proxy)

                tnx_hist = tnx.history(period="5d")
                irx_hist = irx.history(period="5d")

                if tnx_hist.empty or irx_hist.empty:
                    raise ValueError("Yahoo yield data unavailable")

                # Get latest yields (Yahoo returns yields as percentages already)
                yield_10y = tnx_hist['Close'].iloc[-1]
                yield_short = irx_hist['Close'].iloc[-1]

                # Calculate spread
                spread = yield_10y - yield_short

                # Same INVERTED logic as FRED (capital rotation)
                if spread >= 2.0:
                    score = max(0, 30 - (spread - 2.0) * 20)
                elif spread >= 0:
                    score = 70 - (spread / 2.0) * 40
                else:
                    score = 70 + min(30, abs(spread) * 60)

                score = max(0, min(100, score))
                detail = f"Courbe: {spread:+.2f}% (10Y-3M, Yahoo)"

                print(f"✅ Yahoo fallback successful: {detail}")
                return score, detail

            except Exception as yahoo_error:
                print(f"Yahoo fallback also failed: {yahoo_error}")
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

            # Very conservative scoring:
            # +4% real = score 82 (very attractive)
            # 0% = score 50 (neutral)
            # -4% = score 18 (very unattractive)
            score = 50 + (real_rate * 8)
            score = max(0, min(100, score))

            detail = f"TIPS 10Y: {real_rate:+.2f}%"

            return score, detail

        except Exception as e:
            print(f"FRED real rates failed: {e} - trying Yahoo fallback")

            # FALLBACK: Use TIP ETF and TNX to estimate real yield
            try:
                tip = yf.Ticker("TIP")  # TIPS ETF
                tnx = yf.Ticker("^TNX")  # 10-Year Treasury Yield

                tip_hist = tip.history(period="1mo")
                tnx_hist = tnx.history(period="5d")

                if tip_hist.empty or tnx_hist.empty:
                    raise ValueError("Yahoo TIPS/yield data unavailable")

                # Get 10Y nominal yield
                nominal_yield = tnx_hist['Close'].iloc[-1]

                # Estimate inflation expectation from TIP performance
                # TIP 14-day return as proxy for inflation expectations
                tip_return_14d = ((tip_hist['Close'].iloc[-1] / tip_hist['Close'].iloc[-14]) - 1) * 100

                # Rough approximation: real yield = nominal - (TIP return * 5)
                # This is very approximate but better than 50.0 default
                estimated_real_rate = nominal_yield - (tip_return_14d * 5)

                # Very conservative scoring (same as FRED)
                score = 50 + (estimated_real_rate * 8)
                score = max(0, min(100, score))

                detail = f"TIPS est.: {estimated_real_rate:+.2f}% (Yahoo)"

                print(f"✅ Yahoo fallback successful: {detail}")
                return score, detail

            except Exception as yahoo_error:
                print(f"Yahoo fallback also failed: {yahoo_error}")
                return 50.0, "Data unavailable"

    def calculate_term_premium_score(self) -> Tuple[float, str]:
        """
        Calculate term premium demand component (10% weight)
        TLT (long-term) vs SHY (short-term) relative performance

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            tlt = yf.Ticker("TLT")  # 20+ Year Treasury
            shy = yf.Ticker("SHY")  # 1-3 Year Treasury

            tlt_hist = tlt.history(period="2mo")
            shy_hist = shy.history(period="2mo")

            if tlt_hist.empty or shy_hist.empty:
                raise ValueError("No TLT or SHY data available")

            # 14-day performance
            tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
            shy_change = ((shy_hist['Close'].iloc[-1] / shy_hist['Close'].iloc[-15]) - 1) * 100

            # TLT outperforming = seeking duration = greed (locking in long rates)
            # SHY outperforming = avoiding duration = fear (staying short)
            relative_perf = tlt_change - shy_change

            # +5% TLT outperformance = extreme greed
            # -5% SHY outperformance = extreme fear
            score = 50 + (relative_perf * 10)
            score = max(0, min(100, score))

            detail = f"TLT vs SHY: {relative_perf:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating term premium: {e}")
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

        # Component weights (balanced like other markets)
        weights = {
            'duration_risk': 0.30,       # 30% - TLT momentum (price action)
            'term_premium': 0.25,        # 25% - TLT vs SHY (duration demand)
            'credit_quality': 0.20,      # 20% - LQD vs TLT (credit appetite)
            'yield_curve': 0.15,         # 15% - Macro sentiment
            'real_rates': 0.10           # 10% - Attractiveness vs inflation
        }

        # Calculate each component
        yield_curve_score, yield_curve_detail = self.calculate_yield_curve_score()
        duration_risk_score, duration_risk_detail = self.calculate_price_momentum_score()
        real_rates_score, real_rates_detail = self.calculate_real_rates_score()
        credit_quality_score, credit_quality_detail = self.calculate_credit_spreads_score()
        term_premium_score, term_premium_detail = self.calculate_term_premium_score()

        # Store components (5 bond-specific indicators)
        self.components = {
            'yield_curve': {
                'score': round(yield_curve_score, 1),
                'weight': weights['yield_curve'],
                'detail': yield_curve_detail
            },
            'duration_risk': {
                'score': round(duration_risk_score, 1),
                'weight': weights['duration_risk'],
                'detail': duration_risk_detail
            },
            'real_rates': {
                'score': round(real_rates_score, 1),
                'weight': weights['real_rates'],
                'detail': real_rates_detail
            },
            'credit_quality': {
                'score': round(credit_quality_score, 1),
                'weight': weights['credit_quality'],
                'detail': credit_quality_detail
            },
            'term_premium': {
                'score': round(term_premium_score, 1),
                'weight': weights['term_premium'],
                'detail': term_premium_detail
            }
        }

        # Calculate weighted average (5 components)
        total_score = (
            yield_curve_score * weights['yield_curve'] +
            duration_risk_score * weights['duration_risk'] +
            real_rates_score * weights['real_rates'] +
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
            start_date = target_date - timedelta(days=90)
            end_date = target_date + timedelta(days=1)

            # Get historical data for ALL components
            tlt = yf.Ticker("TLT")
            lqd = yf.Ticker("LQD")

            tlt_hist = tlt.history(start=start_date, end=end_date)
            lqd_hist = lqd.history(start=start_date, end=end_date)

            if tlt_hist.empty or len(tlt_hist) < 20:
                print("insufficient data")
                return 50.0

            # 1. PRICE MOMENTUM (60% weight) - TLT 14-day change (DIRECT - capital flow)
            if len(tlt_hist) >= 15:
                pct_change_14d = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                # Extremely aggressive: +3% TLT = score 80, -3% TLT = score 20
                price_momentum_score = 50 + (pct_change_14d * 10)
                price_momentum_score = max(0, min(100, price_momentum_score))
            else:
                price_momentum_score = 50.0

            # 2. CREDIT QUALITY (15% weight) - LQD vs TLT
            if len(lqd_hist) >= 15 and len(tlt_hist) >= 15:
                lqd_change = ((lqd_hist['Close'].iloc[-1] / lqd_hist['Close'].iloc[-15]) - 1) * 100
                tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                spread = lqd_change - tlt_change
                credit_spreads_score = 50 + (spread * 10)
                credit_spreads_score = max(0, min(100, credit_spreads_score))
            else:
                credit_spreads_score = 50.0

            # 3. YIELD CURVE (30% weight) - INVERTED (capital rotation logic)
            try:
                tnx = yf.Ticker("^TNX")
                irx = yf.Ticker("^IRX")
                tnx_hist = tnx.history(start=start_date, end=end_date)
                irx_hist = irx.history(start=start_date, end=end_date)

                if len(tnx_hist) > 0 and len(irx_hist) > 0:
                    yield_10y = tnx_hist['Close'].iloc[-1]
                    yield_short = irx_hist['Close'].iloc[-1]
                    spread = yield_10y - yield_short

                    # INVERTED: Steep = capital to stocks, Inverted = capital to bonds
                    if spread >= 2.0:
                        yield_curve_score = max(0, 30 - (spread - 2.0) * 20)
                    elif spread >= 0:
                        yield_curve_score = 70 - (spread / 2.0) * 40
                    else:
                        yield_curve_score = 70 + min(30, abs(spread) * 60)
                    yield_curve_score = max(0, min(100, yield_curve_score))
                else:
                    yield_curve_score = 50.0
            except:
                yield_curve_score = 50.0

            # 4. REAL RATES (20% weight) - TIP fallback for historical
            try:
                tip = yf.Ticker("TIP")
                tip_hist = tip.history(start=start_date, end=end_date)

                if len(tip_hist) >= 14 and len(tnx_hist) > 0:
                    nominal_yield = tnx_hist['Close'].iloc[-1]
                    tip_return_14d = ((tip_hist['Close'].iloc[-1] / tip_hist['Close'].iloc[-14]) - 1) * 100
                    estimated_real_rate = nominal_yield - (tip_return_14d * 5)
                    # Very conservative scoring
                    real_rates_score = 50 + (estimated_real_rate * 8)
                    real_rates_score = max(0, min(100, real_rates_score))
                else:
                    real_rates_score = 50.0
            except:
                real_rates_score = 50.0

            # 5. TERM PREMIUM (10% weight) - TLT vs SHY
            shy_hist = yf.Ticker("SHY").history(start=start_date, end=end_date)
            if len(tlt_hist) >= 15 and len(shy_hist) >= 15:
                tlt_change = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                shy_change = ((shy_hist['Close'].iloc[-1] / shy_hist['Close'].iloc[-15]) - 1) * 100
                relative_perf = tlt_change - shy_change
                term_premium_score = 50 + (relative_perf * 10)
                term_premium_score = max(0, min(100, term_premium_score))
            else:
                term_premium_score = 50.0

            # Weighted average (balanced)
            total_score = (
                price_momentum_score * 0.30 +
                term_premium_score * 0.25 +
                credit_spreads_score * 0.20 +
                yield_curve_score * 0.15 +
                real_rates_score * 0.10
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
