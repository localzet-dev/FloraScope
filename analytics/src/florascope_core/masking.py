from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import ID, TARGET


def synthetic_mask(
    frame: pd.DataFrame,
    *,
    seed: int,
    fraction: float = 0.15,
    eligible: set[int] | None = None,
) -> set[int]:
    """Повторяет механику private gaps: примерно 15% известных точек на AOI/year."""

    rng = np.random.default_rng(seed)
    known = frame[TARGET].notna()
    if eligible is not None:
        known &= frame.index.to_series().isin(eligible)

    result: set[int] = set()
    for _, group in frame.loc[known].groupby([ID, "year"], sort=False):
        indices = group.index.to_numpy(dtype=int)
        if len(indices) < 4:
            continue
        count = max(1, int(round(len(indices) * fraction)))
        chosen = rng.choice(indices, size=min(count, len(indices)), replace=False)
        result.update(int(value) for value in chosen)
    return result
