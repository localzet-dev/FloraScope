from __future__ import annotations

import httpx
import numpy as np
from datetime import date
from rasterio.enums import Resampling

from .models import Observation, SceneRef
from .raster import Grid, grid_for_asset, normalized_difference, polygon_mask, read_asset
from .stac import StacClient, choose_scenes

COLLECTION = "sentinel-2-c1-l2a"
ARCHIVE_COLLECTION = "sentinel-2-l2a"
ASSET_NAMES = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "rededge1": "rededge1",
    "nir": "nir",
    "nir08": "nir08",
    "swir16": "swir16",
    "swir22": "swir22",
    "scl": "scl",
}
INVALID_SCL = {0, 1, 2, 3, 6, 7, 8, 9, 10, 11}


class Sentinel2Provider:
    def __init__(self, stac_endpoint: str) -> None:
        self.client = StacClient(stac_endpoint)
        self.search_notes: list[str] = []

    def search(
        self,
        *,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        max_cloud_cover: float,
        limit: int = 18,
    ) -> list[SceneRef]:
        self.search_notes = []
        params = dict(source="sentinel-2", bbox=bbox, date_from=date_from,
                      date_to=date_to, max_cloud_cover=max_cloud_cover, limit=80)
        try:
            scenes = self.client.search(collection=COLLECTION, **params)
        except httpx.HTTPError as exc:
            self.search_notes.append(f"{COLLECTION}: {exc}")
            scenes = []
        usable = [scene for scene in scenes if all(name in scene.assets for name in ASSET_NAMES.values())]
        if not usable:
            # Перепроцессированный C1 архив может быть неполон именно для этого
            # AOI/сезона. Legacy L2A остаётся реальным источником исторических COG.
            self.search_notes.append(f"{date_from.year}: fallback {ARCHIVE_COLLECTION}")
            scenes = self.client.search(collection=ARCHIVE_COLLECTION, **params)
            usable = [scene for scene in scenes if all(name in scene.assets for name in ASSET_NAMES.values())]
        return choose_scenes(usable, min_gap_days=7, limit=limit)

    def grid(self, scene: SceneRef, bbox: tuple[float, float, float, float], resolution: float) -> Grid:
        return grid_for_asset(scene.assets["rededge1"].href, bbox, resolution)

    def read(
        self,
        scene: SceneRef,
        geometry: dict,
        grid: Grid,
        *,
        keep_rasters: bool = False,
    ) -> Observation:
        arrays: dict[str, np.ndarray] = {}
        for key in ASSET_NAMES:
            asset = scene.assets[key]
            raw = read_asset(
                asset.href,
                grid,
                resampling=Resampling.nearest if key == "scl" else Resampling.bilinear,
            )
            if key == "scl":
                arrays[key] = np.nan_to_num(raw, nan=0).astype(np.uint8)
                continue
            scale = 0.0001 if asset.scale is None else asset.scale
            default_offset = -0.1 if scene.collection == COLLECTION else 0.0
            offset = default_offset if asset.offset is None else asset.offset
            arrays[key] = raw.astype(np.float32) * scale + offset

        inside = polygon_mask(geometry, grid)
        valid = inside & ~np.isin(arrays["scl"], tuple(INVALID_SCL))
        indices = _indices(arrays)
        valid &= np.isfinite(indices["ndvi"])
        aggregates: dict[str, float] = {}
        raster_result: dict[str, np.ndarray] = {}
        for key, values in indices.items():
            masked = np.where(valid, values, np.nan).astype(np.float32)
            finite = masked[np.isfinite(masked)]
            if finite.size:
                aggregates[key] = float(np.median(finite))
            if keep_rasters:
                raster_result[key] = masked

        total = max(1, int(inside.sum()))
        return Observation(
            source="sentinel-2",
            scene_id=scene.id,
            date=scene.acquired_at.date().isoformat(),
            valid_fraction=float(valid.sum() / total),
            indices=aggregates,
            rasters=raster_result if keep_rasters else None,
        )


def _indices(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    ndvi = normalized_difference(arrays["nir"], arrays["red"])
    ndwi = normalized_difference(arrays["green"], arrays["nir"])
    ndmi = normalized_difference(arrays["nir08"], arrays["swir16"])
    ndre = normalized_difference(arrays["nir08"], arrays["rededge1"])
    nbr = normalized_difference(arrays["nir08"], arrays["swir22"])
    denominator = arrays["nir"] + 6 * arrays["red"] - 7.5 * arrays["blue"] + 1
    evi = np.divide(
        2.5 * (arrays["nir"] - arrays["red"]),
        denominator,
        out=np.full(ndvi.shape, np.nan, dtype=np.float32),
        where=np.abs(denominator) > 1e-6,
    )
    return {"ndvi": ndvi, "evi": evi, "ndwi": ndwi, "ndmi": ndmi, "ndre": ndre, "nbr": nbr}
