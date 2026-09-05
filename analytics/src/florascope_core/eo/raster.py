from __future__ import annotations

import numpy as np
import rasterio
from PIL import Image
from dataclasses import dataclass
from io import BytesIO
from math import ceil
from pathlib import Path
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes
from rasterio.transform import from_bounds, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from scipy import ndimage
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry


@dataclass(frozen=True, slots=True)
class Grid:
    crs: rasterio.crs.CRS
    transform: rasterio.Affine
    width: int
    height: int
    resolution: float

    @property
    def cells(self) -> int:
        return self.width * self.height


def grid_for_asset(
    href: str,
    bbox_wgs84: tuple[float, float, float, float],
    resolution: float,
) -> Grid:
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="1"):
        with rasterio.open(href) as source:
            left, bottom, right, top = transform_bounds(
                "EPSG:4326",
                source.crs,
                *bbox_wgs84,
                densify_pts=21,
            )
            width = max(1, ceil((right - left) / resolution))
            height = max(1, ceil((top - bottom) / resolution))
            return Grid(
                crs=source.crs,
                transform=from_origin(left, top, resolution, resolution),
                width=width,
                height=height,
                resolution=resolution,
            )


def read_asset(
    href: str,
    grid: Grid,
    *,
    resampling: Resampling,
) -> np.ndarray:
    # WarpedVRT задан ровно на bbox AOI. Полный Sentinel/Landsat тайл в память не грузим.
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="1"):
        with rasterio.open(href) as source:
            with WarpedVRT(
                source,
                crs=grid.crs,
                transform=grid.transform,
                width=grid.width,
                height=grid.height,
                resampling=resampling,
                dtype="float32",
                nodata=float("nan"),
            ) as vrt:
                return vrt.read(1, masked=True).astype(np.float32).filled(np.nan)


def polygon_mask(geometry_wgs84: dict, grid: Grid) -> np.ndarray:
    transformer = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    projected = transform_geometry(transformer.transform, shape(geometry_wgs84))
    return geometry_mask(
        [mapping(projected)],
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        invert=True,
    )


def normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denominator = a + b
    return np.divide(
        a - b,
        denominator,
        out=np.full(a.shape, np.nan, dtype=np.float32),
        where=np.abs(denominator) > 1e-6,
    ).astype(np.float32)


def write_geotiff(path: Path, array: np.ndarray, grid: Grid) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = np.where(np.isfinite(array), array, -9999.0).astype(np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=grid.width,
        height=grid.height,
        count=1,
        dtype="float32",
        crs=grid.crs,
        transform=grid.transform,
        nodata=-9999.0,
        compress="deflate",
        tiled=True,
    ) as target:
        target.write(encoded, 1)
    return path


def spatial_components(
    zscore: np.ndarray,
    grid: Grid,
    *,
    threshold: float = -2.0,
    min_area_ha: float = 0.2,
) -> list[dict]:
    mask = np.isfinite(zscore) & (zscore < threshold)
    cleaned = ndimage.binary_closing(mask, structure=np.ones((3, 3), dtype=bool))
    # Closing не превращает облако/nodata в доказанную площадь аномалии.
    cleaned &= np.isfinite(zscore)
    labels, count = ndimage.label(cleaned)
    to_wgs84 = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)

    result: list[dict] = []
    for label_id in range(1, count + 1):
        component = labels == label_id
        area_ha = float(component.sum() * abs(grid.transform.a * grid.transform.e) / 10000.0)
        if area_ha < min_area_ha:
            continue
        polygons = [
            shape(geometry)
            for geometry, value in shapes(
                component.astype(np.uint8),
                mask=component,
                transform=grid.transform,
            )
            if value == 1
        ]
        if not polygons:
            continue
        geometry = polygons[0]
        for extra in polygons[1:]:
            geometry = geometry.union(extra)
        geometry = transform_geometry(to_wgs84.transform, geometry)
        values = zscore[component]
        result.append(
            {
                "id": f"spatial-{len(result) + 1:03d}",
                "area_ha": area_ha,
                "min_zscore": float(np.nanmin(values)),
                "mean_zscore": float(np.nanmean(values)),
                "geometry": mapping(geometry),
            }
        )
    return sorted(result, key=lambda item: item["area_ha"], reverse=True)


def render_tile(path: Path, z: int, x: int, y: int, palette: str) -> bytes:
    half = 20037508.342789244
    size = 2 * half / (2 ** z)
    left = -half + x * size
    right = left + size
    top = half - y * size
    bottom = top - size
    transform = from_bounds(left, bottom, right, top, 256, 256)

    with rasterio.open(path) as source:
        with WarpedVRT(
            source,
            crs="EPSG:3857",
            transform=transform,
            width=256,
            height=256,
            resampling=Resampling.bilinear,
        ) as vrt:
            data = vrt.read(1, masked=True).astype(np.float32).filled(np.nan).astype(np.float32)

    rgba = _colorize(data, palette)
    output = BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG")
    return output.getvalue()


def _colorize(data: np.ndarray, palette: str) -> np.ndarray:
    finite = np.isfinite(data)
    if palette == "zscore":
        t = np.nan_to_num(np.clip((-data - 1.0) / 3.0, 0, 1), nan=0.0)
        low = np.array([230, 177, 66], dtype=float)
        high = np.array([220, 62, 47], dtype=float)
        rgb = (low * (1 - t[..., None]) + high * t[..., None]).astype(np.uint8)
        alpha = np.where(finite & (data < -1.0), 80 + 175 * t, 0).astype(np.uint8)
    elif palette == "quality":
        t = np.nan_to_num(np.clip(data, 0, 1), nan=0.0)
        low = np.array([110, 70, 50], dtype=float)
        high = np.array([70, 200, 135], dtype=float)
        rgb = (low * (1 - t[..., None]) + high * t[..., None]).astype(np.uint8)
        alpha = np.where(finite, 185, 0).astype(np.uint8)
    else:
        t = np.nan_to_num(np.clip((data + 0.1) / 0.9, 0, 1), nan=0.0)
        low = np.array([124, 76, 42], dtype=float)
        high = np.array([38, 145, 78], dtype=float)
        rgb = (low * (1 - t[..., None]) + high * t[..., None]).astype(np.uint8)
        alpha = np.where(finite, 210, 0).astype(np.uint8)
    return np.dstack([rgb, alpha])
