"""Tests for CryptoFearGreedIndex."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from crypto_fear_greed import CryptoFearGreedIndex
from conftest import make_price_history, default_ticker_factory


class TestCryptoIndex:

    # --- Full index tests ---

    @patch('yfinance.Ticker')
    def test_calculate_index_structure(self, mock_ticker):
        """Result dict has all required keys and 5 components."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = CryptoFearGreedIndex()
        result = calc.calculate_index()

        assert 'score' in result
        assert 'label' in result
        assert 'timestamp' in result
        assert 'components' in result
        assert set(result['components'].keys()) == {
            'context', 'momentum', 'dominance', 'volume', 'volatility'
        }

    @patch('yfinance.Ticker')
    def test_all_scores_in_range(self, mock_ticker):
        """All component scores and total score in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = CryptoFearGreedIndex()
        result = calc.calculate_index()

        for name, comp in result['components'].items():
            assert 0 <= comp['score'] <= 100, f"{name} score out of range: {comp['score']}"
        assert 0 <= result['score'] <= 100

    @patch('yfinance.Ticker')
    def test_weights_sum_to_one(self, mock_ticker):
        """Component weights must sum to 1.0."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = CryptoFearGreedIndex()
        result = calc.calculate_index()

        total = sum(c['weight'] for c in result['components'].values())
        assert abs(total - 1.0) < 0.001

    @patch('yfinance.Ticker')
    def test_label_matches_score(self, mock_ticker):
        """Label consistent with score."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = CryptoFearGreedIndex()
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

    # --- Context tests ---

    @patch('yfinance.Ticker')
    def test_context_strong_uptrend(self, mock_ticker):
        """BTC +30% in 30 days -> score near 100."""
        # 31 days at 100, then 29 days at 130 -> iloc[-30]=100, iloc[-1]=130
        prices = [100.0] * 31 + [130.0] * 29
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_context_score()

        assert score > 80

    @patch('yfinance.Ticker')
    def test_context_strong_downtrend(self, mock_ticker):
        """BTC -30% in 30 days -> score near 0."""
        prices = [100.0] * 31 + [70.0] * 29
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_context_score()

        assert score < 20

    # --- Dominance test ---

    @patch('yfinance.Ticker')
    def test_dominance_btc_outperforms_eth(self, mock_ticker):
        """BTC outperforms ETH -> dominance rising -> fear -> score < 50."""
        overrides = {
            'BTC-USD': make_price_history([100.0] * 14 + [105, 108, 110, 112, 114, 116]),
            'ETH-USD': make_price_history([100.0] * 20),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_btc_dominance_score()

        assert score < 50

    # --- Volatility tests ---

    @patch('yfinance.Ticker')
    def test_volatility_high(self, mock_ticker):
        """Extreme volatility (alternating prices) -> score near 0."""
        # Wild swings: annualized vol will be >> 80%
        prices = [80.0, 120.0] * 30
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_volatility_score()

        assert score == 0

    @patch('yfinance.Ticker')
    def test_volatility_low(self, mock_ticker):
        """Near-zero volatility (flat prices) -> score = 100."""
        prices = [100.0] * 60
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_volatility_score()

        assert score == 100

    # --- Volume trend tests ---

    @patch('yfinance.Ticker')
    def test_volume_trend_bullish(self, mock_ticker):
        """Volume up + price up -> greed -> score > 50."""
        prices = [90.0] * 53 + [91, 92, 93, 94, 95, 96, 97]
        volumes = [1_000_000] * 53 + [2_000_000] * 7
        mock_ticker.return_value.history.return_value = make_price_history(prices, volumes)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_volume_trend_score()

        assert score > 50

    @patch('yfinance.Ticker')
    def test_volume_trend_bearish(self, mock_ticker):
        """Volume up + price down -> panic selling -> score < 50."""
        prices = [97.0] * 53 + [96, 95, 94, 93, 92, 91, 90]
        volumes = [1_000_000] * 53 + [2_000_000] * 7
        mock_ticker.return_value.history.return_value = make_price_history(prices, volumes)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_volume_trend_score()

        assert score < 50

    # --- Momentum test ---

    @patch('yfinance.Ticker')
    def test_momentum_score_in_range(self, mock_ticker):
        """Momentum (RSI + MA) score should be in [0, 100]."""
        prices = [100 + i * 0.2 for i in range(250)]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = CryptoFearGreedIndex()
        score, _ = calc.calculate_momentum_score()

        assert 0 <= score <= 100

    # --- Error handling ---

    @patch('yfinance.Ticker', side_effect=Exception('Network error'))
    def test_component_error_returns_50(self, mock_ticker):
        """All components return 50.0 (not 30.0) on error."""
        calc = CryptoFearGreedIndex()

        for method_name in [
            'calculate_context_score',
            'calculate_momentum_score',
            'calculate_btc_dominance_score',
            'calculate_volume_trend_score',
            'calculate_volatility_score',
        ]:
            score, _ = getattr(calc, method_name)()
            assert score == 50.0, f"{method_name} didn't fallback to 50.0"

    # --- Historical ---

    @patch('yfinance.Ticker')
    def test_historical_score_in_range(self, mock_ticker):
        """calculate_simple_historical_score returns float in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = CryptoFearGreedIndex()
        score = calc.calculate_simple_historical_score(datetime(2025, 1, 15))

        assert isinstance(score, float)
        assert 0 <= score <= 100
