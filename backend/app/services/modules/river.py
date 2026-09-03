"""River Intelligence module.

Water extent extraction via MNDWI (Xu, 2006) + Otsu segmentation on Sentinel-2
L2A, boundary change detection between a baseline and a current observation:
- erosion  = land -> water transitions
- accretion = water -> land transitions
- bank movement estimate from boundary displacement sampling.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

import numpy as np
from shapely.geometry import shape

from app.geospatial.masks import water_mask
from app.geospatial.measure import valid_fraction
from app.geospatial.preview import WATER_RAMP, render_index_png
from app.geospatial.raster import aoi_mask
from app.geospatial.vectorize import mask_to_geojson
from app.services.change_engine import confidence_from_quality, detect_mask_change
from app.services.modules.base import (
    AnalysisError,
    ObservationData,
    ProgressCB,
    acquire_observation,
    layer_entry,
)
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

BANDS = ["green", "nir", "swir16"]
METHOD = "MNDWI (Xu 2006) + Otsu segmentation; post-classification comparison"


def _estimate_bank_movement(change_area_m2: float, boundary_length_m: float) -> float | None:
    """Mean bank displacement ≈ transition area / shared boundary length."""
    if boundary_length_m <= 0:
        return None
    return change_area_m2 / boundary_length_m


def analyze(aoi_geojson: dict, params: dict, progress: ProgressCB) -> dict:
    baseline_date = datetime.fromisoformat(params["baseline_date"])
    current_date = datetime.fromisoformat(params["current_date"])
    provider = params.get("provider")
    max_cc = params.get("max_cloud_cover")

    progress("searching_imagery", 0.1)
    current = acquire_observation(aoi_geojson, current_date, BANDS, provider_name=provider, max_cloud_cover=max_cc)
    progress("retrieving_imagery", 0.3)
    baseline = acquire_observation(
        aoi_geojson, baseline_date, BANDS, grid=current.grid, provider_name=provider, max_cloud_cover=max_cc
    )

    progress("processing", 0.5)
    grid = current.grid
    aoi = aoi_mask(aoi_geojson, grid)

    mndwi_cur = current.index("mndwi")
    mndwi_base = baseline.index("mndwi")
    water_cur, t_cur = water_mask(mndwi_cur, current.invalid)
    water_base, t_base = water_mask(mndwi_base, baseline.invalid)
    water_cur &= aoi
    water_base &= aoi

    progress("calculating_changes", 0.65)
    valid = aoi & ~current.invalid & ~baseline.invalid
    change = detect_mask_change(water_base, water_cur, grid, valid=valid)
    # erosion = water gain over former land; accretion = land gain over former water
    erosion_m2 = change.gain_area_m2
    accretion_m2 = change.loss_area_m2

    years = max(abs((current.scene.acquired_at - baseline.scene.acquired_at).days) / 365.25, 1e-6)

    # Bank movement estimate from the shared water boundary.
    from rasterio.features import shapes as rio_shapes  # noqa: F401  (vectorize used below)

    boundary_len = None
    mean_movement = None
    try:
        base_union = None
        from app.geospatial.vectorize import mask_union_wgs84

        base_union = mask_union_wgs84(water_base, grid)
        if base_union is not None:
            from app.geospatial.measure import GEOD

            _, perimeter_m = GEOD.geometry_area_perimeter(base_union)
            boundary_len = abs(perimeter_m)
            mean_movement = _estimate_bank_movement(erosion_m2 + accretion_m2, boundary_len)
    except Exception as exc:
        logger.warning("event=bank_movement_failed error=%s", exc)

    vf_base = valid_fraction(baseline.invalid, aoi)
    vf_cur = valid_fraction(current.invalid, aoi)
    conf, level = confidence_from_quality(vf_base, vf_cur, baseline.scene.cloud_cover, current.scene.cloud_cover)

    progress("generating_layers", 0.8)
    storage = get_storage()
    run = uuid.uuid4().hex[:8]
    water_png_key = f"layers/river/{run}_water_current.png"
    storage.put(water_png_key, render_index_png(mndwi_cur, WATER_RAMP, mask=aoi))
    bounds = grid.bounds_wgs84()

    layers = [
        layer_entry("current_boundary", "geojson", "Current Water Extent",
                    data=mask_to_geojson(water_cur, grid), style={"color": "#0284c7", "fill": False}),
        layer_entry("baseline_boundary", "geojson", "Baseline Water Extent",
                    data=mask_to_geojson(water_base, grid), style={"color": "#475569", "dash": True, "fill": False}),
        layer_entry("erosion", "geojson", "Bank Erosion (land→water)",
                    data=change.gain_geojson, style={"color": "#ef4444", "fill": True}),
        layer_entry("accretion", "geojson", "Accretion / New Char (water→land)",
                    data=change.loss_geojson, style={"color": "#10b981", "fill": True}),
        layer_entry("mndwi", "raster", "MNDWI Water Index", path=water_png_key, bounds=bounds),
    ]
    if current.preview_key:
        layers.append(layer_entry("rgb_current", "raster", f"True Color {current.scene.acquired_at.date()}",
                                  path=current.preview_key, bounds=bounds))
    if baseline.preview_key:
        layers.append(layer_entry("rgb_baseline", "raster", f"True Color {baseline.scene.acquired_at.date()}",
                                  path=baseline.preview_key, bounds=bounds))

    detections = []
    for feat in change.gain_geojson["features"]:
        detections.append({
            "detection_type": "erosion",
            "geometry": feat["geometry"],
            "area_m2": feat["properties"]["area_m2"],
            "confidence": conf,
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {"period_years": round(years, 2)},
        })
    for feat in change.loss_geojson["features"]:
        detections.append({
            "detection_type": "accretion",
            "geometry": feat["geometry"],
            "area_m2": feat["properties"]["area_m2"],
            "confidence": conf,
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {"period_years": round(years, 2)},
        })

    measurements = {
        "river_area_current_km2": round(change.after_area_m2 / 1e6, 4),
        "river_area_baseline_km2": round(change.before_area_m2 / 1e6, 4),
        "area_difference_km2": round(change.net_area_m2 / 1e6, 4),
        "area_difference_pct": round(change.pct_change, 2) if change.pct_change is not None else None,
        "erosion_km2": round(erosion_m2 / 1e6, 4),
        "accretion_km2": round(accretion_m2 / 1e6, 4),
        "erosion_rate_km2_per_year": round(erosion_m2 / 1e6 / years, 4),
        "accretion_rate_km2_per_year": round(accretion_m2 / 1e6 / years, 4),
        "mean_bank_movement_m": round(mean_movement, 1) if mean_movement is not None else None,
        "movement_rate_m_per_year": round(mean_movement / years, 1) if mean_movement is not None else None,
        "mndwi_threshold_baseline": round(t_base, 3),
        "mndwi_threshold_current": round(t_cur, 3),
        "valid_data_fraction_baseline": round(vf_base, 3),
        "valid_data_fraction_current": round(vf_cur, 3),
        "period_years": round(years, 2),
    }

    return {
        "measurements": measurements,
        "layers": layers,
        "detections": detections,
        "confidence_score": conf,
        "confidence_level": level,
        "method": METHOD,
        "baseline_at": baseline.scene.acquired_at,
        "observed_at": current.scene.acquired_at,
        "provenance": {"baseline": baseline.provenance(), "current": current.provenance()},
        "limitations": (
            "Water extent derives from optical MNDWI segmentation; stage/discharge "
            "differences between acquisition dates can appear as change. Land-use "
            "change within the historical river boundary is reported as potential "
            "encroachment, not legal proof."
        ),
        "observations": [
            {"observed_at": baseline.scene.acquired_at, "measurements": {"water_area_km2": round(change.before_area_m2 / 1e6, 4)}, "preview_path": baseline.preview_key},
            {"observed_at": current.scene.acquired_at, "measurements": {"water_area_km2": round(change.after_area_m2 / 1e6, 4)}, "preview_path": current.preview_key},
        ],
    }
