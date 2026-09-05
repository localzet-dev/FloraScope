import numpy as np
import pandas as pd
from pathlib import Path

from florascope_core import pipeline
from florascope_core.dataset import load_csv
from florascope_core.masking import synthetic_mask
from florascope_core.smoke import generate_competition_fixture


def test_outer_labels_cannot_affect_training_or_calibration(tmp_path: Path, monkeypatch):
    train, _ = generate_competition_fixture(tmp_path)
    original = load_csv(train)
    outer = synthetic_mask(original, seed=9901)
    fits, calibrations = [], []

    class Bundle:
        source_classifier = None

        def predict_components(self, x):
            return x['primary_ndvi__interp'].fillna(.5).to_numpy(), None

        def predict(self, x):
            return self.predict_components(x)[0]

    def fit(x, y, source, **kwargs):
        fits.append((x.copy(), y.copy(), source.copy()))
        return Bundle()

    def calibrate(bundle, batch):
        assert outer.isdisjoint(batch.indices)
        calibrations.append((batch.x.copy(), batch.y.copy()))
        return 1.0, None, 1.0

    monkeypatch.setattr(pipeline, 'fit_recovery_model', fit)
    monkeypatch.setattr(pipeline, '_calibrate', calibrate)
    monkeypatch.setattr(pipeline, 'load_csv', lambda _: original.copy())
    before = pipeline.benchmark(train, fast=True)
    changed = original.copy()
    changed.loc[list(outer), 'primary_ndvi'] += 10
    monkeypatch.setattr(pipeline, 'load_csv', lambda _: changed.copy())
    after = pipeline.benchmark(train, fast=True)
    for first, second in zip(fits[:2], fits[2:]):
        pd.testing.assert_frame_equal(first[0], second[0])
        np.testing.assert_array_equal(first[1], second[1])
        np.testing.assert_array_equal(first[2], second[2])
    pd.testing.assert_frame_equal(calibrations[0][0], calibrations[1][0])
    np.testing.assert_array_equal(calibrations[0][1], calibrations[1][1])
    assert after.rmse > before.rmse
    assert before.protocol == 'nested_calibration_v1'
