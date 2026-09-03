import json
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.satellite.base import ProviderError
from app.satellite.discovery import persist_scene
from app.satellite.providers import get_provider
from app.schemas.common import SceneOut
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/satellite", tags=["satellite"])


@router.get("/scenes", response_model=list[SceneOut])
def search_scenes(
    bbox: str = Query(..., description="west,south,east,north (EPSG:4326)"),
    start: date = Query(...),
    end: date = Query(...),
    provider: str = "earth_search",
    collections: str | None = None,
    max_cloud_cover: float | None = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Live STAC catalogue search (results cached and persisted as metadata)."""
    try:
        w, s, e, n = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox must be 'west,south,east,north'")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise HTTPException(422, "bbox out of range")

    geometry = {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }
    cache_key = f"stac:{provider}:{bbox}:{start}:{end}:{collections}:{max_cloud_cover}"
    cached = cache_get(cache_key)
    if cached:
        return [SceneOut(**s) for s in json.loads(cached)]

    try:
        prov = get_provider(provider)
        scenes = prov.search(
            geometry=geometry,
            start=datetime.combine(start, time.min, tzinfo=timezone.utc),
            end=datetime.combine(end, time.max, tzinfo=timezone.utc),
            collections=collections.split(",") if collections else None,
            max_cloud_cover=max_cloud_cover,
            limit=60,
        )
    except ProviderError as exc:
        raise HTTPException(502, str(exc))

    out = []
    for meta in scenes:
        row = persist_scene(db, meta)
        out.append(SceneOut(
            id=row.id, provider=meta.provider, external_id=meta.external_id,
            collection=meta.collection, sensor=meta.sensor, acquired_at=meta.acquired_at,
            cloud_cover=meta.cloud_cover, geometry=meta.geometry,
        ))
    db.commit()
    cache_set(cache_key, json.dumps([s.model_dump(mode="json") for s in out]))
    return out
