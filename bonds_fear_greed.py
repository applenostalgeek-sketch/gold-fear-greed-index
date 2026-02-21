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
            # Calibrated: ~±3.3% TLT = score 0/100 (covers most 14-day moves)
            score = 50 + (pct_change_14d * 15)
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

            # +2.5% spread = extreme greed, -2.5% spread = extreme fear
            score = 50 + (spread * 20)
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
                raise ValueError("No FRED API key")

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

            # DIRECT LOGIC (term premium perspective):
            # Steep curve (+1.7%+) = high term premium = rewarding long bond holders = GREED
            # Flat curve (0%) = no term premium = NEUTRAL
            # Inverted curve (<0%) = Fed hiking aggressively = bond prices crushed = FEAR
            score = 50 + (spread * 30)
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

                # Same DIRECT logic as FRED (term premium)
                score = 50 + (spread * 30)

                score = max(0, min(100, score))
                detail = f"Courbe: {spread:+.2f}% (10Y-3M, Yahoo)"

                print(f"Yahoo fallback successful: {detail}")
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

            # 5-day volatility (fast window for crisis detection)
            vol_5d = returns.tail(5).std() * np.sqrt(252) * 100  # Annualized %

            # 30-day baseline volatility
            vol_30d_avg = returns.tail(30).std() * np.sqrt(252) * 100

            # High volatility = fear, low volatility = greed
            ratio = vol_5d / vol_30d_avg if vol_30d_avg > 0 else 1.0

            # Aggressive multiplier: ratio 1.5 = score 12, ratio 2.0 = score 0
            # ratio 0.5 = score 87, ratio 0.3 = score 100
            score = 50 + (1 - ratio) * 75
            score = max(0, min(100, score))

            detail = f"Vol TLT 5j: {vol_5d:.1f}% vs 30j: {vol_30d_avg:.1f}%"

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
        Calculate real rates component (15% weight)
        TIPS yield from FRED — higher real rates = bond prices fall = lower score (fear)

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            if not self.fred_api_key:
                print("No FRED API key - using fallback")
                raise ValueError("No FRED API key")

            # Fetch 10-Year TIPS yield
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key={self.fred_api_key}&file_type=json&sort_order=desc&limit=1"

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                raise ValueError("FRED API request failed")

            data = response.json()
            real_rate = float(data['observations'][0]['value'])

            # Scoring: higher real rates = bond prices fall = FEAR (low score)
            # Lower real rates = bond prices rise = GREED (high score)
            # Centered on 1.5% (current regime avg): 1.5% = 50, 4% = 0, -1% = 100
            score = 50 - (real_rate - 1.5) * 20
            score = max(0, min(100, score))

            detail = f"TIPS 10Y: {real_rate:+.2f}%"

            return score, detail

        except Exception as e:
            print(f"FRED real rates failed: {e} - trying Yahoo fallback")

            # FALLBACK: Use nominal 10Y yield centered on historical average
            try:
                tnx = yf.Ticker("^TNX")  # 10-Year Treasury Yield
                tnx_hist = tnx.history(period="5d")

                if tnx_hist.empty:
                    raise ValueError("Yahoo yield data unavailable")

                nominal_yield = tnx_hist['Close'].iloc[-1]

                # Fallback: use nominal yield centered on ~4.0% (current regime avg)
                # Higher yield = bond prices fall = FEAR (low score)
                score = 50 - (nominal_yield - 4.0) * 20
                score = max(0, min(100, score))

                detail = f"10Y Yield: {nominal_yield:.2f}% (Yahoo fallback)"

                print(f"Yahoo fallback successful: {detail}")
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
        Calculate equity vs bonds rotation component (10% weight)
        TLT vs SPY relative performance — from BONDS perspective
        Bonds outperform stocks = capital flowing into bonds = greed for bonds

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

            # FROM BONDS PERSPECTIVE:
            # TLT outperforming SPY = capital flowing to bonds = greed for bonds = HIGH score
            # SPY outperforming TLT = bonds unloved = fear for bonds = LOW score
            relative_perf = tlt_change - spy_change

            score = 50 + (relative_perf * 8)
            score = max(0, min(100, score))

            detail = f"TLT vs SPY: {relative_perf:+.1f}%"

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
        print("Calculating Bonds Fear & Greed Index v2...")

        # Component weights (6 components, Duration Risk primary)
        weights = {
            'duration_risk': 0.30,       # 30% - TLT momentum (PRIMARY)
            'yield_curve': 0.20,         # 20% - Structural signal
            'credit_quality': 0.20,      # 20% - LQD vs TLT (credit appetite)
            'real_rates': 0.15,          # 15% - Attractiveness vs inflation
            'bond_volatility': 0.10,     # 10% - MOVE index proxy (crisis detection)
            'equity_vs_bonds': 0.05      # 5% - Stock/bond rotation
        }

        # Calculate each component
        yield_curve_score, yield_curve_detail = self.calculate_yield_curve_score()
        duration_risk_score, duration_risk_detail = self.calculate_price_momentum_score()
        real_rates_score, real_rates_detail = self.calculate_real_rates_score()
        credit_quality_score, credit_quality_detail = self.calculate_credit_spreads_score()
        bond_vol_score, bond_vol_detail = self.calculate_bond_volatility_score()
        equity_bonds_score, equity_bonds_detail = self.calculate_equity_vs_bonds_score()

        # Store components (6 bond-specific indicators)
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
            'credit_quality': {
                'score': round(credit_quality_score, 1),
                'weight': weights['credit_quality'],
                'detail': credit_quality_detail
            },
            'real_rates': {
                'score': round(real_rates_score, 1),
                'weight': weights['real_rates'],
                'detail': real_rates_detail
            },
            'bond_volatility': {
                'score': round(bond_vol_score, 1),
                'weight': weights['bond_volatility'],
                'detail': bond_vol_detail
            },
            'equity_vs_bonds': {
                'score': round(equity_bonds_score, 1),
                'weight': weights['equity_vs_bonds'],
                'detail': equity_bonds_detail
            }
        }

        # Calculate weighted average (6 components)
        total_score = (
            yield_curve_score * weights['yield_curve'] +
            duration_risk_score * weights['duration_risk'] +
            credit_quality_score * weights['credit_quality'] +
            real_rates_score * weights['real_rates'] +
            bond_vol_score * weights['bond_volatility'] +
            equity_bonds_score * weights['equity_vs_bonds']
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

        print(f"Bonds Index calculated: {self.score} ({self.label})")

        return {
            'score': self.score,
            'label': self.label,
            'components': self.components,
            'timestamp': datetime.now().isoformat(),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M UTC')
        }

    def calculate_simple_historical_score(self, target_date: datetime) -> tuple:
        """
        Calculate COMPLETE historical score for a past date
        Uses 6 components: Yield Curve, TLT Momentum, Credit, Real Rates, Bond Vol, Equity vs Bonds

        Args:
            target_date: The date to calculate the score for

        Returns:
            Tuple of (score 0-100, price of TLT)
        """
        try:
            print(f"  Calculating for {target_date.strftime('%Y-%m-%d')}...", end=" ")

            # Fetch historical data up to target date
            start_date = target_date - timedelta(days=90)
            end_date = target_date + timedelta(days=1)

            # Get historical data for ALL components
            tlt = yf.Ticker("TLT")
            lqd = yf.Ticker("LQD")
            spy = yf.Ticker("SPY")

            tlt_hist = tlt.history(start=start_date, end=end_date)
            lqd_hist = lqd.history(start=start_date, end=end_date)
            spy_hist = spy.history(start=start_date, end=end_date)

            if tlt_hist.empty or len(tlt_hist) < 20:
                print("insufficient data")
                return 50.0, None

            # 1. TLT PRICE MOMENTUM (30% weight - PRIMARY)
            if len(tlt_hist) >= 15:
                pct_change_14d = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                price_momentum_score = 50 + (pct_change_14d * 15)
                price_momentum_score = max(0, min(100, price_momentum_score))
            else:
                price_momentum_score = 50.0

            # 2. CREDIT QUALITY (20% weight) - LQD vs TLT
            if len(lqd_hist) >= 15 and len(tlt_hist) >= 15:
                lqd_change = ((lqd_hist['Close'].iloc[-1] / lqd_hist['Close'].iloc[-15]) - 1) * 100
                tlt_change_credit = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                spread = lqd_change - tlt_change_credit
                credit_spreads_score = 50 + (spread * 20)
                credit_spreads_score = max(0, min(100, credit_spreads_score))
            else:
                credit_spreads_score = 50.0

            # 3. YIELD CURVE (25% weight) - DIRECT (term premium logic)
            try:
                tnx = yf.Ticker("^TNX")
                irx = yf.Ticker("^IRX")
                tnx_hist = tnx.history(start=start_date, end=end_date)
                irx_hist = irx.history(start=start_date, end=end_date)

                if len(tnx_hist) > 0 and len(irx_hist) > 0:
                    yield_10y = tnx_hist['Close'].iloc[-1]
                    yield_short = irx_hist['Close'].iloc[-1]
                    spread = yield_10y - yield_short

                    # Steep = high term premium = greed, Inverted = fear
                    yield_curve_score = 50 + (spread * 30)
                    yield_curve_score = max(0, min(100, yield_curve_score))
                else:
                    yield_curve_score = 50.0
            except Exception:
                yield_curve_score = 50.0

            # 4. REAL RATES (15% weight) - Nominal yield fallback for historical
            try:
                if len(tnx_hist) > 0:
                    nominal_yield = tnx_hist['Close'].iloc[-1]
                    # Higher yield = bond prices fall = FEAR (low score)
                    # Centered on 4.0% (current regime avg for nominal)
                    real_rates_score = 50 - (nominal_yield - 4.0) * 20
                    real_rates_score = max(0, min(100, real_rates_score))
                else:
                    real_rates_score = 50.0
            except Exception:
                real_rates_score = 50.0

            # 5. BOND VOLATILITY (15% weight) - TLT vol proxy for MOVE
            returns = tlt_hist['Close'].pct_change().dropna()
            if len(returns) >= 30:
                vol_5d = returns.tail(5).std() * np.sqrt(252) * 100
                vol_30d = returns.tail(30).std() * np.sqrt(252) * 100
                ratio = vol_5d / vol_30d if vol_30d > 0 else 1.0
                bond_vol_score = 50 + (1 - ratio) * 75
                bond_vol_score = max(0, min(100, bond_vol_score))
            else:
                bond_vol_score = 50.0

            # 6. EQUITY VS BONDS (10% weight) - TLT vs SPY rotation
            if len(tlt_hist) >= 15 and len(spy_hist) >= 15:
                tlt_change_rot = ((tlt_hist['Close'].iloc[-1] / tlt_hist['Close'].iloc[-15]) - 1) * 100
                spy_change = ((spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-15]) - 1) * 100
                relative_perf = tlt_change_rot - spy_change
                equity_bonds_score = 50 + (relative_perf * 8)
                equity_bonds_score = max(0, min(100, equity_bonds_score))
            else:
                equity_bonds_score = 50.0

            # Weighted average (6 components, Duration Risk primary)
            total_score = (
                price_momentum_score * 0.30 +
                yield_curve_score * 0.20 +
                credit_spreads_score * 0.20 +
                real_rates_score * 0.15 +
                bond_vol_score * 0.10 +
                equity_bonds_score * 0.05
            )

            # Get TLT price for this date
            tlt_price = round(float(tlt_hist['Close'].iloc[-1]), 2) if len(tlt_hist) > 0 else None

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1), tlt_price

        except Exception as e:
            print(f"error: {e}")
            return 50.0, None

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
                    if not self.score:
                        self.calculate_index()
                    score = self.score
                    label = self.label
                    # Fetch today's TLT price
                    try:
                        tlt = yf.Ticker("TLT")
                        ph = tlt.history(period="5d")
                        price = round(float(ph['Close'].iloc[-1]), 2)
                    except Exception:
                        price = None
                else:
                    # Calculate simplified historical score
                    score, price = self.calculate_simple_historical_score(historical_date)
                    rounded = round(score)
                    if rounded <= 25:
                        label = "Extreme Fear"
                    elif rounded <= 45:
                        label = "Fear"
                    elif rounded <= 55:
                        label = "Neutral"
                    elif rounded <= 75:
                        label = "Greed"
                    else:
                        label = "Extreme Greed"

                entry = {
                    'date': date_str,
                    'score': round(score, 1),
                    'label': label
                }
                if price is not None:
                    entry['price'] = price
                history.append(entry)

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

            # Fetch today's TLT price
            try:
                tlt = yf.Ticker("TLT")
                ph = tlt.history(period="5d")
                today_price = round(float(ph['Close'].iloc[-1]), 2)
            except Exception:
                today_price = None

            # Add new entry
            entry = {
                'date': today,
                'score': self.score,
                'label': self.label
            }
            if today_price is not None:
                entry['price'] = today_price
            history.append(entry)

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
