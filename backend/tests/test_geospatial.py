"""Unit tests for geospatial computations (no network required)."""
import numpy as np
import pytest
from shapely.geometry import box, mapping

from app.geospatial.indices import bsi, evi, mndwi, ndvi, ndwi
from app.geospatial.masks import clean_mask, otsu_threshold, water_mask
from app.geospatial.measure import geodesic_area_km2, mask_area_m2, valid_fraction
from app.geospatial.raster import build_grid, utm_crs_for, aoi_mask
from app.geospatial.vectorize import mask_to_geojson
from app.services.change_engine import confidence_from_quality, detect_mask_change, index_statistics


AOI = mapping(box(89.70, 23.72, 89.74, 23.76))  # ~4x4 km near Padma


class TestIndices:
    def test_ndvi_range(self):
        nir = np.array([[3000.0, 500.0]])
        red = np.array([[1000.0, 2000.0]])
        result = ndvi(nir, red)
        assert result[0, 0] == pytest.approx(0.5, abs=0.01)
        assert result[0, 1] < 0

    def test_mndwi_water_positive(self):
        green = np.array([[2000.0]])
        swir = np.array([[500.0]])
        assert mndwi(green, swir)[0, 0] > 0.5

    def test_ndwi_symmetry(self):
        g = np.array([[1500.0]])
        n = np.array([[1500.0]])
        assert ndwi(g, n)[0, 0] == pytest.approx(0.0, abs=1e-3)

    def test_evi_reasonable(self):
        v = evi(np.array([[4000.0]]), np.array([[1000.0]]), np.array([[500.0]]))
        assert 0.0 < v[0, 0] < 1.5

    def test_bsi_bare_soil_positive(self):
        v = bsi(swir16=np.array([[3500.0]]), red=np.array([[2500.0]]),
                nir=np.array([[2000.0]]), blue=np.array([[800.0]]))
        assert v[0, 0] > 0


class TestGrid:
    def test_utm_zone_bangladesh(self):
        crs = utm_crs_for(89.75, 23.76)
        assert crs.to_epsg() == 32645  # UTM 45N

    def test_build_grid_resolution(self):
        grid = build_grid(AOI, resolution=10.0)
        assert grid.resolution == 10.0
        # ~4 km AOI -> ~400-460 px (lat/lon aspect + padding)
        assert 380 <= grid.width <= 470
        assert 380 <= grid.height <= 470

    def test_grid_pixel_guard(self):
        big = mapping(box(88.0, 22.0, 91.0, 25.0))
        grid = build_grid(big, resolution=10.0, max_pixels=1_000_000)
        assert grid.width * grid.height <= 1_100_000
        assert grid.resolution > 10.0

    def test_aoi_mask_covers_interior(self):
        grid = build_grid(AOI, resolution=20.0)
        mask = aoi_mask(AOI, grid)
        assert 0.9 < mask.mean() <= 1.0  # bbox AOI fills nearly the whole grid

    def test_bounds_wgs84_round_trip(self):
        grid = build_grid(AOI, resolution=10.0)
        w, s, e, n = grid.bounds_wgs84()
        assert w == pytest.approx(89.70, abs=0.01)
        assert n == pytest.approx(23.76, abs=0.01)


class TestMeasure:
    def test_geodesic_area_1deg_box(self):
        # 0.1 x 0.1 deg box at equator ~ 123 km²
        area = geodesic_area_km2(mapping(box(0, 0, 0.1, 0.1)))
        assert area == pytest.approx(123, rel=0.05)

    def test_mask_area(self):
        mask = np.zeros((10, 10), dtype=bool)
        mask[:5, :5] = True
        assert mask_area_m2(mask, 10.0) == 25 * 100

    def test_valid_fraction(self):
        aoi = np.ones((4, 4), dtype=bool)
        invalid = np.zeros((4, 4), dtype=bool)
        invalid[0] = True
        assert valid_fraction(invalid, aoi) == pytest.approx(0.75)


class TestMasks:
    def test_otsu_separates_bimodal(self):
        vals = np.concatenate([np.random.normal(-0.4, 0.05, 3000), np.random.normal(0.5, 0.05, 3000)])
        t = otsu_threshold(vals)
        # any split strictly between the two modes is a valid separation
        assert -0.3 < t < 0.4

    def test_water_mask_threshold_clamped(self):
        arr = np.random.normal(-0.5, 0.02, (100, 100)).astype(np.float32)  # all land
        mask, t = water_mask(arr)
        assert -0.05 <= t <= 0.35
        assert mask.mean() < 0.05

    def test_clean_mask_removes_specks(self):
        mask = np.zeros((50, 50), dtype=bool)
        mask[0, 0] = True  # single speck
        mask[10:20, 10:20] = True  # solid block
        cleaned = clean_mask(mask, min_pixels=10)
        assert not cleaned[0, 0]
        assert cleaned[15, 15]


class TestChangeEngine:
    def _grid(self):
        return build_grid(AOI, resolution=20.0)

    def test_gain_loss_detection(self):
        grid = self._grid()
        h, w = grid.height, grid.width
        before = np.zeros((h, w), dtype=bool)
        after = np.zeros((h, w), dtype=bool)
        before[10:60, 10:60] = True          # will be partially lost
        after[10:60, 10:35] = True           # loss on right half
        after[100:150, 100:150] = True       # new gain
        result = detect_mask_change(before, after, grid)
        assert result.loss_area_m2 > 0
        assert result.gain_area_m2 > 0
        assert result.loss_geojson["features"]
        assert result.gain_geojson["features"]
        assert result.net_area_m2 == pytest.approx(result.after_area_m2 - result.before_area_m2)

    def test_invalid_pixels_excluded(self):
        grid = self._grid()
        h, w = grid.height, grid.width
        before = np.zeros((h, w), dtype=bool)
        after = np.zeros((h, w), dtype=bool)
        before[10:60, 10:60] = True
        valid = np.ones((h, w), dtype=bool)
        valid[10:60, 10:60] = False  # cloud over the whole changed area
        result = detect_mask_change(before, after, grid, valid=valid)
        assert result.loss_area_m2 == 0

    def test_index_statistics(self):
        arr = np.full((10, 10), 0.5, dtype=np.float32)
        aoi = np.ones((10, 10), dtype=bool)
        stats = index_statistics(arr, aoi)
        assert stats["mean"] == pytest.approx(0.5)
        assert stats["n"] == 100

    def test_confidence_unavailable_when_data_poor(self):
        score, level = confidence_from_quality(0.1, 0.9, 5.0, 5.0)
        assert score is None
        assert level == "unavailable"

    def test_confidence_high_when_clean(self):
        score, level = confidence_from_quality(0.99, 0.98, 1.0, 2.0)
        assert score is not None and score > 0.85
        assert level == "high"


class TestVectorize:
    def test_mask_to_geojson_min_area(self):
        grid = build_grid(AOI, resolution=20.0)
        mask = np.zeros((grid.height, grid.width), dtype=bool)
        mask[10:40, 10:40] = True  # 30x30 px * 400 m² = 360000 m²
        fc = mask_to_geojson(mask, grid, min_area_m2=1000.0)
        assert len(fc["features"]) == 1
        assert fc["features"][0]["properties"]["area_m2"] == pytest.approx(360000, rel=0.05)
        # coordinates are lon/lat
        coords = fc["features"][0]["geometry"]["coordinates"][0][0]
        assert 89 < coords[0] < 90 and 23 < coords[1] < 24
