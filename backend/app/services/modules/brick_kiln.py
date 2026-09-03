"""Brick Kiln Intelligence module.

Candidate kiln-site screening from Sentinel-2 using a documented
spectral-morphological workflow (no fabricated detector accuracy):

1. Spectral gate: high Bare Soil Index, low NDVI, not water (kiln yards are
   large bare/fired-clay surfaces).
2. Morphological gate: connected components filtered to typical Bangladesh
   FCBTK/zigzag kiln yard footprints (0.3–6 ha) and compactness bounds.
3. Temporal comparison: candidates absent in the baseline observation are
   flagged as potential new kiln construction.

Every output is explicitly a *candidate* requiring verification; this module
is registered in the model registry with its limitations, and can be swapped
for a trained object detector without changing the API.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

import numpy as np
from pyproj import CRS, Transformer
from scipy import ndimage

from app.geospatial.masks import water_mask
from app.geospatial.measure import valid_fraction
from app.geospatial.raster import TargetGrid, aoi_mask
from app.services.change_engine import confidence_from_quality
from app.services.modules.base import ProgressCB, acquire_observation, layer_entry
from app.services.storage import get_storage
from app.geospatial.preview import render_index_png

logger = logging.getLogger(__name__)

BANDS = ["blue", "green", "red", "nir", "swir16"]
METHOD = "Spectral-morphological candidate screening (BSI+NDVI gate, footprint morphology filter)"

MIN_AREA_M2 = 3000.0     # ~0.3 ha
MAX_AREA_M2 = 60000.0    # ~6 ha
BSI_THRESHOLD = 0.05
NDVI_MAX = 0.25


def _candidate_mask(obs, aoi: np.ndarray) -> np.ndarray:
    ndvi = obs.index("ndvi")
    bsi = obs.index("bsi")
    mndwi = obs.index("mndwi")
    water, _ = water_mask(mndwi, obs.invalid)
    cand = (bsi > BSI_THRESHOLD) & (ndvi < NDVI_MAX) & ~water & aoi
    if obs.invalid is not None:
        cand &= ~obs.invalid
    return cand


def _extract_candidates(cand: np.ndarray, grid: TargetGrid) -> list[dict]:
    """Connected components -> filtered candidate features with centroid + shape."""
    labeled, n = ndimage.label(cand)
    if n == 0:
        return []
    tr = Transformer.from_crs(grid.crs, CRS.from_epsg(4326), always_xy=True)
    px_area = grid.resolution**2
    out = []
    objects = ndimage.find_objects(labeled)
    for i, slc in enumerate(objects, start=1):
        if slc is None:
            continue
        blob = labeled[slc] == i
        area_m2 = float(blob.sum()) * px_area
        if not (MIN_AREA_M2 <= area_m2 <= MAX_AREA_M2):
            continue
        h, w = blob.shape
        bbox_fill = blob.sum() / (h * w)
        aspect = max(h, w) / max(min(h, w), 1)
        # Kiln yards are compact-to-oval: reject stringy river banks/roads.
        if bbox_fill < 0.35 or aspect > 4.0:
            continue
        cy, cx = ndimage.center_of_mass(blob)
        row = slc[0].start + cy
        col = slc[1].start + cx
        x = grid.transform.c + (col + 0.5) * grid.resolution
        y = grid.transform.f - (row + 0.5) * grid.resolution
        lon, lat = tr.transform(x, y)
        out.append({
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "area_m2": round(area_m2, 1),
            "bbox_fill": round(float(bbox_fill), 2),
            "aspect_ratio": round(float(aspect), 2),
        })
    return out


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

    cand_cur_mask = _candidate_mask(current, aoi)
    cand_base_mask = _candidate_mask(baseline, aoi)
    candidates = _extract_candidates(cand_cur_mask, grid)
    baseline_candidates = _extract_candidates(cand_base_mask, grid)

    progress("calculating_changes", 0.7)
    # New-candidate detection: no baseline candidate centroid within 150 m.
    def near_existing(c) -> bool:
        for b in baseline_candidates:
            if abs(b["lon"] - c["lon"]) < 0.0015 and abs(b["lat"] - c["lat"]) < 0.0014:
                return True
        return False

    for c in candidates:
        c["is_new"] = not near_existing(c)

    vf_base = valid_fraction(baseline.invalid, aoi)
    vf_cur = valid_fraction(current.invalid, aoi)
    data_conf, _ = confidence_from_quality(vf_base, vf_cur, baseline.scene.cloud_cover, current.scene.cloud_cover)
    # Candidate screening has no validated accuracy: cap confidence and mark low.
    conf = round(min(data_conf or 0.0, 0.5), 2) if data_conf is not None else None
    level = "low" if conf is not None else "unavailable"

    progress("generating_layers", 0.85)
    bounds = grid.bounds_wgs84()
    storage = get_storage()
    run = uuid.uuid4().hex[:8]
    bsi_png = f"layers/brick_kiln/{run}_bsi.png"
    BSI_RAMP = [(-0.3, (30, 60, 30)), (0.0, (222, 210, 170)), (0.3, (181, 56, 1))]
    storage.put(bsi_png, render_index_png(current.index("bsi"), BSI_RAMP, mask=aoi))

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            "properties": {
                "area_m2": c["area_m2"],
                "is_new": c["is_new"],
                "status": "candidate",
            },
        }
        for c in candidates
    ]
    layers = [
        layer_entry("kiln_candidates", "geojson", "Candidate Kiln Sites",
                    data={"type": "FeatureCollection", "features": features},
                    style={"color": "#b53801", "marker": True}),
        layer_entry("bsi", "raster", "Bare Soil Index", path=bsi_png, bounds=bounds),
    ]
    if current.preview_key:
        layers.append(layer_entry("rgb_current", "raster", f"True Color {current.scene.acquired_at.date()}",
                                  path=current.preview_key, bounds=bounds))
    if baseline.preview_key:
        layers.append(layer_entry("rgb_baseline", "raster", f"True Color {baseline.scene.acquired_at.date()}",
                                  path=baseline.preview_key, bounds=bounds))

    detections = [
        {
            "detection_type": "kiln_candidate",
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            "area_m2": c["area_m2"],
            "confidence": conf,
            "status": "candidate",
            "observed_at": current.scene.acquired_at.isoformat(),
            "properties": {
                "is_new": c["is_new"],
                "bbox_fill": c["bbox_fill"],
                "aspect_ratio": c["aspect_ratio"],
            },
        }
        for c in candidates
    ]

    new_count = sum(1 for c in candidates if c["is_new"])
    measurements = {
        "candidate_count": len(candidates),
        "baseline_candidate_count": len(baseline_candidates),
        "new_candidate_count": new_count,
        "candidate_total_area_ha": round(sum(c["area_m2"] for c in candidates) / 1e4, 2),
        "spectral_gate": {"bsi_gt": BSI_THRESHOLD, "ndvi_lt": NDVI_MAX},
        "footprint_filter_m2": [MIN_AREA_M2, MAX_AREA_M2],
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
            "Candidate screening only: bright bare-soil surfaces (construction "
            "sites, sand deposits, dried ponds) can produce false positives, and "
            "kilns under vegetation regrowth can be missed. No validated detection "
            "accuracy is claimed — candidates require independent verification "
            "(status='candidate'). Pollution attribution to individual kilns is "
            "not scientifically supportable with this data and is not reported."
        ),
        "observations": [
            {"observed_at": baseline.scene.acquired_at, "measurements": {"candidate_count": len(baseline_candidates)}, "preview_path": baseline.preview_key},
            {"observed_at": current.scene.acquired_at, "measurements": {"candidate_count": len(candidates)}, "preview_path": current.preview_key},
        ],
    }
