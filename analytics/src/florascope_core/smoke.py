from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path


def generate_competition_fixture(root: str | Path, *, seed: int = 7) -> tuple[Path, Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for aoi in range(5):
        for year in range(2019, 2025):
            crop = ["wheat", "corn", "soy"][aoi % 3]
            for timestamp in pd.date_range(f"{year}-03-15", f"{year}-09-30", freq="5D"):
                doy = timestamp.dayofyear
                truth = (
                    0.18
                    + 0.48 * (0.5 + 0.5 * np.sin(2 * np.pi * (doy - 105) / 365.25))
                    + rng.normal(0, 0.018)
                )
                s2 = truth + rng.normal(0, 0.015) if rng.random() < 0.5 else np.nan
                landsat = truth + rng.normal(0, 0.025) if rng.random() < 0.35 else np.nan
                modis = truth + rng.normal(0, 0.04) if rng.random() < 0.8 else np.nan
                primary = s2 if np.isfinite(s2) else landsat if np.isfinite(landsat) else modis
                rows.append(
                    {
                        "anon_polygon_id": f"AOI-{aoi:03d}",
                        "date": timestamp.strftime("%Y-%m-%d"),
                        "s2_ndvi": s2,
                        "s2_evi": s2 * 0.9 if np.isfinite(s2) else np.nan,
                        "s2_ndwi": s2 * 0.3 - 0.1 if np.isfinite(s2) else np.nan,
                        "landsat_ndvi": landsat,
                        "landsat_evi": landsat * 0.9 if np.isfinite(landsat) else np.nan,
                        "landsat_ndwi": landsat * 0.3 - 0.1 if np.isfinite(landsat) else np.nan,
                        "modis_ndvi": modis,
                        "modis_evi": modis * 0.85 if np.isfinite(modis) else np.nan,
                        "era5_temp_c": 15 + 10 * np.sin(2 * np.pi * (doy - 100) / 365.25),
                        "era5_precip_mm": max(0, rng.gamma(1.5, 2) - 1),
                        "year": year,
                        "primary_ndvi": primary,
                        "doy": doy,
                        "ndvi_climatology_mean": truth,
                        "ndvi_climatology_std": 0.05,
                        "n_reference_years": 4,
                        "crop_type": crop,
                    }
                )

    train = pd.DataFrame(rows)
    test = train.copy()
    test["is_synthetic_gap"] = False
    dynamic = [
        "primary_ndvi",
        "s2_ndvi",
        "s2_evi",
        "s2_ndwi",
        "landsat_ndvi",
        "landsat_evi",
        "landsat_ndwi",
        "modis_ndvi",
        "modis_evi",
        "era5_temp_c",
        "era5_precip_mm",
        "ndvi_climatology_mean",
        "ndvi_climatology_std",
        "n_reference_years",
    ]
    for _, group in test.loc[test.primary_ndvi.notna()].groupby(["anon_polygon_id", "year"]):
        count = max(1, round(len(group) * 0.15))
        indices = rng.choice(group.index, size=count, replace=False)
        test.loc[indices, "is_synthetic_gap"] = True
        test.loc[indices, dynamic] = np.nan

    train_path = root / "train_dataset.csv"
    test_path = root / "test_dataset.csv"
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    return train_path, test_path
