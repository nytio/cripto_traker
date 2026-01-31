import pytest

from app.services.analytics import compute_ema_series


def test_compute_ema_series_recursion():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = compute_ema_series(values, 3)
    assert result[:2] == [None, None]
    assert result[2:] == pytest.approx([2.0, 3.0, 4.0])
