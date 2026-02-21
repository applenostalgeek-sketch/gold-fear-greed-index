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
        fred_key = fred_api_key or os.environ.get('FRED_API_KEY')
        self.fred_api_key = fred_key.strip() if fred_key else None
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

            # Scoring - proportional to distance from MAs + RSI
            # Base 50 (neutral), MA contribution ±25, RSI contribution ±25

            # MA50 distance contribution (max ±15 points)
            ma50_pct = ((current_price - ma50) / ma50) * 100
            ma50_contrib = max(-15, min(15, ma50_pct * 1.5))

            # MA200 distance contribution (max ±10 points)
            ma200_pct = ((current_price - ma200) / ma200) * 100
            ma200_contrib = max(-10, min(10, ma200_pct * 0.5))

            # RSI contribution (max ±25 points)
            # RSI 50 = 0, RSI 70 = +10, RSI 80 = +15, RSI 30 = -10
            rsi_contrib = (current_rsi - 50) * 0.5
            rsi_contrib = max(-25, min(25, rsi_contrib))

            total_score = 50 + ma50_contrib + ma200_contrib + rsi_contrib
            total_score = max(0, min(100, total_score))

            ma_status = "Price > MA50" if current_price > ma50 else "Price < MA50"
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

    def calculate_gld_price_momentum_score(self) -> Tuple[float, str]:
        """
        Calculate GLD Price Momentum component (25% weight)
        Direct measurement of GLD ETF performance over 14 days
        Primary indicator: captures actual buying/selling sentiment

        Returns:
            Tuple of (score 0-100, detail string)
        """
        try:
            gld = yf.Ticker("GLD")
            hist = gld.history(period="1mo")

            if len(hist) < 14:
                raise ValueError("Insufficient GLD data")

            # Calculate 14-day price change
            recent_price_change = (hist['Close'].iloc[-1] / hist['Close'].iloc[-14] - 1) * 100

            # Scoring: GLD +10% = score 100, GLD -10% = score 0
            # Multiplier 5 avoids saturation (old multiplier 7 saturated at ±7.1%)
            score = 50 + (recent_price_change * 5)
            score = max(0, min(100, score))

            detail = f"GLD 14d: {recent_price_change:+.1f}%"

            return score, detail

        except Exception as e:
            print(f"Error calculating GLD price momentum: {e}")
            return 50.0, "Data unavailable"

    def calculate_vix_score(self) -> Tuple[float, str]:
        """
        Calculate VIX component (10% weight)
        Uses z-score vs 3-month average for context-aware scoring
        High VIX = market fear = people buy gold = greed for gold = high score

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
            std_vix = hist['Close'].std()

            # Z-score approach: contextualizes VIX relative to recent history
            # VIX 1 std above avg = score 75, 2 std above = 100
            # VIX 1 std below avg = score 25, 2 std below = 0
            if std_vix > 0:
                z_score = (current_vix - avg_vix) / std_vix
            else:
                z_score = 0

            score = 50 + (z_score * 25)
            score = max(0, min(100, score))

            detail = f"VIX: {current_vix:.1f} (avg: {avg_vix:.1f}, z: {z_score:+.1f})"

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
            # DXY down 3.3% = 100, DXY up 3.3% = 0
            # Multiplier 15 adapted to DXY's lower volatility vs gold
            score = 50 - (dxy_change * 15)
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
        # PHILOSOPHY: Measure sentiment TOWARDS gold (like Alternative.me measures sentiment towards crypto)
        weights = {
            'gld_price': 0.30,       # PRIMARY: Direct GLD performance = buying sentiment
            'momentum': 0.25,        # RSI + MA mean-reversion signal
            'dollar_index': 0.20,    # Dollar inverse correlation
            'real_rates': 0.15,      # Critical macro factor for gold
            'vix': 0.10,             # Safe haven demand indicator (z-score)
        }

        # Calculate each component
        print("Calculating RECALIBRATED Gold Fear & Greed Index v2...")
        print("(Philosophy: Measure sentiment TOWARDS gold)")

        gld_price_score, gld_price_detail = self.calculate_gld_price_momentum_score()
        print(f"GLD Price (30%): {gld_price_score:.1f} - {gld_price_detail}")

        momentum_score, momentum_detail = self.calculate_momentum_score()
        print(f"RSI/MA Momentum (25%): {momentum_score:.1f} - {momentum_detail}")

        dxy_score, dxy_detail = self.calculate_dollar_index_score()
        print(f"Dollar Index (20%): {dxy_score:.1f} - {dxy_detail}")

        real_rates_score, real_rates_detail = self.calculate_real_rates_score()
        print(f"Real Rates (15%): {real_rates_score:.1f} - {real_rates_detail}")

        vix_score, vix_detail = self.calculate_vix_score()
        print(f"VIX (10%): {vix_score:.1f} - {vix_detail}")

        # Calculate weighted average
        total_score = (
            gld_price_score * weights['gld_price'] +
            momentum_score * weights['momentum'] +
            dxy_score * weights['dollar_index'] +
            real_rates_score * weights['real_rates'] +
            vix_score * weights['vix']
        )

        # Build components dictionary
        components = {
            'gld_price': {
                'score': round(gld_price_score, 1),
                'weight': weights['gld_price'],
                'detail': gld_price_detail
            },
            'momentum': {
                'score': round(momentum_score, 1),
                'weight': weights['momentum'],
                'detail': momentum_detail
            },
            'dollar_index': {
                'score': round(dxy_score, 1),
                'weight': weights['dollar_index'],
                'detail': dxy_detail
            },
            'real_rates': {
                'score': round(real_rates_score, 1),
                'weight': weights['real_rates'],
                'detail': real_rates_detail
            },
            'vix': {
                'score': round(vix_score, 1),
                'weight': weights['vix'],
                'detail': vix_detail
            }
        }

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

    def calculate_simple_historical_score(self, target_date: datetime) -> tuple:
        """
        Calculate COMPLETE historical score for a past date
        Uses 5 RECALIBRATED components: GLD Price, RSI/MA, DXY, Real Rates, VIX

        Args:
            target_date: The date to calculate the score for

        Returns:
            Tuple of (score 0-100, price of GLD)
        """
        try:
            print(f"  Calculating for {target_date.strftime('%Y-%m-%d')}...", end=" ")

            # Fetch historical data up to target date
            end_date = target_date
            start_date = target_date - timedelta(days=250)  # Extended for MA200

            # Get historical data for ALL components
            gold = yf.Ticker("GC=F")
            vix = yf.Ticker("^VIX")
            dxy = yf.Ticker("DX-Y.NYB")
            gld = yf.Ticker("GLD")
            tnx = yf.Ticker("^TNX")

            gold_hist = gold.history(start=start_date, end=end_date + timedelta(days=1))
            vix_hist = vix.history(start=start_date, end=end_date + timedelta(days=1))
            dxy_hist = dxy.history(start=start_date, end=end_date + timedelta(days=1))
            gld_hist = gld.history(start=start_date, end=end_date + timedelta(days=1))
            tnx_hist = tnx.history(start=start_date, end=end_date + timedelta(days=1))

            if len(gold_hist) < 20:
                print("insufficient data")
                return 50.0, None

            # 1. GLD PRICE MOMENTUM (25% weight) - PRIMARY INDICATOR
            if len(gld_hist) >= 14:
                recent_price_change = (gld_hist['Close'].iloc[-1] / gld_hist['Close'].iloc[-14] - 1) * 100
                gld_price_score = 50 + (recent_price_change * 5)
                gld_price_score = max(0, min(100, gld_price_score))
            else:
                gld_price_score = 50.0

            # 2. RSI/MA MOMENTUM (25% weight) - Mean-reversion signal
            if len(gold_hist) >= 200:
                close_prices = gold_hist['Close']
                current_price = close_prices.iloc[-1]
                ma50 = close_prices.rolling(window=50).mean().iloc[-1]
                ma200 = close_prices.rolling(window=200).mean().iloc[-1]

                # RSI calculation
                delta = close_prices.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]

                ma50_pct = ((current_price - ma50) / ma50) * 100
                ma50_contrib = max(-15, min(15, ma50_pct * 1.5))
                ma200_pct = ((current_price - ma200) / ma200) * 100
                ma200_contrib = max(-10, min(10, ma200_pct * 0.5))
                rsi_contrib = max(-25, min(25, (current_rsi - 50) * 0.5))
                momentum_score = 50 + ma50_contrib + ma200_contrib + rsi_contrib
                momentum_score = max(0, min(100, momentum_score))
            else:
                momentum_score = 50.0

            # 3. DOLLAR INDEX (20% weight)
            if len(dxy_hist) >= 14:
                current_dxy = dxy_hist['Close'].iloc[-1]
                dxy_14d_ago = dxy_hist['Close'].iloc[-14]
                dxy_change = ((current_dxy - dxy_14d_ago) / dxy_14d_ago) * 100
                dxy_score = 50 - (dxy_change * 15)
                dxy_score = max(0, min(100, dxy_score))
            else:
                dxy_score = 50.0

            # 4. REAL RATES (20% weight) - Using FRED API for historical accuracy
            if self.fred_api_key:
                try:
                    date_str = target_date.strftime('%Y-%m-%d')
                    url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DFII10&api_key={self.fred_api_key}&file_type=json&observation_start={date_str}&observation_end={date_str}"

                    response = requests.get(url, timeout=10)

                    if response.status_code == 200:
                        data = response.json()

                        if data['observations'] and data['observations'][0]['value'] != '.':
                            tips_rate = float(data['observations'][0]['value'])
                            real_rates_score = 75 - (tips_rate * 18.75)
                            real_rates_score = max(0, min(100, real_rates_score))
                        else:
                            if len(tnx_hist) > 0:
                                current_yield = tnx_hist['Close'].iloc[-1]
                                real_rates_score = 100 - ((current_yield - 2) * 25)
                                real_rates_score = max(0, min(100, real_rates_score))
                            else:
                                real_rates_score = 50.0
                    else:
                        if len(tnx_hist) > 0:
                            current_yield = tnx_hist['Close'].iloc[-1]
                            real_rates_score = 100 - ((current_yield - 2) * 25)
                            real_rates_score = max(0, min(100, real_rates_score))
                        else:
                            real_rates_score = 50.0
                except Exception:
                    if len(tnx_hist) > 0:
                        current_yield = tnx_hist['Close'].iloc[-1]
                        real_rates_score = 100 - ((current_yield - 2) * 25)
                        real_rates_score = max(0, min(100, real_rates_score))
                    else:
                        real_rates_score = 50.0
            else:
                if len(tnx_hist) > 0:
                    current_yield = tnx_hist['Close'].iloc[-1]
                    real_rates_score = 100 - ((current_yield - 2) * 25)
                    real_rates_score = max(0, min(100, real_rates_score))
                else:
                    real_rates_score = 50.0

            # 5. VIX (10% weight) - Z-score vs 3-month average
            if len(vix_hist) > 10:
                current_vix = vix_hist['Close'].iloc[-1]
                avg_vix = vix_hist['Close'].mean()
                std_vix = vix_hist['Close'].std()
                if std_vix > 0:
                    z_score = (current_vix - avg_vix) / std_vix
                else:
                    z_score = 0
                vix_score = 50 + (z_score * 25)
                vix_score = max(0, min(100, vix_score))
            else:
                vix_score = 50.0

            # Weighted average with RECALIBRATED weights (5 components)
            total_score = (
                gld_price_score * 0.30 +
                momentum_score * 0.25 +
                dxy_score * 0.20 +
                real_rates_score * 0.15 +
                vix_score * 0.10
            )

            # Get GLD price for this date
            gld_price = round(float(gld_hist['Close'].iloc[-1]), 2) if len(gld_hist) > 0 else None

            print(f"Score: {total_score:.1f}")
            return round(total_score, 1), gld_price

        except Exception as e:
            print(f"error: {e}")
            return 50.0, None

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
                        # Fetch today's GLD price
                        try:
                            gld = yf.Ticker("GLD")
                            ph = gld.history(period="5d")
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

                # Fetch today's GLD price
                try:
                    gld = yf.Ticker("GLD")
                    ph = gld.history(period="5d")
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
