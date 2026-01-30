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
        Primary: 10Y TIPS via FRED API
        Fallback: Calculate from nominal yields and inflation expectations

        Returns:
            Tuple of (score 0-100, detail string)
        """
        # Try FRED API first
        if self.fred_api_key:
            try:
                # FRED series for 10Y TIPS
                url = f"https://api.stlouisfed.org/fred/series/observations"
                params = {
                    'series_id': 'DFII10',  # 10-Year Treasury Inflation-Indexed Security
                    'api_key': self.fred_api_key,
                    'file_type': 'json',
                    'sort_order': 'desc',
                    'limit': 30
                }

                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()

                # Check for API errors
                if 'error_message' in data:
                    print(f"FRED API error: {data['error_message']}")
                    raise ValueError(f"FRED API error: {data['error_message']}")

                if 'observations' not in data or len(data['observations']) == 0:
                    raise ValueError("No TIPS observations in response")

                # Get latest non-null value
                tips_rate = None
                for obs in data['observations']:
                    if obs['value'] != '.':
                        tips_rate = float(obs['value'])
                        break

                if tips_rate is None:
                    raise ValueError("All TIPS values are null")

                # Calculate average from valid observations
                valid_obs = [float(obs['value']) for obs in data['observations']
                            if obs['value'] != '.']
                avg_tips = np.mean(valid_obs) if valid_obs else tips_rate

                # Score: lower real rates = higher gold appeal = higher score
                # Real rate at -1% = 100, at 3% = 0
                score = 75 - (tips_rate * 18.75)
                score = max(0, min(100, score))

                detail = f"TIPS 10Y: {tips_rate:.2f}% (avg: {avg_tips:.2f}%)"

                return score, detail

            except Exception as e:
                print(f"FRED API failed ({type(e).__name__}: {e}), using fallback...")

        # Fallback: Use TNX (10Y Treasury Yield) as proxy
        # Lower nominal yields generally = more gold appeal
        try:
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="3mo")

            if hist.empty:
                raise ValueError("No TNX data")

            current_yield = hist['Close'].iloc[-1]
            avg_yield = hist['Close'].mean()

            # Score: lower yields = higher score (more gold demand)
            # Yield at 2% = 100, at 6% = 0
            score = 100 - ((current_yield - 2) * 25)
            score = max(0, min(100, score))

            detail = f"10Y Yield: {current_yield:.2f}% (proxy, avg: {avg_yield:.2f}%)"

            return score, detail

        except Exception as e:
            print(f"Error calculating real rates (all methods): {e}")
            return 50.0, "Data unavailable"

    def calculate_dollar_index_score(self) -> Tuple[float, str]:
        """
        Calculate Dollar Index component (10% weight)
        DXY measures USD strength vs basket of currencies
        Inverse correlation: Weak dollar = Strong gold = Higher score

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            dxy = yf.Ticker("DX-Y.NYB")  # US Dollar Index
            hist = dxy.history(period="3mo")

            if hist.empty:
                raise ValueError("No DXY data available")

            current_dxy = hist['Close'].iloc[-1]

            # Calculate 30-day moving average
            ma_30 = hist['Close'].tail(30).mean()

            # Calculate 14-day change
            if len(hist) >= 14:
                dxy_14d_ago = hist['Close'].iloc[-14]
                dxy_change = ((current_dxy - dxy_14d_ago) / dxy_14d_ago) * 100
            else:
                dxy_change = 0

            # Score: Dollar FALLS = Gold RISES = Higher score
            # DXY down 5% = 100, DXY up 5% = 0
            score = 50 - (dxy_change * 10)
            score = max(0, min(100, score))

            detail = f"DXY: {current_dxy:.2f} ({dxy_change:+.1f}% 14d, MA30: {ma_30:.2f})"

            return score, detail

        except Exception as e:
            print(f"Error calculating Dollar Index: {e}")
            return 50.0, "Data unavailable"

    def calculate_index(self) -> Dict:
        """
        Calculate the complete Gold Fear & Greed Index

        Returns:
            Dictionary with score, label, components, and history
        """
        # Define weights (total must equal 1.0)
        weights = {
            'volatility': 0.15,      # Reduced from 0.20
            'momentum': 0.25,        # Unchanged - most important
            'gold_vs_spy': 0.15,     # Unchanged
            'etf_flows': 0.15,       # Reduced from 0.20
            'vix': 0.10,             # Unchanged
            'real_rates': 0.10,      # Unchanged
            'dollar_index': 0.10     # NEW - critical for gold
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

        dxy_score, dxy_detail = self.calculate_dollar_index_score()
        print(f"Dollar Index: {dxy_score:.1f} - {dxy_detail}")

        # Calculate weighted average
        total_score = (
            vol_score * weights['volatility'] +
            momentum_score * weights['momentum'] +
            gold_spy_score * weights['gold_vs_spy'] +
            etf_score * weights['etf_flows'] +
            vix_score * weights['vix'] +
            real_rates_score * weights['real_rates'] +
            dxy_score * weights['dollar_index']
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
            },
            'dollar_index': {
                'score': round(dxy_score, 1),
                'weight': weights['dollar_index'],
                'detail': dxy_detail
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
            gold = yf.Ticker("GC=F")
            spy = yf.Ticker("SPY")
            vix = yf.Ticker("^VIX")
            dxy = yf.Ticker("DX-Y.NYB")

            gold_hist = gold.history(start=start_date, end=end_date + timedelta(days=1))
            spy_hist = spy.history(start=start_date, end=end_date + timedelta(days=1))
            vix_hist = vix.history(start=start_date, end=end_date + timedelta(days=1))
            dxy_hist = dxy.history(start=start_date, end=end_date + timedelta(days=1))

            if len(gold_hist) < 20 or len(spy_hist) < 20:
                print("insufficient data")
                return 50.0

            # Calculate Gold vs SPY (30% weight)
            gold_return = (gold_hist['Close'].iloc[-1] / gold_hist['Close'].iloc[-14] - 1) * 100
            spy_return = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-14] - 1) * 100
            relative_perf = gold_return - spy_return
            gold_spy_score = 50 + (relative_perf * 2.5)
            gold_spy_score = max(0, min(100, gold_spy_score))

            # Calculate Momentum (30% weight)
            close_prices = gold_hist['Close']
            if len(close_prices) >= 50:
                ma50 = close_prices.rolling(window=50).mean().iloc[-1]
                current_price = close_prices.iloc[-1]

                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]

                ma_score = 40 if current_price > ma50 else 0
                rsi_score = current_rsi * 0.6
                momentum_score = ma_score + rsi_score
            else:
                momentum_score = 50

            # Calculate VIX (15% weight)
            if len(vix_hist) > 0:
                current_vix = vix_hist['Close'].iloc[-1]
                vix_score = (current_vix - 10) * 3.33
                vix_score = max(0, min(100, vix_score))
            else:
                vix_score = 50

            # Calculate Dollar Index (25% weight)
            if len(dxy_hist) >= 14:
                current_dxy = dxy_hist['Close'].iloc[-1]
                dxy_14d_ago = dxy_hist['Close'].iloc[-14]
                dxy_change = ((current_dxy - dxy_14d_ago) / dxy_14d_ago) * 100
                dxy_score = 50 - (dxy_change * 10)
                dxy_score = max(0, min(100, dxy_score))
            else:
                dxy_score = 50

            # Weighted average (simplified for historical calculation)
            total_score = (
                gold_spy_score * 0.30 +
                momentum_score * 0.30 +
                vix_score * 0.15 +
                dxy_score * 0.25
            )

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1)

        except Exception as e:
            print(f"error: {e}")
            return 50.0

    def save_to_file(self, filepath: str = 'data/gold-fear-greed.json', force_rebuild: bool = False):
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

            print(f"\n✅ Index saved to {filepath} with {len(history)} days of history")

        except Exception as e:
            print(f"Error saving to file: {e}")


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description='Calculate Gold Fear & Greed Index')
    parser.add_argument('--force-rebuild', action='store_true',
                        help='Force rebuild all 365 days of history (slow, 2-3 minutes)')
    args = parser.parse_args()

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
    calculator.save_to_file('data/gold-fear-greed.json', force_rebuild=args.force_rebuild)


if __name__ == "__main__":
    main()
