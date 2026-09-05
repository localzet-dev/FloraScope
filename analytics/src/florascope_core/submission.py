from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

from .dataset import load_csv
from .schema import DATE, ID, SYNTHETIC


def validate_submission(test_path: str | Path, submission_path: str | Path) -> dict:
    test = load_csv(test_path)
    submission = pd.read_csv(submission_path)
    required = [ID, DATE, "primary_ndvi_pred"]
    missing = [column for column in required if column not in submission]
    if missing:
        raise ValueError(f"В submission не хватает колонок: {missing}")
    if list(submission.columns) != required:
        raise ValueError(f"Submission должен содержать ровно колонки {required}")
    if submission.duplicated([ID, DATE]).any():
        raise ValueError("В submission есть дубли polygon/date")

    prediction = pd.to_numeric(submission["primary_ndvi_pred"], errors="coerce")
    if not np.isfinite(prediction).all():
        raise ValueError("В submission есть NaN/inf")

    expected = test.loc[test[SYNTHETIC], [ID, DATE]].copy()
    expected[DATE] = expected[DATE].dt.strftime("%Y-%m-%d")
    expected_keys = set(map(tuple, expected.astype(str).to_numpy()))
    actual_keys = set(map(tuple, submission[[ID, DATE]].astype(str).to_numpy()))
    if expected_keys != actual_keys:
        raise ValueError(
            "Ключи submission не совпадают с synthetic gaps: "
            f"missing={len(expected_keys - actual_keys)}, extra={len(actual_keys - expected_keys)}"
        )

    return {
        "valid": True,
        "rows": int(len(submission)),
        "min_prediction": float(prediction.min()),
        "max_prediction": float(prediction.max()),
    }
