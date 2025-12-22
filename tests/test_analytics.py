from datetime import date

import pytest

from app.services.analytics import compute_indicators


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
