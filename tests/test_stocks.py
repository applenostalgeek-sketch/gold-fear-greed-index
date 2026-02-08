"""Tests for StocksFearGreedIndex."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from stocks_fear_greed import StocksFearGreedIndex
from conftest import make_price_history, default_ticker_factory


class TestStocksIndex:

    # --- Full index tests ---

    @patch('yfinance.Ticker')
    def test_calculate_index_structure(self, mock_ticker):
        """Result dict has all required keys and 7 components."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = StocksFearGreedIndex()
        result = calc.calculate_index()

        assert 'score' in result
        assert 'label' in result
        assert 'timestamp' in result
        assert 'components' in result
        assert set(result['components'].keys()) == {
            'price_strength', 'vix', 'momentum', 'market_participation',
            'junk_bonds', 'safe_haven', 'sector_rotation'
        }

    @patch('yfinance.Ticker')
    def test_all_scores_in_range(self, mock_ticker):
        """All component scores and total score in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = StocksFearGreedIndex()
        result = calc.calculate_index()

        for name, comp in result['components'].items():
            assert 0 <= comp['score'] <= 100, f"{name} score out of range: {comp['score']}"
        assert 0 <= result['score'] <= 100

    @patch('yfinance.Ticker')
    def test_weights_sum_to_one(self, mock_ticker):
        """Component weights must sum to 1.0."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = StocksFearGreedIndex()
        result = calc.calculate_index()

        total = sum(c['weight'] for c in result['components'].values())
        assert abs(total - 1.0) < 0.001

    @patch('yfinance.Ticker')
    def test_label_matches_score(self, mock_ticker):
        """Label consistent with score."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = StocksFearGreedIndex()
        result = calc.calculate_index()
        score, label = result['score'], result['label']

        if score <= 25:
            assert label == 'Extreme Fear'
        elif score <= 45:
            assert label == 'Fear'
        elif score <= 55:
            assert label == 'Neutral'
        elif score <= 75:
            assert label == 'Greed'
        else:
            assert label == 'Extreme Greed'

    # --- VIX continuous formula test ---

    @patch('yfinance.Ticker')
    def test_vix_continuous_at_20(self, mock_ticker):
        """VIX = 20 -> score ~ 58 (continuous formula)."""
        mock_ticker.return_value.history.return_value = make_price_history([20.0] * 60)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_vix_score()

        # Formula: 90 - (20 - 10) * 3.2 = 58.0
        assert abs(score - 58.0) < 1

    @patch('yfinance.Ticker')
    def test_vix_continuous_at_30(self, mock_ticker):
        """VIX = 30 -> score ~ 26 (continuous formula)."""
        mock_ticker.return_value.history.return_value = make_price_history([30.0] * 60)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_vix_score()

        # Formula: 90 - (30 - 10) * 3.2 = 26.0
        assert abs(score - 26.0) < 1

    # --- Component directional tests ---

    @patch('yfinance.Ticker')
    def test_price_strength_bullish(self, mock_ticker):
        """SPY rising -> score > 50."""
        prices = [100.0] * 14 + [101, 102, 103, 104, 105, 106]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_price_strength_score()

        assert score > 50

    @patch('yfinance.Ticker')
    def test_market_participation_broad(self, mock_ticker):
        """RSP outperforms SPY -> broad participation -> score > 50."""
        overrides = {
            'SPY': make_price_history([100.0] * 20),
            'RSP': make_price_history([100.0] * 14 + [101, 102, 103, 104, 105, 106]),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_market_participation_score()

        assert score > 50

    @patch('yfinance.Ticker')
    def test_junk_bond_risk_on(self, mock_ticker):
        """HYG outperforms TLT -> risk-on -> score > 50."""
        overrides = {
            'HYG': make_price_history([100.0] * 14 + [101, 102, 103, 104, 105, 106]),
            'TLT': make_price_history([100.0] * 20),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_junk_bond_score()

        assert score > 50

    @patch('yfinance.Ticker')
    def test_safe_haven_flight(self, mock_ticker):
        """TLT rising (flight to safety) -> score < 50 for stocks."""
        prices = [100.0] * 26 + [102, 104, 106, 108]  # 30 data points
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_safe_haven_score()

        assert score < 50

    @patch('yfinance.Ticker')
    def test_sector_rotation_risk_on(self, mock_ticker):
        """QQQ outperforms XLP -> risk-on -> score > 50."""
        overrides = {
            'QQQ': make_price_history([100.0] * 14 + [103, 106, 109, 112, 115, 118]),
            'XLP': make_price_history([100.0] * 20),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = StocksFearGreedIndex()
        score, _ = calc.calculate_sector_rotation_score()

        assert score > 50

    # --- Error handling ---

    @patch('yfinance.Ticker', side_effect=Exception('Network error'))
    def test_component_error_returns_50(self, mock_ticker):
        """All components return (50.0, ...) on error."""
        calc = StocksFearGreedIndex()

        for method_name in [
            'calculate_price_strength_score',
            'calculate_vix_score',
            'calculate_momentum_score',
            'calculate_market_participation_score',
            'calculate_junk_bond_score',
            'calculate_safe_haven_score',
            'calculate_sector_rotation_score',
        ]:
            score, _ = getattr(calc, method_name)()
            assert score == 50.0, f"{method_name} didn't fallback to 50.0"

    # --- Historical ---

    @patch('yfinance.Ticker')
    def test_historical_score_in_range(self, mock_ticker):
        """calculate_simple_historical_score returns float in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = StocksFearGreedIndex()
        score = calc.calculate_simple_historical_score(datetime(2025, 1, 15))

        assert isinstance(score, float)
        assert 0 <= score <= 100
