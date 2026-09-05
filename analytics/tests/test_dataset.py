import pandas as pd
from pathlib import Path

from florascope_core.dataset import load_csv, source_priority_audit


def test_private_features_may_omit_target(tmp_path: Path) -> None:
    path = tmp_path / "private_features.csv"
    pd.DataFrame(
        [
            {
                "anon_polygon_id": "AOI-1",
                "date": "2025-05-01",
                "crop_type": "зерновые",
                "is_synthetic_gap": True,
            }
        ]
    ).to_csv(path, index=False)
    frame = load_csv(path)
    assert "primary_ndvi" in frame
    assert frame["primary_ndvi"].isna().all()
    assert frame.loc[0, "year"] == 2025


def test_source_priority_is_s2_then_landsat_then_modis(tmp_path: Path) -> None:
    path = tmp_path / "train.csv"
    pd.DataFrame(
        [
            {"anon_polygon_id": "A", "date": "2025-05-01", "crop_type": "x", "s2_ndvi": 0.6, "landsat_ndvi": 0.5,
             "modis_ndvi": 0.4, "primary_ndvi": 0.6},
            {"anon_polygon_id": "A", "date": "2025-05-02", "crop_type": "x", "s2_ndvi": None, "landsat_ndvi": 0.52,
             "modis_ndvi": 0.41, "primary_ndvi": 0.52},
            {"anon_polygon_id": "A", "date": "2025-05-03", "crop_type": "x", "s2_ndvi": None, "landsat_ndvi": None,
             "modis_ndvi": 0.43, "primary_ndvi": 0.43},
        ]
    ).to_csv(path, index=False)
    report = source_priority_audit(load_csv(path))
    assert report["checked"] == 3
    assert report["match_rate"] == 1.0
