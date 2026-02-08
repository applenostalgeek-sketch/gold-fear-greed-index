"""Tests for BondsFearGreedIndex."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from bonds_fear_greed import BondsFearGreedIndex
from conftest import make_price_history, make_fred_response, default_ticker_factory


def bonds_fred_side_effect(url, **kwargs):
    """Mock requests.get for bonds FRED calls (series_id in URL)."""
    url_str = str(url)
    if 'DGS2' in url_str:
        return make_fred_response(4.0)   # 2Y yield
    elif 'DGS10' in url_str:
        return make_fred_response(4.5)   # 10Y yield
    elif 'DFII10' in url_str:
        return make_fred_response(2.0)   # Real rate
    return make_fred_response(0)


class TestBondsIndex:

    # --- Full index tests ---

    @patch('requests.get', side_effect=bonds_fred_side_effect)
    @patch('yfinance.Ticker')
    def test_calculate_index_structure(self, mock_ticker, mock_requests):
        """Result dict has all required keys and 6 components."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = BondsFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        assert 'score' in result
        assert 'label' in result
        assert 'components' in result
        assert set(result['components'].keys()) == {
            'yield_curve', 'duration_risk', 'credit_quality',
            'real_rates', 'bond_volatility', 'equity_vs_bonds'
        }

    @patch('requests.get', side_effect=bonds_fred_side_effect)
    @patch('yfinance.Ticker')
    def test_all_scores_in_range(self, mock_ticker, mock_requests):
        """All component scores and total score in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = BondsFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        for name, comp in result['components'].items():
            assert 0 <= comp['score'] <= 100, f"{name} score out of range: {comp['score']}"
        assert 0 <= result['score'] <= 100

    @patch('requests.get', side_effect=bonds_fred_side_effect)
    @patch('yfinance.Ticker')
    def test_weights_sum_to_one(self, mock_ticker, mock_requests):
        """Component weights must sum to 1.0."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = BondsFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()

        total = sum(c['weight'] for c in result['components'].values())
        assert abs(total - 1.0) < 0.001

    @patch('requests.get', side_effect=bonds_fred_side_effect)
    @patch('yfinance.Ticker')
    def test_label_matches_score(self, mock_ticker, mock_requests):
        """Label consistent with score (bonds uses < thresholds)."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = BondsFearGreedIndex(fred_api_key='test')
        result = calc.calculate_index()
        score, label = result['score'], result['label']

        # Bonds uses < (not <=) for thresholds
        if score < 25:
            assert label == 'Extreme Fear'
        elif score < 45:
            assert label == 'Fear'
        elif score < 55:
            assert label == 'Neutral'
        elif score < 75:
            assert label == 'Greed'
        else:
            assert label == 'Extreme Greed'

    # --- Yield curve tests ---

    @patch('requests.get')
    def test_yield_curve_inverted(self, mock_requests):
        """Inverted curve (2Y > 10Y) -> high score (bonds greed)."""
        def mock_fred(url, **kwargs):
            if 'DGS2' in str(url):
                return make_fred_response(5.0)  # 2Y = 5%
            elif 'DGS10' in str(url):
                return make_fred_response(4.0)  # 10Y = 4%
            return make_fred_response(0)

        mock_requests.side_effect = mock_fred

        calc = BondsFearGreedIndex(fred_api_key='test')
        score, _ = calc.calculate_yield_curve_score()

        # spread = 4.0 - 5.0 = -1.0 (inverted)
        # score = 70 + min(30, 1.0 * 60) = 100
        assert score > 70

    @patch('requests.get')
    def test_yield_curve_steep(self, mock_requests):
        """Steep curve (10Y >> 2Y) -> low score (bonds fear)."""
        def mock_fred(url, **kwargs):
            if 'DGS2' in str(url):
                return make_fred_response(2.0)  # 2Y = 2%
            elif 'DGS10' in str(url):
                return make_fred_response(5.0)  # 10Y = 5%
            return make_fred_response(0)

        mock_requests.side_effect = mock_fred

        calc = BondsFearGreedIndex(fred_api_key='test')
        score, _ = calc.calculate_yield_curve_score()

        # spread = 5.0 - 2.0 = 3.0, score = max(0, 30 - (3.0-2.0)*20) = 10
        assert score < 50

    @patch('yfinance.Ticker')
    @patch('requests.get', side_effect=Exception('FRED down'))
    def test_yield_curve_fred_failure_yahoo_fallback(self, mock_requests, mock_ticker):
        """FRED fails -> falls back to Yahoo ^TNX/^IRX."""
        overrides = {
            '^TNX': make_price_history([4.5] * 10),   # 10Y yield
            '^IRX': make_price_history([5.0] * 10),    # Short rate (inverted)
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = BondsFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_yield_curve_score()

        assert 0 <= score <= 100
        assert 'Yahoo' in detail

    # --- Credit quality test ---

    @patch('yfinance.Ticker')
    def test_credit_quality_risk_on(self, mock_ticker):
        """LQD outperforms TLT -> greed -> score > 50."""
        overrides = {
            'LQD': make_price_history([100.0] * 15 + [103, 104, 105, 106, 107]),
            'TLT': make_price_history([100.0] * 20),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = BondsFearGreedIndex()
        score, _ = calc.calculate_credit_spreads_score()

        assert score > 50

    # --- Real rates tests ---

    @patch('requests.get')
    def test_real_rates_fred_success(self, mock_requests):
        """FRED TIPS rate -> direct score computation."""
        mock_requests.return_value = make_fred_response(2.0)

        calc = BondsFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_real_rates_score()

        # Formula: 50 + (2.0 * 6) = 62
        assert score == 62.0
        assert 'TIPS' in detail

    @patch('yfinance.Ticker')
    @patch('requests.get', side_effect=Exception('FRED down'))
    def test_real_rates_yahoo_fallback(self, mock_requests, mock_ticker):
        """FRED fails -> Yahoo ^TNX fallback."""
        mock_ticker.return_value.history.return_value = make_price_history([4.0] * 10)

        calc = BondsFearGreedIndex(fred_api_key='test')
        score, detail = calc.calculate_real_rates_score()

        # Fallback: 50 + ((4.0 - 2.5) * 6) = 59
        assert score == 59.0

    # --- Bond volatility test ---

    @patch('yfinance.Ticker')
    def test_bond_volatility_high_means_fear(self, mock_ticker):
        """High recent vol (5d) vs baseline (30d) -> low score."""
        # Stable for 55 days, then wild swings last 5 days
        prices = [100.0] * 55 + [95.0, 108.0, 92.0, 112.0, 88.0]
        mock_ticker.return_value.history.return_value = make_price_history(prices)

        calc = BondsFearGreedIndex()
        score, _ = calc.calculate_bond_volatility_score()

        assert score < 50

    # --- Equity vs bonds test ---

    @patch('yfinance.Ticker')
    def test_equity_outperforms_bonds_means_fear(self, mock_ticker):
        """SPY outperforms TLT -> capital leaving bonds -> low score."""
        overrides = {
            'SPY': make_price_history([100.0] * 15 + [103, 105, 107, 109, 111]),
            'TLT': make_price_history([100.0] * 20),
        }
        mock_ticker.side_effect = default_ticker_factory(overrides)

        calc = BondsFearGreedIndex()
        score, _ = calc.calculate_equity_vs_bonds_score()

        assert score < 50

    # --- Error handling ---

    @patch('yfinance.Ticker', side_effect=Exception('Network error'))
    def test_component_error_returns_50(self, mock_ticker):
        """All yfinance-based components return 50.0 on error."""
        calc = BondsFearGreedIndex()

        for method_name in [
            'calculate_price_momentum_score',
            'calculate_credit_spreads_score',
            'calculate_bond_volatility_score',
            'calculate_equity_vs_bonds_score',
        ]:
            score, _ = getattr(calc, method_name)()
            assert score == 50.0, f"{method_name} didn't fallback to 50.0"

    # --- Historical ---

    @patch('yfinance.Ticker')
    def test_historical_score_in_range(self, mock_ticker):
        """calculate_simple_historical_score returns float in [0, 100]."""
        mock_ticker.side_effect = default_ticker_factory()

        calc = BondsFearGreedIndex()
        score = calc.calculate_simple_historical_score(datetime(2025, 1, 15))

        assert isinstance(score, float)
        assert 0 <= score <= 100
