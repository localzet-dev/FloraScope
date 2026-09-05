import numpy as np

from florascope_core.eo.raster import normalized_difference


def test_normalized_difference_handles_zero_denominator() -> None:
    result = normalized_difference(np.array([0.8, 0.0]), np.array([0.2, 0.0]))
    assert np.isclose(result[0], 0.6)
    assert np.isnan(result[1])


def test_integer_nodata_and_outside_scene_are_nan(tmp_path):
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from florascope_core.eo.raster import Grid, read_asset

    path = tmp_path / 'integer.tif'
    transform = from_origin(0, 40, 20, 20)
    with rasterio.open(path, 'w', driver='GTiff', width=2, height=2,
                       count=1, dtype='uint16', crs='EPSG:32637',
                       transform=transform, nodata=0) as dst:
        dst.write(np.array([[1000, 0], [2000, 3000]], dtype=np.uint16), 1)
    grid = Grid(rasterio.crs.CRS.from_epsg(32637), transform, 3, 3, 20)
    result = read_asset(str(path), grid, resampling=Resampling.nearest)
    assert result[0, 0] == 1000
    assert np.isnan(result[0, 1])
    assert np.isnan(result[2, :]).all()
    assert np.isnan(result[:, 2]).all()


def test_sentinel_quality_is_pixel_mask_plus_finite_ndvi(monkeypatch):
    from datetime import datetime
    import rasterio
    from rasterio.transform import from_origin
    from florascope_core.eo import sentinel2
    from florascope_core.eo.raster import Grid
    from florascope_core.eo.models import SceneRef, AssetRef
    arrays = {key: np.full((2, 2), .3, dtype=np.float32) for key in sentinel2.ASSET_NAMES}
    arrays['scl'] = np.array([[4, 9], [4, 0]], dtype=np.float32)
    arrays['nir'][0, 0] = .6
    arrays['nir'][1, 0] = np.nan
    monkeypatch.setattr(sentinel2, 'read_asset', lambda href, *args, **kwargs: arrays[href])
    monkeypatch.setattr(sentinel2, 'polygon_mask', lambda *args: np.ones((2, 2), dtype=bool))
    scene = SceneRef('quality', 'sentinel-2', datetime(2024, 6, 1), 0,
                     {key: AssetRef(key, 1, 0) for key in arrays})
    grid = Grid(rasterio.crs.CRS.from_epsg(32637), from_origin(0, 40, 20, 20), 2, 2, 20)
    observed = sentinel2.Sentinel2Provider('unused').read(scene, {}, grid, keep_rasters=True)
    assert observed.valid_fraction == .25
    assert np.isclose(observed.indices['ndvi'], 1 / 3)
    assert np.isfinite(observed.rasters['ndvi']).sum() == 1
