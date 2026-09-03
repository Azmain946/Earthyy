"""AOI-windowed raster access.

Reads only the pixels covering the area of interest from remote Cloud
Optimized GeoTIFFs (HTTP range requests via GDAL /vsicurl/). Full scenes are
never downloaded. All bands from all scenes are warped onto one common UTM
grid so arrays are pixel-aligned for change detection.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

logger = logging.getLogger(__name__)

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.jp2,.TIF",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": True,
    "VSI_CACHE_SIZE": 26214400,
    "GDAL_CACHEMAX": 256,
}


@dataclass
class TargetGrid:
    """A common analysis grid in a metric CRS covering the AOI."""

    crs: CRS
    transform: rasterio.Affine
    width: int
    height: int
    resolution: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        left = self.transform.c
        top = self.transform.f
        right = left + self.width * self.resolution
        bottom = top - self.height * self.resolution
        return (left, bottom, right, top)

    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) in EPSG:4326."""
        tr = Transformer.from_crs(self.crs, CRS.from_epsg(4326), always_xy=True)
        left, bottom, right, top = self.bounds
        xs, ys = tr.transform([left, right, left, right], [bottom, bottom, top, top])
        return (min(xs), min(ys), max(xs), max(ys))


def utm_crs_for(lon: float, lat: float) -> CRS:
    zone = int(math.floor((lon + 180) / 6) + 1)
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def build_grid(aoi_geojson: dict, resolution: float = 10.0, max_pixels: int = 6_000_000) -> TargetGrid:
    """Build a UTM analysis grid covering the AOI at the requested resolution.

    If the AOI would exceed `max_pixels`, the resolution is coarsened so that
    processing stays bounded (performance guard for very large zones).
    """
    geom = shape(aoi_geojson)
    lon, lat = geom.centroid.x, geom.centroid.y
    crs = utm_crs_for(lon, lat)
    tr = Transformer.from_crs(CRS.from_epsg(4326), crs, always_xy=True)
    geom_utm = shp_transform(tr.transform, geom)
    minx, miny, maxx, maxy = geom_utm.bounds
    # pad one pixel
    minx -= resolution
    miny -= resolution
    maxx += resolution
    maxy += resolution

    width = max(int(math.ceil((maxx - minx) / resolution)), 8)
    height = max(int(math.ceil((maxy - miny) / resolution)), 8)
    if width * height > max_pixels:
        scale = math.sqrt(width * height / max_pixels)
        resolution = resolution * scale
        width = max(int(math.ceil((maxx - minx) / resolution)), 8)
        height = max(int(math.ceil((maxy - miny) / resolution)), 8)
        logger.info("event=grid_coarsened resolution=%.1f pixels=%d", resolution, width * height)

    transform = from_origin(minx, maxy, resolution, resolution)
    return TargetGrid(crs=crs, transform=transform, width=width, height=height, resolution=resolution)


def read_band(href: str, grid: TargetGrid, resampling: Resampling = Resampling.bilinear) -> np.ndarray:
    """Windowed read of one remote COG band onto the target grid (float32).

    Nodata pixels are returned as NaN.
    """
    url = href if href.startswith("/vsicurl/") or not href.startswith("http") else f"/vsicurl/{href}"
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(url) as src:
            with WarpedVRT(
                src,
                crs=grid.crs,
                transform=grid.transform,
                width=grid.width,
                height=grid.height,
                resampling=resampling,
                nodata=src.nodata,
            ) as vrt:
                data = vrt.read(1).astype(np.float32)
                if src.nodata is not None:
                    data[data == src.nodata] = np.nan
                # Sentinel-2 L2A uses 0 as nodata even when untagged.
                data[data == 0] = np.nan
    return data


def read_rgb(hrefs: dict[str, str], grid: TargetGrid) -> np.ndarray | None:
    """Read a 3-band RGB stack; prefers the pre-rendered `visual` asset."""
    url = hrefs.get("visual")
    if url:
        vurl = f"/vsicurl/{url}" if url.startswith("http") else url
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(vurl) as src:
                    with WarpedVRT(
                        src,
                        crs=grid.crs,
                        transform=grid.transform,
                        width=grid.width,
                        height=grid.height,
                        resampling=Resampling.bilinear,
                    ) as vrt:
                        return vrt.read([1, 2, 3]).astype(np.float32)
        except Exception as exc:
            logger.warning("event=visual_read_failed error=%s", exc)
    bands = []
    for key in ("red", "green", "blue"):
        if key not in hrefs:
            return None
        bands.append(read_band(hrefs[key], grid))
    return np.stack(bands)


def aoi_mask(aoi_geojson: dict, grid: TargetGrid) -> np.ndarray:
    """Boolean mask of pixels inside the AOI polygon."""
    from rasterio.features import geometry_mask

    geom = shape(aoi_geojson)
    tr = Transformer.from_crs(CRS.from_epsg(4326), grid.crs, always_xy=True)
    geom_utm = shp_transform(tr.transform, geom)
    return ~geometry_mask(
        [geom_utm.__geo_interface__],
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        invert=False,
    )


def cloud_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    """Invalid-pixel mask from the Sentinel-2 Scene Classification Layer.

    True where the pixel is unusable: cloud shadow (3), cloud medium/high
    probability (8, 9), thin cirrus (10), snow (11), saturated/defective (1).
    """
    invalid = np.isin(scl, [1, 3, 8, 9, 10, 11])
    return invalid | np.isnan(scl)
