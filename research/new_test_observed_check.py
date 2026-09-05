"""Проверка на видимых observations нового test; скрытые ответы не используются."""
import argparse
import json
import numpy as np
from florascope_core.dataset import load_csv
from florascope_core.features import FeatureBuilder
from florascope_core.masking import synthetic_mask
from florascope_core.model import RecoveryBundle
from pathlib import Path

p = argparse.ArgumentParser();
p.add_argument('--model', required=True);
p.add_argument('--output', required=True);
args = p.parse_args()
f = load_csv('/data/input/private_features.csv');
model = RecoveryBundle.load(args.model)
rows = []
for seed in (9901, 10039, 10177):
    mask = synthetic_mask(f, seed=seed)
    hidden = mask | set(f.index[f.is_synthetic_gap])
    b = FeatureBuilder(f, model.crop_categories).build(sorted(mask), hidden)
    pred = model.predict(b.x);
    line = b.x['primary_ndvi__interp'].to_numpy();
    valid = np.isfinite(line)
    rows.append({'seed': seed, 'targets': len(mask), 'rmse': float(np.sqrt(np.mean((pred - b.y) ** 2))),
                 'linear_rmse_common': float(np.sqrt(np.mean((line[valid] - b.y[valid]) ** 2))),
                 'linear_targets': int(valid.sum())})
r = {'protocol': 'frozen_model_new_test_visible_observations_v1', 'model': args.model, 'folds': rows,
     'rmse_mean': float(np.mean([r['rmse'] for r in rows]))}
Path(args.output).write_text(json.dumps(r, indent=2));
print(json.dumps(r, indent=2))
