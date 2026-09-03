"""Scene discovery and selection.

Implements the discovery workflow: AOI geometry -> STAC search -> filter ->
rank -> persist metadata. Ranking prefers low cloud cover, full AOI coverage
and proximity to the target date.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.scene import SatelliteScene
from app.satellite.base import SceneMeta
from app.satellite.providers import get_provider

logger = logging.getLogger(__name__)
settings = get_settings()


def rank_scenes(scenes: list[SceneMeta], aoi_geojson: dict, target_date: datetime | None = None) -> list[SceneMeta]:
    """Rank scenes: coverage of AOI (most important), cloud cover, date proximity."""
    aoi = shape(aoi_geojson)

    def score(s: SceneMeta) -> float:
        footprint = shape(s.geometry)
        coverage = aoi.intersection(footprint).area / max(aoi.area, 1e-12)
        cloud = (s.cloud_cover if s.cloud_cover is not None else 50.0) / 100.0
        date_penalty = 0.0
        if target_date is not None:
            days = abs((s.acquired_at.replace(tzinfo=None) - target_date.replace(tzinfo=None)).days)
            date_penalty = min(days / 365.0, 1.0)
        return coverage * 3.0 - cloud * 1.5 - date_penalty * 0.5

    return sorted(scenes, key=score, reverse=True)


def find_best_scene(
    aoi_geojson: dict,
    target_date: datetime,
    window_days: int = 45,
    provider_name: str | None = None,
    collections: list[str] | None = None,
    max_cloud_cover: float | None = None,
) -> SceneMeta | None:
    """Find the most suitable scene near `target_date` for the AOI.

    Searches a window around the target date, progressively relaxing the cloud
    filter if nothing suitable is found (monsoon-season Bangladesh often needs
    this).
    """
    provider = get_provider(provider_name)
    max_cc = max_cloud_cover if max_cloud_cover is not None else settings.default_max_cloud_cover
    start = target_date - timedelta(days=window_days)
    end = target_date + timedelta(days=window_days)

    for cloud_limit in (max_cc, 60.0, 90.0, None):
        scenes = provider.search(
            geometry=aoi_geojson,
            start=start,
            end=end,
            collections=collections,
            max_cloud_cover=cloud_limit,
            limit=50,
        )
        # Require usable AOI coverage (>60%).
        aoi = shape(aoi_geojson)
        usable = [
            s for s in scenes
            if shape(s.geometry).intersection(aoi).area / max(aoi.area, 1e-12) > 0.6
        ]
        if usable:
            ranked = rank_scenes(usable, aoi_geojson, target_date)
            best = ranked[0]
            logger.info(
                "event=scene_selected provider=%s scene=%s cloud=%s date=%s",
                best.provider, best.external_id, best.cloud_cover, best.acquired_at.date(),
            )
            return best
        if cloud_limit is None:
            break
    logger.warning("event=no_scene_found target=%s window_days=%s", target_date.date(), window_days)
    return None


def persist_scene(db: Session, meta: SceneMeta) -> SatelliteScene:
    """Store or refresh scene metadata in the database (cache layer)."""
    from geoalchemy2.shape import from_shape

    existing = (
        db.query(SatelliteScene)
        .filter_by(provider=meta.provider, external_id=meta.external_id)
        .first()
    )
    if existing:
        return existing
    scene = SatelliteScene(
        provider=meta.provider,
        external_id=meta.external_id,
        collection=meta.collection,
        sensor=meta.sensor,
        acquired_at=meta.acquired_at,
        cloud_cover=meta.cloud_cover,
        geometry=from_shape(shape(meta.geometry), srid=4326),
        assets=meta.assets,
        properties=meta.properties,
    )
    db.add(scene)
    db.flush()
    return scene
