from __future__ import annotations

ID = "anon_polygon_id"
DATE = "date"
TARGET = "primary_ndvi"
SYNTHETIC = "is_synthetic_gap"
CROP = "crop_type"

SOURCE_NDVI = ["s2_ndvi", "landsat_ndvi", "modis_ndvi"]
SENSOR_COLUMNS = [
    "s2_ndvi",
    "s2_evi",
    "s2_ndwi",
    "landsat_ndvi",
    "landsat_evi",
    "landsat_ndwi",
    "modis_ndvi",
    "modis_evi",
]
WEATHER_COLUMNS = ["era5_temp_c", "era5_precip_mm"]
DERIVED_COLUMNS = [
    "ndvi_climatology_mean",
    "ndvi_climatology_std",
    "ndvi_zscore",
    "n_reference_years",
    "status",
]
DYNAMIC_COLUMNS = [TARGET, *SENSOR_COLUMNS, *WEATHER_COLUMNS, *DERIVED_COLUMNS]


def ensure_base(columns: list[str]) -> None:
    missing = [column for column in (ID, DATE, CROP) if column not in columns]
    if missing:
        raise ValueError(f"Не хватает обязательных колонок: {missing}")
