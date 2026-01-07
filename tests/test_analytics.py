from datetime import date

import pytest

from app.services.analytics import compute_indicators, merge_prophet_forecast


def test_compute_indicators_basic():
    rows = [
        {"date": date(2024, 1, day), "price": float(day)} for day in range(1, 11)
    ]
    result = compute_indicators(rows)

    assert len(result) == 10
    assert result[0]["date"] == "2024-01-01"
    assert result[0]["sma_7"] == pytest.approx(1.0)
    assert result[6]["sma_7"] == pytest.approx(4.0)
    assert result[-1]["sma_7"] == pytest.approx(sum(range(4, 11)) / 7)


def test_merge_prophet_forecast_appends_rows():
    series = [
        {
            "date": "2024-01-01",
            "price": 1.0,
            "sma_7": 1.0,
            "sma_50": None,
            "sma_20": None,
            "bb_upper": None,
            "bb_lower": None,
        }
    ]
    forecast = [
        {"date": "2024-01-01", "yhat": 1.2, "yhat_lower": 1.0, "yhat_upper": 1.4},
        {"date": "2024-01-02", "yhat": 1.3, "yhat_lower": 1.1, "yhat_upper": 1.5},
    ]

    merged = merge_prophet_forecast(series, forecast)

    assert merged[0]["yhat"] == pytest.approx(1.2)
    assert merged[-1]["date"] == "2024-01-02"
    assert "price" in merged[-1]
    assert merged[-1]["price"] is None
