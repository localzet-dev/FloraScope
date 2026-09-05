from __future__ import annotations

import argparse
import hashlib
import json
import numpy as np
from dataclasses import asdict
from florascope_core.dataset import load_csv
from florascope_core.features import FeatureBuilder
from florascope_core.masking import synthetic_mask
from florascope_core.pipeline import benchmark, train_production
from florascope_core.schema import ID, TARGET
from pathlib import Path
from tempfile import TemporaryDirectory


def run(train: Path, output: Path, seed: int = 9901) -> dict:
    frame = load_csv(train)
    polygons = sorted(frame[ID].unique())
    rng = np.random.default_rng(seed)
    held_out = sorted(rng.choice(polygons, max(1, len(polygons) // 5), replace=False).tolist())
    training = frame.loc[~frame[ID].isin(held_out)]
    evaluation = frame.loc[frame[ID].isin(held_out)].reset_index(drop=True)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        train_path = root / 'train.csv'
        training.to_csv(train_path, index=False)
        calibration = benchmark(train_path, seed=seed, fast=True)
        bundle, _ = train_production(train_path, root / 'model', calibration=calibration, fast=True)
        mask = synthetic_mask(evaluation, seed=seed)
        batch = FeatureBuilder(evaluation, bundle.crop_categories).build(sorted(mask), mask)
        prediction = bundle.predict(batch.x)
    squared = (batch.y - prediction) ** 2
    gap = batch.x['primary_gap_span'].to_numpy()
    breakdown = {}
    for name, selected in [('<=10 days', gap <= 10), ('11-30 days', (gap > 10) & (gap <= 30)),
                           ('>30 days', gap > 30), ('one-sided', ~np.isfinite(gap))]:
        if selected.any():
            breakdown[name] = {'rows': int(selected.sum()), 'rmse': float(np.sqrt(squared[selected].mean()))}
    result = {
        'protocol': 'unseen_aoi_diagnostic_v1', 'seed': seed, 'fast': True,
        'input_sha256': hashlib.sha256(train.read_bytes()).hexdigest(),
        'training_polygons': sorted(training[ID].unique().tolist()), 'held_out_polygons': held_out,
        'held_out_known': int(evaluation[TARGET].notna().sum()), 'validation_targets': len(mask),
        'rmse': float(np.sqrt(squared.mean())), 'gap_span_breakdown': breakdown,
        'training_only_calibration': asdict(calibration),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.train, args.output), ensure_ascii=False, indent=2))
