"""Shared observation acquisition used by every intelligence module.

One reusable pipeline: discover scene -> windowed AOI band reads -> cloud
mask -> RGB preview. Modules add their own indices, masks and change logic on
top of pixel-aligned arrays.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import numpy as np

from app.geospatial import indices
from app.geospatial.preview import render_rgb_png
from app.geospatial.raster import TargetGrid, aoi_mask, build_grid, cloud_mask_from_scl, read_band, read_rgb
from app.satellite.base import SceneMeta
from app.satellite.discovery import find_best_scene
from app.satellite.providers import get_provider
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

ProgressCB = Callable[[str, float], None]


class AnalysisError(RuntimeError):
    """User-facing analysis failure with a helpful message."""


@dataclass
class ObservationData:
    """Pixel-aligned bands and metadata for one scene over the AOI grid."""

    scene: SceneMeta
    grid: TargetGrid
    bands: dict[str, np.ndarray] = field(default_factory=dict)
    invalid: np.ndarray | None = None  # cloud/nodata mask
    preview_key: str | None = None

    def index(self, name: str) -> np.ndarray:
        b = self.bands
        if name == "ndvi":
            return indices.ndvi(b["nir"], b["red"])
        if name == "ndwi":
            return indices.ndwi(b["green"], b["nir"])
        if name == "mndwi":
            return indices.mndwi(b["green"], b["swir16"])
        if name == "evi":
            return indices.evi(b["nir"], b["red"], b["blue"])
        if name == "ndmi":
            return indices.ndmi(b["nir"], b["swir16"])
        if name == "bsi":
            return indices.bsi(b["swir16"], b["red"], b["nir"], b["blue"])
        if name == "nbr":
            return indices.nbr(b["nir"], b["swir22"])
        raise ValueError(f"Unknown index {name}")

    def provenance(self) -> dict:
        return {
            "provider": self.scene.provider,
            "scene_id": self.scene.external_id,
            "collection": self.scene.collection,
            "sensor": self.scene.sensor,
            "acquired_at": self.scene.acquired_at.isoformat(),
            "cloud_cover": self.scene.cloud_cover,
        }


def acquire_observation(
    aoi_geojson: dict,
    target_date: datetime,
    band_keys: list[str],
    grid: TargetGrid | None = None,
    provider_name: str | None = None,
    window_days: int = 60,
    max_cloud_cover: float | None = None,
    render_preview: bool = True,
) -> ObservationData:
    """Discover the best scene near target_date and read AOI-windowed bands."""
    scene = find_best_scene(
        aoi_geojson,
        target_date,
        window_days=window_days,
        provider_name=provider_name,
        max_cloud_cover=max_cloud_cover,
    )
    if scene is None:
        raise AnalysisError(
            f"No suitable satellite observation found near {target_date.date()} "
            f"(±{window_days} days) for this area. Try widening the date window "
            "or relaxing the cloud-cover limit."
        )
    if grid is None:
        grid = build_grid(aoi_geojson)

    provider = get_provider(scene.provider)
    obs = ObservationData(scene=scene, grid=grid)

    for key in band_keys:
        href = scene.assets.get(key)
        if not href:
            raise AnalysisError(
                f"Scene {scene.external_id} is missing required band '{key}'."
            )
        obs.bands[key] = read_band(provider.sign_href(href), grid)
        logger.info("event=band_read scene=%s band=%s", scene.external_id, key)

    # Cloud/quality mask from SCL when available.
    scl_href = scene.assets.get("scl")
    if scl_href:
        from rasterio.enums import Resampling

        scl = read_band(provider.sign_href(scl_href), grid, resampling=Resampling.nearest)
        obs.invalid = cloud_mask_from_scl(scl)
    else:
        first = next(iter(obs.bands.values()))
        obs.invalid = ~np.isfinite(first)

    if render_preview:
        try:
            signed = {k: provider.sign_href(v) for k, v in scene.assets.items() if k in ("visual", "red", "green", "blue")}
            rgb = read_rgb(signed, grid)
            if rgb is not None:
                key = f"previews/{scene.provider}/{scene.external_id}/{uuid.uuid4().hex[:8]}_rgb.png"
                get_storage().put(key, render_rgb_png(rgb))
                obs.preview_key = key
        except Exception as exc:
            logger.warning("event=preview_failed scene=%s error=%s", scene.external_id, exc)

    return obs


def layer_entry(key: str, kind: str, title: str, *, path: str | None = None, data: dict | None = None,
                bounds: tuple | None = None, style: dict | None = None) -> dict:
    """Normalized map-layer descriptor stored on the Analysis row."""
    entry: dict = {"key": key, "kind": kind, "title": title}
    if path:
        entry["path"] = path
    if data is not None:
        entry["data"] = data
    if bounds is not None:
        entry["bounds"] = list(bounds)
    if style:
        entry["style"] = style
    return entry
