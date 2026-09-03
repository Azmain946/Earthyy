"""Earthyy Change Engine.

Reusable spatial/temporal change detection over pixel-aligned boolean masks.
All four modules call this engine: river (water masks), forest (canopy masks),
agriculture (vegetation masks) and brick kiln (candidate footprints via the
object strategy).

Strategies:
- SpectralChangeDetector: index difference between two dates.
- BoundaryChangeDetector: class-mask transition analysis (gain/loss polygons).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.geospatial.masks import clean_mask
from app.geospatial.measure import mask_area_m2
from app.geospatial.raster import TargetGrid
from app.geospatial.vectorize import mask_to_geojson


@dataclass
class MaskChangeResult:
    """Result of comparing a `before` and `after` boolean mask."""

    before_area_m2: float
    after_area_m2: float
    loss_area_m2: float  # before=True  -> after=False
    gain_area_m2: float  # before=False -> after=True
    net_area_m2: float
    pct_change: float | None
    loss_mask: np.ndarray = field(repr=False, default=None)
    gain_mask: np.ndarray = field(repr=False, default=None)
    loss_geojson: dict = field(default_factory=dict)
    gain_geojson: dict = field(default_factory=dict)


def detect_mask_change(
    before: np.ndarray,
    after: np.ndarray,
    grid: TargetGrid,
    valid: np.ndarray | None = None,
    min_change_pixels: int = 12,
    min_polygon_m2: float = 2000.0,
) -> MaskChangeResult:
    """Boundary/class change detection between two aligned boolean masks.

    Pixels flagged invalid (clouds/nodata on either date) are excluded from
    both change classes so cloud edges are not reported as change.
    """
    if valid is None:
        valid = np.ones_like(before, dtype=bool)

    before_v = before & valid
    after_v = after & valid
    loss = clean_mask(before_v & ~after & valid, min_pixels=min_change_pixels)
    gain = clean_mask(~before & after_v & valid, min_pixels=min_change_pixels)

    res = grid.resolution
    before_area = mask_area_m2(before_v, res)
    after_area = mask_area_m2(after_v, res)
    loss_area = mask_area_m2(loss, res)
    gain_area = mask_area_m2(gain, res)
    pct = None
    if before_area > 0:
        pct = (after_area - before_area) / before_area * 100.0

    return MaskChangeResult(
        before_area_m2=before_area,
        after_area_m2=after_area,
        loss_area_m2=loss_area,
        gain_area_m2=gain_area,
        net_area_m2=after_area - before_area,
        pct_change=pct,
        loss_mask=loss,
        gain_mask=gain,
        loss_geojson=mask_to_geojson(loss, grid, min_area_m2=min_polygon_m2),
        gain_geojson=mask_to_geojson(gain, grid, min_area_m2=min_polygon_m2),
    )


def index_statistics(index: np.ndarray, aoi: np.ndarray, invalid: np.ndarray | None = None) -> dict:
    """Robust statistics of a spectral index over the AOI."""
    sel = aoi.copy()
    if invalid is not None:
        sel &= ~invalid
    values = index[sel]
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"mean": None, "median": None, "p10": None, "p90": None, "std": None, "n": 0}
    return {
        "mean": round(float(np.mean(values)), 4),
        "median": round(float(np.median(values)), 4),
        "p10": round(float(np.percentile(values, 10)), 4),
        "p90": round(float(np.percentile(values, 90)), 4),
        "std": round(float(np.std(values)), 4),
        "n": int(values.size),
    }


def confidence_from_quality(
    valid_fraction_before: float,
    valid_fraction_after: float,
    cloud_before: float | None,
    cloud_after: float | None,
) -> tuple[float | None, str]:
    """Data-quality-derived confidence for change results.

    This is *not* a model accuracy claim: it quantifies how much of the AOI
    had usable (cloud-free, valid) observations on both dates, discounted by
    scene-level cloud cover. When data quality is too poor to be meaningful
    the confidence is reported as unavailable.
    """
    vf = min(valid_fraction_before, valid_fraction_after)
    if vf <= 0.2:
        return None, "unavailable"
    cloud_penalty = 0.0
    for c in (cloud_before, cloud_after):
        if c is not None:
            cloud_penalty += min(c, 100.0) / 100.0 * 0.15
    score = max(0.0, min(1.0, vf - cloud_penalty))
    level = "high" if score >= 0.85 else "medium" if score >= 0.6 else "low"
    return round(score, 2), level
