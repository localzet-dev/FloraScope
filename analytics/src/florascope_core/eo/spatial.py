from __future__ import annotations

import numpy as np
import warnings
from datetime import date
from pathlib import Path

from .models import Observation, SceneRef
from .raster import spatial_components, write_geotiff
from .sentinel2 import Sentinel2Provider


def analyze_spatial(
    provider: Sentinel2Provider,
    current: list[Observation],
    history: list[Observation],
    scenes: dict[str, SceneRef],
    geometry: dict,
    bbox: tuple[float, float, float, float],
    layers_dir: Path,
    *,
    resolution_m: float,
) -> tuple[list[dict], list[dict]]:
    current_s2 = [
        item for item in current if item.source == "sentinel-2" and item.scene_id in scenes
    ]
    history_s2 = [
        item for item in history if item.source == "sentinel-2" and item.scene_id in scenes
    ]
    if not current_s2 or len(history_s2) < 2:
        raise ValueError("для spatial layer не хватает Sentinel-2")

    latest_meta = max(current_s2, key=lambda item: item.date)
    latest_scene = scenes[latest_meta.scene_id]
    grid = provider.grid(latest_scene, bbox, resolution_m)
    latest = provider.read(latest_scene, geometry, grid, keep_rasters=True)
    if latest.rasters is None:
        raise ValueError("latest Sentinel raster не прочитан")

    latest_doy = date.fromisoformat(latest.date).timetuple().tm_yday
    reference_meta = sorted(
        history_s2,
        key=lambda item: abs(
            date.fromisoformat(item.date).timetuple().tm_yday - latest_doy
        ),
    )[:8]
    references: list[np.ndarray] = []
    for meta in reference_meta:
        scene = scenes[meta.scene_id]
        observation = provider.read(scene, geometry, grid, keep_rasters=True)
        if observation.rasters and "ndvi" in observation.rasters:
            references.append(observation.rasters["ndvi"])
    if len(references) < 2:
        raise ValueError("мало исторических Sentinel raster для spatial baseline")

    stack = np.stack(references)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        expected = np.nanmedian(stack, axis=0)
        spread = np.maximum(np.nanstd(stack, axis=0), 0.04)
    zscore = (latest.rasters["ndvi"] - expected) / spread
    zscore[np.isfinite(stack).sum(axis=0) < 2] = np.nan
    quality = np.mean(np.isfinite(stack), axis=0).astype(np.float32)

    write_geotiff(layers_dir / "ndvi.tif", latest.rasters["ndvi"], grid)
    write_geotiff(layers_dir / "zscore.tif", zscore.astype(np.float32), grid)
    write_geotiff(layers_dir / "quality.tif", quality, grid)
    events = spatial_components(zscore, grid)
    for event in events:
        event["date"] = latest.date
        event["severity"] = "CRITICAL"
    layers = [
        {"key": "ndvi", "label": "Latest NDVI"},
        {"key": "zscore", "label": "Spatial anomaly"},
        {"key": "quality", "label": "Reference quality"},
    ]
    return events, layers
