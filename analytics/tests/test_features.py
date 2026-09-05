import numpy as np
from pathlib import Path

from florascope_core.dataset import load_csv
from florascope_core.features import FeatureBuilder
from florascope_core.smoke import generate_competition_fixture


def test_target_row_dynamic_values_are_not_visible(tmp_path: Path) -> None:
    train, _ = generate_competition_fixture(tmp_path)
    frame = load_csv(train)
    target = int(frame.index[frame.primary_ndvi.notna()][20])

    original = FeatureBuilder(frame).build([target], {target}).x
    changed = frame.copy()
    for column in ["primary_ndvi", "s2_ndvi", "landsat_ndvi", "modis_ndvi", "era5_temp_c"]:
        changed.loc[target, column] = 999.0
    altered = FeatureBuilder(changed).build([target], {target}).x

    assert list(original.columns) == list(altered.columns)
    assert np.allclose(original.to_numpy(), altered.to_numpy(), equal_nan=True)


def test_outer_dynamic_values_cannot_change_inner_features(tmp_path):
    from florascope_core.schema import DYNAMIC_COLUMNS
    train, _ = generate_competition_fixture(tmp_path)
    frame = load_csv(train)
    known = frame.index[frame.primary_ndvi.notna()].tolist()
    inner, outer = known[20:25], set(known[30:40])
    before = FeatureBuilder(frame).build(inner, outer | set(inner))
    changed = frame.copy()
    for column in DYNAMIC_COLUMNS:
        if column in changed:
            changed.loc[list(outer), column] = 'changed' if column == 'status' else 999.0
    after = FeatureBuilder(changed).build(inner, outer | set(inner))
    assert np.allclose(before.x, after.x, equal_nan=True)
    assert np.array_equal(before.y, after.y)
    assert not any('polygon' in column for column in before.x)
