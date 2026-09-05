from __future__ import annotations

import numpy as np
from scipy.linalg import solve_banded

_GRID = np.arange(1, 367)
_N = 366


def linear_curve(days: np.ndarray, values: np.ndarray) -> np.ndarray:
    if len(days) == 0:
        return np.full(_N, np.nan)

    order = np.argsort(days)
    days = np.asarray(days, dtype=int)[order]
    values = np.asarray(values, dtype=float)[order]
    if len(days) == 1:
        return np.full(_N, values[0], dtype=float)
    return np.interp(_GRID, days, values)


def whittaker_curve(days: np.ndarray, values: np.ndarray, lam: float = 1000.0) -> np.ndarray:
    """Whittaker smoother на суточной сетке.

    Здесь pentadiagonal solve вместо sparse matrix на каждый сезон. На train это
    сотни коротких рядов; так тот же baseline считается в разы быстрее.
    """

    if len(days) < 2:
        return linear_curve(days, values)

    y = np.zeros(_N, dtype=float)
    w = np.zeros(_N, dtype=float)
    indices = np.asarray(days, dtype=int) - 1
    y[indices] = np.asarray(values, dtype=float)
    w[indices] = 1.0

    # D2.T @ D2 для второй разности - пятидиагональная матрица.
    main = np.full(_N, 6.0)
    main[0] = main[-1] = 1.0
    main[1] = main[-2] = 5.0
    first = np.full(_N - 1, -4.0)
    first[0] = first[-1] = -2.0
    second = np.ones(_N - 2)

    band = np.zeros((5, _N), dtype=float)
    band[0, 2:] = lam * second
    band[1, 1:] = lam * first
    band[2, :] = lam * main + w
    band[3, :-1] = lam * first
    band[4, :-2] = lam * second
    return solve_banded((2, 2), band, w * y, check_finite=False)
