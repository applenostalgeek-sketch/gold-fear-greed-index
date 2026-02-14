"""Tests for GoldFearGreedIndex."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from gold_fear_greed import GoldFearGreedIndex
from conftest import make_price_history, make_fred_response, default_ticker_factory


class TestGoldIndex:

    # --- Full index tests ---

    @patch('requests.get')
    @patch('yfinance.Ticker')
    def test_calculate_index_structure(self, mock_ticker, mock_requests):
        """Result dict has all required keys and 5 components."""
        mock_ticker.side_effect = default_ticker_factory()
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        assert 'score' in result
        assert 'label' in result
        assert 'timestamp' in result
        assert 'components' in result
        assert set(result['components'].keys()) == {
            'gld_price', 'momentum', 'dollar_index', 'real_rates', 'vix'
        }

    @patch('requests.get')
    @patch('yfinance.Ticker')
    def test_all_scores_in_range(self, mock_ticker, mock_requests):
        """All component scores and total score must be in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        for name, comp in result['components'].items():
            assert 0 <= comp['score'] <= 100, f"{name} score out of range: {comp['score']}"
        assert 0 <= result['score'] <= 100

    @patch('requests.get')
    @patch('yfinance.Ticker')
    def test_weights_sum_to_one(self, mock_ticker, mock_requests):
        """Component weights must sum to 1.0."""
        mock_ticker.side_effect = default_ticker_factory()
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        total = sum(c['weight'] for c in result['components'].values())
        assert abs(total - 1.0) < 0.001

    @patch('requests.get')
    @patch('yfinance.Ticker')
    def test_label_matches_score(self, mock_ticker, mock_requests):
        """Label must be consistent with the computed score."""
        mock_ticker.side_effect = default_ticker_factory()
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()
        score, label = result['score'], result['label']

        rounded = round(score)
        if rounded <= 25:
            assert label == 'Extreme Fear'
        elif rounded <= 45:
            assert label == 'Fear'
        elif rounded <= 55:
            assert label == 'Neutral'
        elif rounded <= 75:
            assert label == 'Greed'
        else:
            assert label == 'Extreme Greed'

    # --- Individual component tests ---

    @patch('yfinance.Ticker')
    def test_gld_price_bullish(self, mock_ticker):
        """Rising GLD prices -> score > 50."""
        prices = [100.0] * 14 + [101, 102, 103, 104, 105, 106]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_gld_price_momentum_score()

        assert score > 50
        assert 0 <= score <= 100

    @patch('yfinance.Ticker')
    def test_gld_price_bearish(self, mock_ticker):
        """Falling GLD prices -> score < 50."""
        prices = [100.0] * 14 + [99, 98, 97, 96, 95, 94]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_gld_price_momentum_score()

        assert score < 50
        assert 0 <= score <= 100

    @patch('yfinance.Ticker')
    def test_vix_high_is_gold_greed(self, mock_ticker):
        """High VIX = safe haven demand = high score for gold."""
        # VIX at 15 for 50 days, then spikes to 35
        prices = [15.0] * 50 + [35.0] * 10
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_vix_score()

        assert score > 50

    @patch('yfinance.Ticker')
    def test_vix_low_is_gold_fear(self, mock_ticker):
        """Low VIX = less safe haven demand = low score for gold."""
        # VIX at 25 for 50 days, then drops to 12
        prices = [25.0] * 50 + [12.0] * 10
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_vix_score()

        assert score < 50

    @patch('yfinance.Ticker')
    def test_dollar_rising_bearish_for_gold(self, mock_ticker):
        """DXY rising -> bearish for gold -> score < 50."""
        # DXY goes from 100 to ~106 over last 14 days
        prices = [100.0] * 46 + [100 + i * 0.5 for i in range(14)]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_dollar_index_score()

        assert score < 50

    # --- FRED / fallback tests ---

    @patch('requests.get')
    def test_real_rates_fred_success(self, mock_requests):
        """FRED returns TIPS rate -> score uses FRED formula."""
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_real_rates_score()

        # Formula: 75 - (2.0 * 18.75) = 37.5
        assert score == 37.5
        assert 'TIPS' in detail

    @patch('yfinance.Ticker')
    @patch('requests.get', side_effect=Exception('FRED down'))
    def test_real_rates_fred_failure_yahoo_fallback(self, mock_requests, mock_ticker):
        """FRED fails -> falls back to Yahoo ^TNX."""
        # ^TNX returns yield of 4.0%
        mock_ticker.return_value.history.return_value = make_price_history([4.0] * 60)

        calc = GoldFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_real_rates_score()

        # Fallback formula: 100 - ((4.0 - 2) * 25) = 50.0
        assert score == 50.0

    @patch('yfinance.Ticker')
    @patch('requests.get', side_effect=Exception('FRED down'))
    def test_real_rates_total_failure(self, mock_requests, mock_ticker):
        """Both FRED and Yahoo fail -> score = 50.0."""
        mock_ticker.return_value.history.return_value = pd.DataFrame()  # empty

        calc = GoldFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_real_rates_score()

        assert score == 50.0
        assert 'unavailable' in detail.lower()

    @patch('yfinance.Ticker')
    def test_momentum_score_in_range(self, mock_ticker):
        """Momentum (RSI + MA) score should be in [0, 100]."""
        # Steady uptrend for 250 days
        prices = [100 + i * 0.1 for i in range(250)]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = GoldFearGreedIndex()
        score, _ = calc.calculate_momentum_score()

        assert 0 <= score <= 100

    # --- Error handling ---

    @patch('yfinance.Ticker', side_effect=Exception('Network error'))
    def test_component_error_returns_50(self, mock_ticker):
        """All components return (50.0, ...) when data fetch fails."""
        calc = GoldFearGreedIndex()

        for method_name in [
            'calculate_gld_price_momentum_score',
            'calculate_vix_score',
            'calculate_dollar_index_score',
            'calculate_momentum_score',
            'calculate_volatility_score',
        ]:
            score, _ = getattr(calc, method_name)()
            assert score == 50.0, f"{method_name} didn't fallback to 50.0"

    # --- Historical ---

    @patch('requests.get')
    @patch('yfinance.Ticker')
    def test_historical_score_in_range(self, mock_ticker, mock_requests):
        """calculate_simple_historical_score returns float in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()
        mock_requests.return_value = make_fred_response(2.0)

        calc = GoldFearGreedIndex(fred_api_key='test')
        score = calc.calculate_simple_historical_score(datetime(2025, 1, 15))

        assert isinstance(score, float)
        assert 0 <= score <= 100
