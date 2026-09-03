"""Raster mask -> vector GeoJSON conversion and geometry utilities."""
from __future__ import annotations

import numpy as np
from pyproj import CRS, Transformer
from rasterio import features
from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform, unary_union

from app.geospatial.raster import TargetGrid


def mask_to_geojson(
    mask: np.ndarray,
    grid: TargetGrid,
    min_area_m2: float = 900.0,
    simplify_m: float = 10.0,
) -> dict:
    """Vectorize a boolean mask into a GeoJSON FeatureCollection (EPSG:4326).

    Small slivers below `min_area_m2` are dropped; geometries are simplified
    before being sent to the browser.
    """
    tr = Transformer.from_crs(grid.crs, CRS.from_epsg(4326), always_xy=True)
    feats = []
    for geom_dict, value in features.shapes(mask.astype(np.uint8), transform=grid.transform):
        if value != 1:
            continue
        geom = shape(geom_dict)
        if geom.area < min_area_m2:
            continue
        geom = geom.simplify(simplify_m, preserve_topology=True)
        geom_ll = shp_transform(tr.transform, geom)
        feats.append(
            {
                "type": "Feature",
                "geometry": mapping(geom_ll),
                "properties": {"area_m2": round(float(geom.area), 1)},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def mask_union_wgs84(mask: np.ndarray, grid: TargetGrid, min_area_m2: float = 900.0):
    """Union of all mask polygons as one shapely geometry in EPSG:4326 (or None)."""
    tr = Transformer.from_crs(grid.crs, CRS.from_epsg(4326), always_xy=True)
    geoms = []
    for geom_dict, value in features.shapes(mask.astype(np.uint8), transform=grid.transform):
        if value != 1:
            continue
        geom = shape(geom_dict)
        if geom.area < min_area_m2:
            continue
        geoms.append(geom)
    if not geoms:
        return None
    merged = unary_union(geoms).simplify(10.0, preserve_topology=True)
    return shp_transform(tr.transform, merged)
