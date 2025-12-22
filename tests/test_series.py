from app.services.series import clamp_days


def test_clamp_days():
    assert clamp_days("30", 10) == 10
    assert clamp_days("7", 365) == 7
    assert clamp_days("", 365) == 0
    assert clamp_days("abc", 365) == 0
