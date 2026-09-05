"""Парная проверка удаления organizer climatology; маски и seeds не меняем."""
import json
import numpy as np
from dataclasses import asdict
from florascope_core.dataset import load_csv, primary_source
from florascope_core.features import FeatureBuilder
from florascope_core.masking import synthetic_mask
from florascope_core.pipeline import benchmark, _fit_masked
from pathlib import Path

root = Path('/research/results')
frame = load_csv('/data/input/train_dataset.csv')
removed = ['ndvi_climatology_mean', 'ndvi_climatology_std']
reduced = frame.drop(columns=removed)
path = Path('/data/input/train_updated_schema.csv')
reduced.to_csv(path, index=False)
previous = json.loads((root / 'cv_three_seeds_nested.json').read_text())['folds']
results = []
for report in previous:
    seed = report['seed']
    outer = synthetic_mask(frame, seed=seed)
    builder = FeatureBuilder(frame)
    bundle = _fit_masked(frame, builder, primary_source(frame), outer, seed, True)
    bundle.general_weight = report['general_weight']
    bundle.baseline = report['selected_baseline']
    bundle.model_weight = report['model_weight']
    original = builder.build(sorted(outer), outer)
    missing = FeatureBuilder(reduced, builder.crop_categories).build(sorted(outer), outer)
    rmse = lambda batch: float(np.sqrt(np.mean((batch.y - bundle.predict(batch.x)) ** 2)))
    row = {'seed': seed, 'targets': len(outer), 'original_reproduced_rmse': rmse(original),
           'old_model_missing_columns_rmse': rmse(missing)}
    assert abs(row['original_reproduced_rmse'] - report['rmse']) < 1e-10, 'Baseline must reproduce before comparison'
    print(json.dumps(row), flush=True)
    row['retrained_without_columns'] = asdict(benchmark(path, seed=seed, fast=True))
    results.append(row)
    (root / 'updated_schema_check.json').write_text(
        json.dumps({'removed_columns': removed, 'folds': results}, indent=2))
    print(json.dumps(row), flush=True)
