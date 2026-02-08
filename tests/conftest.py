"""Shared test helpers for Fear & Greed Index tests."""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Add project root to sys.path so we can import calculator modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def make_price_history(prices, volumes=None):
    """
    Create a DataFrame mimicking yfinance Ticker.history() output.

    Args:
        prices: List of closing prices
        volumes: Optional list of volumes (defaults to 1M each)
    """
    n = len(prices)
    dates = pd.date_range(start='2020-01-02', periods=n, freq='B')
    if volumes is None:
        volumes = [1_000_000] * n
    prices_arr = np.array(prices, dtype=float)
    volumes_arr = np.array(volumes, dtype=float)
    return pd.DataFrame({
        'Close': prices_arr,
        'Open': prices_arr * 0.999,
        'High': prices_arr * 1.005,
        'Low': prices_arr * 0.995,
        'Volume': volumes_arr,
    }, index=dates)


def make_fred_response(value):
    """Create a mock requests.Response for a successful FRED API call."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        'observations': [{'value': str(value), 'date': '2025-06-15'}]
    }
    return resp


def default_ticker_factory(overrides=None):
    """
    Returns a side_effect function for yf.Ticker.
    Each call returns a MagicMock whose .history() gives a DataFrame.

    Args:
        overrides: dict of {symbol: DataFrame} for custom data per symbol
    """
    overrides = overrides or {}

    def factory(symbol):
        mock = MagicMock()
        if symbol in overrides:
            mock.history.return_value = overrides[symbol]
        else:
            # Default: 250 days of flat prices at 100, volume 1M
            mock.history.return_value = make_price_history([100.0] * 250)
        return mock

    return factory
