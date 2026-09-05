"""MODIS-only stress test: другая частота, масштаб и типы растительности."""
import json
import numpy as np
import pandas as pd
from florascope_core.eo.models import Observation
from florascope_core.eo.temporal import analyze_temporal
from florascope_core.features import FeatureBuilder
from florascope_core.masking import synthetic_mask
from florascope_core.model import RecoveryBundle
from florascope_core.schema import SENSOR_COLUMNS, WEATHER_COLUMNS
from pathlib import Path

root = Path('/research');
records = [];
summary = [];
temporal = {}
model = RecoveryBundle.load('/artifacts/competition_model')
for path in sorted((root / 'external').glob('*_statistics.json')):
    site = path.stem.removesuffix('_statistics')
    raw = pd.DataFrame(json.loads(path.read_text())['statistics'])
    valid = (raw.pixels_pass_rel >= 80) & raw.value_mean.between(-1, 1)
    frame = pd.DataFrame({'date': pd.to_datetime(raw.calendar_date), 'primary_ndvi': raw.value_mean.where(valid),
                          'anon_polygon_id': site, 'crop_type': 'UNKNOWN', 'is_synthetic_gap': False})
    frame['year'] = frame.date.dt.year;
    frame['doy'] = frame.date.dt.dayofyear
    for column in [*SENSOR_COLUMNS, *WEATHER_COLUMNS]: frame[column] = np.nan
    frame['modis_ndvi'] = frame.primary_ndvi
    for seed in (9901, 10039, 10177):
        mask = synthetic_mask(frame, seed=seed)
        batch = FeatureBuilder(frame, model.crop_categories).build(sorted(mask), mask)
        prediction = model.predict(batch.x);
        baseline = batch.x.primary_ndvi__interp.to_numpy()
        records.append({'site': site, 'seed': seed, 'targets': len(mask),
                        'model_rmse': float(np.sqrt(np.mean((prediction - batch.y) ** 2))),
                        'linear_rmse': float(np.sqrt(np.mean((baseline - batch.y) ** 2)))})
    observations = [Observation(source='modis', scene_id=f'{site}-{row.date.date()}', date=str(row.date.date()),
                                valid_fraction=float(raw.loc[i, 'pixels_pass_rel']) / 100,
                                indices={'ndvi': float(row.primary_ndvi)}) for i, row in frame.iterrows() if
                    pd.notna(row.primary_ndvi)]
    result = analyze_temporal([o for o in observations if o.date.startswith('2024')],
                              [o for o in observations if not o.date.startswith('2024')], {}, 2024)
    temporal[site] = result
    summary.append({'site': site, 'total': len(raw), 'quality_accepted': int(valid.sum()),
                    'pixels_per_window': int(raw.pixels_total.iloc[0]), 'events_2024': len(result['events'])})
    frame.to_csv(root / 'external' / f'{site}_frame.csv', index=False)
(root / 'results/external_modis_check.json').write_text(json.dumps(
    {'protocol': 'external_modis_only_stress_v1', 'quality_min_percent': 80, 'summary': summary, 'folds': records},
    indent=2))
(root / 'results/external_modis_temporal.json').write_text(
    json.dumps(temporal, ensure_ascii=False, indent=2, allow_nan=False))
print(json.dumps({'summary': summary, 'folds': records}, indent=2))
