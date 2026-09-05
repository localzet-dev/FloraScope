import pandas as pd
from pathlib import Path

from florascope_core.smoke import generate_competition_fixture
from florascope_core.submission import validate_submission


def test_submission_keys_must_match_synthetic_rows(tmp_path: Path) -> None:
    _, test = generate_competition_fixture(tmp_path / "input")
    frame = pd.read_csv(test)
    expected = frame.loc[frame.is_synthetic_gap, ["anon_polygon_id", "date"]].copy()
    expected["primary_ndvi_true"] = 0.5
    path = tmp_path / "submission.csv"
    expected.to_csv(path, index=False)
    report = validate_submission(test, path)
    assert report["valid"] is True
    assert report["rows"] == len(expected)


def test_submission_rejects_nan_duplicates_extra_rows_and_columns(tmp_path):
    import numpy as np
    import pytest
    _, test = generate_competition_fixture(tmp_path / 'input')
    frame = pd.read_csv(test)
    good = frame.loc[frame.is_synthetic_gap, ['anon_polygon_id', 'date']].copy()
    good['primary_ndvi_true'] = .5
    nan = good.copy();
    nan.iloc[0, 2] = np.nan
    extra_column = good.assign(extra=1)
    extra_row = good.iloc[:1].copy();
    extra_row['anon_polygon_id'] = 'unknown'
    cases = [nan, pd.concat([good, good.iloc[:1]]), extra_column,
             pd.concat([good, extra_row]), good.iloc[1:]]
    for candidate in cases:
        path = tmp_path / 'submission.csv'
        candidate.to_csv(path, index=False)
        with pytest.raises(ValueError):
            validate_submission(test, path)
