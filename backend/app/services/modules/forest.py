"""Forest Intelligence module.

Dense-canopy mapping from Sentinel-2 NDVI thresholding with morphological
cleaning, plus NBR as a disturbance indicator, and canopy loss/gain change
detection against a baseline observation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.geospatial.masks import forest_mask
from app.geospatial.measure import valid_fraction
from app.geospatial.preview import NDVI_RAMP, render_index_png
from app.geospatial.raster import aoi_mask
from app.geospatial.vectorize import mask_to_geojson
from app.services.change_engine import confidence_from_quality, detect_mask_change, index_statistics
from app.services.modules.base import ProgressCB, acquire_observation, layer_entry
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

BANDS = ["red", "nir", "swir22"]
METHOD = "NDVI-threshold canopy mask (θ=0.6) + morphological cleaning; NBR disturbance; post-classification comparison"


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
    nbr_cur = current.index("nbr")
    nbr_base = baseline.index("nbr")

    forest_cur = forest_mask(ndvi_cur, invalid=current.invalid) & aoi
    forest_base = forest_mask(ndvi_base, invalid=baseline.invalid) & aoi

    progress("calculating_changes", 0.7)
    valid = aoi & ~current.invalid & ~baseline.invalid
    change = detect_mask_change(forest_base, forest_cur, grid, valid=valid, min_polygon_m2=3000.0)

    loss_ha = change.loss_area_m2 / 1e4
    gain_ha = change.gain_area_m2 / 1e4
    years = max(abs((current.scene.acquired_at - baseline.scene.acquired_at).days) / 365.25, 1e-6)

    stats_ndvi = index_statistics(ndvi_cur, aoi, current.invalid)
    stats_ndvi_base = index_statistics(ndvi_base, aoi, baseline.invalid)
    dnbr = index_statistics(nbr_base - nbr_cur, aoi & valid, None)

    vf_base = valid_fraction(baseline.invalid, aoi)
    vf_cur = valid_fraction(current.invalid, aoi)
    conf, level = confidence_from_quality(vf_base, vf_cur, baseline.scene.cloud_cover, current.scene.cloud_cover)

    progress("generating_layers", 0.85)
    storage = get_storage()
    run = uuid.uuid4().hex[:8]
    ndvi_png = f"layers/forest/{run}_ndvi.png"
    storage.put(ndvi_png, render_index_png(ndvi_cur, NDVI_RAMP, mask=aoi))
    bounds = grid.bounds_wgs84()

    layers = [
        layer_entry("forest_current", "geojson", "Dense Canopy Boundary (current)",
                    data=mask_to_geojson(forest_cur, grid, min_area_m2=10000.0),
                    style={"color": "#006d30", "fill": False}),
        layer_entry("forest_loss", "geojson", "Canopy Disturbance / Loss",
                    data=change.loss_geojson, style={"color": "#ba1a1a", "fill": True}),
        layer_entry("forest_gain", "geojson", "Canopy Gain / Regrowth",
                    data=change.gain_geojson, style={"color": "#10b981", "fill": True}),
        layer_entry("ndvi", "raster", "NDVI Canopy Integrity", path=ndvi_png, bounds=bounds),
    ]
    if current.preview_key:
        layers.append(layer_entry("rgb_current", "raster", f"True Color {current.scene.acquired_at.date()}",
                                  path=current.preview_key, bounds=bounds))
    if baseline.preview_key:
        layers.append(layer_entry("rgb_baseline", "raster", f"True Color {baseline.scene.acquired_at.date()}",
                                  path=baseline.preview_key, bounds=bounds))

    detections = []
    for feat in change.loss_geojson["features"]:
        detections.append({
            "detection_type": "forest_loss",
            "geometry": feat["geometry"],
            "area_m2": feat["properties"]["area_m2"],
            "confidence": conf,
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {"period_years": round(years, 2)},
        })
    for feat in change.gain_geojson["features"]:
        detections.append({
            "detection_type": "forest_gain",
            "geometry": feat["geometry"],
            "area_m2": feat["properties"]["area_m2"],
            "confidence": conf,
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {"period_years": round(years, 2)},
        })

    measurements = {
        "forest_area_current_ha": round(change.after_area_m2 / 1e4, 1),
        "forest_area_baseline_ha": round(change.before_area_m2 / 1e4, 1),
        "forest_loss_ha": round(loss_ha, 2),
        "forest_gain_ha": round(gain_ha, 2),
        "net_change_ha": round((change.after_area_m2 - change.before_area_m2) / 1e4, 2),
        "loss_rate_ha_per_year": round(loss_ha / years, 2),
        "change_pct": round(change.pct_change, 2) if change.pct_change is not None else None,
        "mean_ndvi": stats_ndvi["mean"],
        "baseline_mean_ndvi": stats_ndvi_base["mean"],
        "mean_dnbr": dnbr["mean"],
        "period_years": round(years, 2),
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
            "Canopy mapping uses an NDVI-threshold proxy, which can confuse dense "
            "cropland with forest in some seasons. Detected loss is reported as "
            "'forest-cover change' / 'potential forest loss' — no claim of illegal "
            "logging is made. Cloud-contaminated pixels are excluded on both dates."
        ),
        "observations": [
            {"observed_at": baseline.scene.acquired_at, "measurements": {"forest_area_ha": round(change.before_area_m2 / 1e4, 1), "mean_ndvi": stats_ndvi_base["mean"]}, "preview_path": baseline.preview_key},
            {"observed_at": current.scene.acquired_at, "measurements": {"forest_area_ha": round(change.after_area_m2 / 1e4, 1), "mean_ndvi": stats_ndvi["mean"]}, "preview_path": current.preview_key},
        ],
    }
