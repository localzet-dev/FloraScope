from __future__ import annotations

import numpy as np
from datetime import date
from rasterio.enums import Resampling

from .models import Observation, SceneRef
from .raster import Grid, grid_for_asset, normalized_difference, polygon_mask, read_asset
from .stac import StacClient, choose_scenes

COLLECTION = "landsat-c2-l2"
REQUIRED = ["blue", "green", "red", "nir08", "swir16", "qa_pixel"]


class LandsatProvider:
    """Landsat 8/9 C2 L2 через Earth Search.

    В некоторых окружениях USGS assets могут потребовать requester-pays/AWS доступ.
    Live service поэтому считает Landsat дополнительным источником и не падает целиком,
    если он недоступен.
    """

    def __init__(self, stac_endpoint: str) -> None:
        self.client = StacClient(stac_endpoint)

    def search(
        self,
        *,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        max_cloud_cover: float,
        limit: int = 12,
    ) -> list[SceneRef]:
        scenes = self.client.search(
            collection=COLLECTION,
            source="landsat",
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            max_cloud_cover=max_cloud_cover,
            limit=60,
        )
        usable = [scene for scene in scenes if all(name in scene.assets for name in REQUIRED)]
        return choose_scenes(usable, min_gap_days=12, limit=limit)

    def grid(self, scene: SceneRef, bbox: tuple[float, float, float, float]) -> Grid:
        return grid_for_asset(scene.assets["red"].href, bbox, 30.0)

    def read(self, scene: SceneRef, geometry: dict, *, max_cells: int = 300_000) -> Observation:
        grid = self.grid(scene, tuple(_bounds(geometry)))
        if grid.cells > max_cells:
            raise ValueError(f"Landsat AOI: {grid.cells} ячеек, лимит {max_cells}")
        arrays: dict[str, np.ndarray] = {}
        for key in REQUIRED:
            asset = scene.assets[key]
            raw = read_asset(asset.href, grid,
                             resampling=Resampling.nearest if key == "qa_pixel" else Resampling.bilinear)
            if key == "qa_pixel":
                arrays[key] = np.nan_to_num(raw, nan=1).astype(np.uint16)
                continue
            # Коэффициенты масштаба/смещения USGS Collection 2 Surface Reflectance.
            scale = 0.0000275 if asset.scale is None else asset.scale
            offset = -0.2 if asset.offset is None else asset.offset
            arrays[key] = raw.astype(np.float32) * scale + offset

        inside = polygon_mask(geometry, grid)
        qa = arrays["qa_pixel"]
        invalid_bits = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5)
        valid = inside & ((qa & invalid_bits) == 0)

        ndvi = normalized_difference(arrays["nir08"], arrays["red"])
        valid &= np.isfinite(ndvi)
        ndwi = normalized_difference(arrays["green"], arrays["nir08"])
        denominator = arrays["nir08"] + 6 * arrays["red"] - 7.5 * arrays["blue"] + 1
        evi = np.divide(
            2.5 * (arrays["nir08"] - arrays["red"]),
            denominator,
            out=np.full(ndvi.shape, np.nan, dtype=np.float32),
            where=np.abs(denominator) > 1e-6,
        )
        result = {}
        for key, values in {"ndvi": ndvi, "evi": evi, "ndwi": ndwi}.items():
            finite = values[valid & np.isfinite(values)]
            if finite.size:
                result[key] = float(np.median(finite))

        total = max(1, int(inside.sum()))
        return Observation(
            source="landsat",
            scene_id=scene.id,
            date=scene.acquired_at.date().isoformat(),
            valid_fraction=float(valid.sum() / total),
            indices=result,
            rasters=None,
        )


def _bounds(geometry: dict) -> tuple[float, float, float, float]:
    from shapely.geometry import shape

    return tuple(float(value) for value in shape(geometry).bounds)
