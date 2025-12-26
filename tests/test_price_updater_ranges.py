from datetime import date

from app.services.price_updater import _split_ranges_by_boundary


def test_split_ranges_by_boundary():
    boundary = date(2024, 1, 1)
    ranges = [
        (date(2023, 12, 28), date(2024, 1, 3)),
        (date(2024, 1, 4), date(2024, 1, 5)),
        (date(2023, 12, 20), date(2023, 12, 25)),
    ]

    historical, recent = _split_ranges_by_boundary(ranges, boundary)

    assert historical == [
        (date(2023, 12, 28), date(2023, 12, 31)),
        (date(2023, 12, 20), date(2023, 12, 25)),
    ]
    assert recent == [
        (date(2024, 1, 1), date(2024, 1, 3)),
        (date(2024, 1, 4), date(2024, 1, 5)),
    ]
