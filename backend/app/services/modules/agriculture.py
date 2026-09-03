"""Agriculture Intelligence module.

Cultivated-area estimation and vegetation condition from Sentinel-2 spectral
indices (NDVI, EVI, NDMI), compared against a baseline observation. The
vegetation condition score is defined as the mean AOI NDVI linearly rescaled
from [0.2, 0.85] to [0, 100] — documented, not arbitrary.

No yield prediction is made: without ground truth (historical yields, crop
calendars, weather) only vegetation trend and relative indicators are
scientifically defensible.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

import numpy as np

from app.geospatial.masks import vegetation_mask
from app.geospatial.measure import valid_fraction
from app.geospatial.preview import NDVI_RAMP, render_index_png
from app.geospatial.raster import aoi_mask
from app.geospatial.vectorize import mask_to_geojson
from app.services.change_engine import confidence_from_quality, detect_mask_change, index_statistics
from app.services.modules.base import ProgressCB, acquire_observation, layer_entry
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

BANDS = ["blue", "green", "red", "nir", "swir16"]
METHOD = "Sentinel-2 L2A spectral indices (NDVI/EVI/NDMI); baseline comparison"


def condition_score(mean_ndvi: float | None) -> int | None:
    """Vegetation condition 0-100 := clamp((NDVI - 0.2) / 0.65) * 100."""
    if mean_ndvi is None:
        return None
    return int(round(float(np.clip((mean_ndvi - 0.2) / 0.65, 0, 1)) * 100))


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

    progress("analyzing", 0.55)
    grid = current.grid
    aoi = aoi_mask(aoi_geojson, grid)

    ndvi_cur = current.index("ndvi")
    ndvi_base = baseline.index("ndvi")
    evi_cur = current.index("evi")
    ndmi_cur = current.index("ndmi")
    ndwi_cur = current.index("ndwi")

    veg_cur = vegetation_mask(ndvi_cur, invalid=current.invalid) & aoi
    veg_base = vegetation_mask(ndvi_base, invalid=baseline.invalid) & aoi

    stats_cur = index_statistics(ndvi_cur, aoi, current.invalid)
    stats_base = index_statistics(ndvi_base, aoi, baseline.invalid)
    stats_evi = index_statistics(evi_cur, aoi, current.invalid)
    stats_ndmi = index_statistics(ndmi_cur, aoi, current.invalid)
    stats_ndwi = index_statistics(ndwi_cur, aoi, current.invalid)

    progress("calculating_changes", 0.7)
    valid = aoi & ~current.invalid & ~baseline.invalid
    change = detect_mask_change(veg_base, veg_cur, grid, valid=valid)

    # Anomaly: relative NDVI drop vs baseline observation.
    ndvi_drop_pct = None
    anomaly = False
    if stats_base["mean"] and stats_cur["mean"] is not None and stats_base["mean"] > 0.05:
        ndvi_drop_pct = round((stats_cur["mean"] - stats_base["mean"]) / stats_base["mean"] * 100.0, 1)
        anomaly = ndvi_drop_pct <= -15.0

    # Stress polygons: currently vegetated in baseline but NDVI dropped > 0.15
    stress = valid & veg_base & np.where(np.isfinite(ndvi_cur - ndvi_base), (ndvi_cur - ndvi_base) < -0.15, False)
    from app.geospatial.masks import clean_mask

    stress = clean_mask(stress, min_pixels=12)
    stress_geojson = mask_to_geojson(stress, grid, min_area_m2=2000.0)
    stress_area_ha = float(stress.sum()) * grid.resolution**2 / 1e4

    vf_base = valid_fraction(baseline.invalid, aoi)
    vf_cur = valid_fraction(current.invalid, aoi)
    conf, level = confidence_from_quality(vf_base, vf_cur, baseline.scene.cloud_cover, current.scene.cloud_cover)

    progress("generating_layers", 0.85)
    storage = get_storage()
    run = uuid.uuid4().hex[:8]
    ndvi_png = f"layers/agriculture/{run}_ndvi.png"
    storage.put(ndvi_png, render_index_png(ndvi_cur, NDVI_RAMP, mask=aoi))
    bounds = grid.bounds_wgs84()

    layers = [
        layer_entry("ndvi", "raster", "NDVI Spectral Gradient", path=ndvi_png, bounds=bounds),
        layer_entry("cultivated", "geojson", "Cultivated / Vegetated Boundary",
                    data=mask_to_geojson(veg_cur, grid, min_area_m2=5000.0),
                    style={"color": "#0369a1", "fill": False}),
        layer_entry("stress", "geojson", "Vegetation Stress Anomaly",
                    data=stress_geojson, style={"color": "#c2410c", "fill": True}),
    ]
    if current.preview_key:
        layers.append(layer_entry("rgb_current", "raster", f"True Color {current.scene.acquired_at.date()}",
                                  path=current.preview_key, bounds=bounds))
    if baseline.preview_key:
        layers.append(layer_entry("rgb_baseline", "raster", f"True Color {baseline.scene.acquired_at.date()}",
                                  path=baseline.preview_key, bounds=bounds))

    detections = [
        {
            "detection_type": "vegetation_stress",
            "geometry": feat["geometry"],
            "area_m2": feat["properties"]["area_m2"],
            "confidence": conf,
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {"delta_ndvi_threshold": -0.15},
        }
        for feat in stress_geojson["features"]
    ]

    measurements = {
        "cultivated_area_ha": round(change.after_area_m2 / 1e4, 1),
        "cultivated_area_baseline_ha": round(change.before_area_m2 / 1e4, 1),
        "cultivated_change_pct": round(change.pct_change, 2) if change.pct_change is not None else None,
        "mean_ndvi": stats_cur["mean"],
        "baseline_mean_ndvi": stats_base["mean"],
        "ndvi_change_pct": ndvi_drop_pct,
        "mean_evi": stats_evi["mean"],
        "mean_ndmi": stats_ndmi["mean"],
        "mean_ndwi": stats_ndwi["mean"],
        "vegetation_condition_score": condition_score(stats_cur["mean"]),
        "condition_score_method": "clamp((mean_NDVI - 0.2) / 0.65) * 100",
        "stress_area_ha": round(stress_area_ha, 1),
        "anomaly_detected": bool(anomaly),
        "ndvi_stats_current": stats_cur,
        "ndvi_stats_baseline": stats_base,
        "valid_data_fraction_baseline": round(vf_base, 3),
        "valid_data_fraction_current": round(vf_cur, 3),
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
            "Vegetation stress is a spectral indicator, not a disease or yield "
            "diagnosis. Crop-type classification and yield estimation require "
            "ground truth and multi-temporal training data not yet integrated. "
            "Seasonal phenology differences between the two dates can contribute "
            "to the measured NDVI change."
        ),
        "observations": [
            {"observed_at": baseline.scene.acquired_at, "measurements": {"mean_ndvi": stats_base["mean"], "cultivated_area_ha": round(change.before_area_m2 / 1e4, 1)}, "preview_path": baseline.preview_key},
            {"observed_at": current.scene.acquired_at, "measurements": {"mean_ndvi": stats_cur["mean"], "cultivated_area_ha": round(change.after_area_m2 / 1e4, 1)}, "preview_path": current.preview_key},
        ],
    }
