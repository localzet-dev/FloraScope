from __future__ import annotations

import numpy as np
import rasterio
from datetime import date, datetime, timezone
from math import pi, sin
from pathlib import Path
from threading import Lock
from pyproj import Transformer
from rasterio.transform import from_origin

from florascope_core.eo.live_analysis import LiveAnalyzer
from florascope_core.eo.models import AssetRef, SceneRef


def test_live_analysis_runs_on_local_geotiffs(tmp_path: Path, monkeypatch) -> None:
    scenes, geometry = _fixture(tmp_path / "scenes")
    analyzer = LiveAnalyzer(
        earth_search_url="https://unused.invalid",
        weather_url="https://unused.invalid",
        data_dir=tmp_path / "runtime",
        resolution_m=20,
        max_cells=20_000,
    )

    def search(**kwargs):
        start = kwargs["date_from"]
        end = kwargs["date_to"]
        return [scene for scene in scenes if start <= scene.acquired_at.date() <= end]

    monkeypatch.setattr(analyzer.sentinel, "search", search)
    monkeypatch.setattr(analyzer.landsat, "search", lambda **_: [])
    monkeypatch.setattr(analyzer.weather, "fetch", lambda **_: {})

    original_read = analyzer.sentinel.read
    lock = Lock()
    active_reads = 0
    max_active_reads = 0

    def tracked_read(*args, **kwargs):
        nonlocal active_reads, max_active_reads
        with lock:
            active_reads += 1
            max_active_reads = max(max_active_reads, active_reads)
        try:
            return original_read(*args, **kwargs)
        finally:
            with lock:
                active_reads -= 1

    monkeypatch.setattr(analyzer.sentinel, "read", tracked_read)

    result = analyzer.run(
        {
            "id": "field-test",
            "name": "local fixture",
            "area_ha": 40.0,
            "geometry": geometry,
        },
        date_from=date(2026, 4, 1),
        date_to=date(2026, 9, 1),
        history_years=3,
        max_cloud_cover=20,
    )

    assert result["quality"]["current_observations"] == 6
    assert result["quality"]["historical_observations"] == 18
    assert result["events"]
    assert result["spatial_events"]
    assert max_active_reads == 3
    assert {layer["key"] for layer in result["layers"]} == {"ndvi", "zscore", "quality"}

    root = Path(analyzer.data_dir) / "live" / result["id"] / "layers"
    assert (root / "ndvi.tif").exists()
    assert (root / "zscore.tif").exists()


def _fixture(root: Path) -> tuple[list[SceneRef], dict]:
    root.mkdir(parents=True)
    width = height = 36
    transform = from_origin(500000, 5001000, 20, 20)
    to_wgs84 = Transformer.from_crs("EPSG:32637", "EPSG:4326", always_xy=True)
    left, bottom = to_wgs84.transform(500000 + 3 * 20, 5001000 - 33 * 20)
    right, top = to_wgs84.transform(500000 + 33 * 20, 5001000 - 3 * 20)
    geometry = {
        "type": "Polygon",
        "coordinates": [[[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]],
    }

    scenes: list[SceneRef] = []
    for year in (2023, 2024, 2025, 2026):
        for month in (4, 5, 6, 7, 8, 9):
            when = date(year, month, 1)
            scenes.append(
                _scene(
                    root,
                    when,
                    transform,
                    width,
                    height,
                    anomaly=year == 2026 and month >= 7,
                )
            )
    return scenes, geometry


def _scene(
    root: Path,
    when: date,
    transform,
    width: int,
    height: int,
    *,
    anomaly: bool,
) -> SceneRef:
    doy = when.timetuple().tm_yday
    nir_base = 0.50 + 0.18 * sin(2 * pi * (doy - 95) / 365.25)
    nir = np.full((height, width), nir_base, np.float32)
    nir08 = np.full((height, width), nir_base - 0.02, np.float32)
    if anomaly:
        nir -= 0.08
        nir08 -= 0.09
        nir[10:27, 10:27] -= 0.18
        nir08[10:27, 10:27] -= 0.19

    arrays = {
        "blue": np.full((height, width), 0.09, np.float32),
        "green": np.full((height, width), 0.22, np.float32),
        "red": np.full((height, width), 0.15, np.float32),
        "rededge1": np.full((height, width), 0.28, np.float32),
        "nir": nir,
        "nir08": nir08,
        "swir16": np.full((height, width), 0.25, np.float32),
        "swir22": np.full((height, width), 0.21, np.float32),
        "scl": np.full((height, width), 4, np.uint8),
    }
    assets: dict[str, AssetRef] = {}
    for key, array in arrays.items():
        path = root / f"{when}-{key}.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype=str(array.dtype),
            crs="EPSG:32637",
            transform=transform,
        ) as target:
            target.write(array, 1)
        assets[key] = AssetRef(str(path), scale=1.0, offset=0.0)

    return SceneRef(
        id=f"local-{when}",
        source="sentinel-2",
        acquired_at=datetime.combine(when, datetime.min.time(), tzinfo=timezone.utc),
        cloud_cover=1.0,
        assets=assets,
    )


def test_search_failure_emits_progress_without_stopping_other_sources():
    from florascope_core.eo.live_analysis import LiveAnalyzer
    messages = []
    info = {"sentinel-2": {"errors": []}}
    def unavailable():
        raise TimeoutError("test timeout")
    scenes = LiveAnalyzer._safe_search(None, "sentinel-2", unavailable, info,
                                      lambda p, s, m: messages.append((p, s, m)), 4)
    assert scenes == []
    assert messages[0][1] == "WARNING"
    assert "test timeout" in messages[0][2]
    assert info["sentinel-2"]["errors"]


def test_catalog_failure_is_not_reported_as_pixel_quality(tmp_path, monkeypatch):
    import pytest
    analyzer = LiveAnalyzer(earth_search_url="https://unused.invalid", weather_url="https://unused.invalid",
                            data_dir=tmp_path, resolution_m=20, max_cells=20000)
    def unavailable(**kwargs):
        raise TimeoutError("catalog timeout")
    monkeypatch.setattr(analyzer.sentinel, "search", unavailable)
    monkeypatch.setattr(analyzer.landsat, "search", unavailable)
    field = {"id": "test", "name": "test", "geometry": {"type": "Polygon", "coordinates": [
        [[39,45],[39.01,45],[39.01,45.01],[39,45.01],[39,45]]]}}
    with pytest.raises(ValueError, match="Проверка качества пикселей не выполнялась"):
        analyzer.run(field, date_from=date(2025,3,1), date_to=date(2025,9,1), history_years=1)
