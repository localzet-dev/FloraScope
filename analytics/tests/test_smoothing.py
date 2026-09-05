import numpy as np

from florascope_core.smoothing import linear_curve, whittaker_curve


def test_smoothers_return_daily_curve() -> None:
    days = np.array([100, 150, 200])
    values = np.array([0.2, 0.7, 0.4])
    assert linear_curve(days, values).shape == (366,)
    result = whittaker_curve(days, values)
    assert result.shape == (366,)
    assert np.isfinite(result).all()
