"""Geodesically-correct measurement utilities."""
from __future__ import annotations

import numpy as np
from pyproj import Geod
from shapely.geometry import shape

GEOD = Geod(ellps="WGS84")


def geodesic_area_km2(geojson_geometry: dict) -> float:
    """Geodesic area of a GeoJSON (multi)polygon in km² (WGS84 ellipsoid)."""
    geom = shape(geojson_geometry)
    area_m2, _ = GEOD.geometry_area_perimeter(geom)
    return abs(area_m2) / 1e6


def mask_area_m2(mask: np.ndarray, resolution: float) -> float:
    """Area of True pixels in m² given grid resolution in metres."""
    return float(mask.sum()) * resolution * resolution


def valid_fraction(invalid: np.ndarray, aoi: np.ndarray) -> float:
    """Fraction of AOI pixels with valid (non-cloud, non-nodata) data."""
    total = int(aoi.sum())
    if total == 0:
        return 0.0
    return float((aoi & ~invalid).sum()) / total
