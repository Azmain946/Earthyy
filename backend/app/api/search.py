"""Geographic search: local monitoring zones + OpenStreetMap Nominatim geocoding.

Nominatim is a real public geocoder (usage policy: 1 req/s, attribution).
Results are cached to respect rate limits.
"""
import json
import logging

import requests
from fastapi import APIRouter, Depends, Query
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.zone import MonitoringZone
from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@router.get("")
def search(q: str = Query(..., min_length=2, max_length=200),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    results = []

    # 1. Local monitoring zones
    zones = (
        db.query(MonitoringZone)
        .filter(MonitoringZone.name.ilike(f"%{q}%"), MonitoringZone.status == "active")
        .limit(5)
        .all()
    )
    for z in zones:
        c = to_shape(z.geometry).centroid
        results.append({
            "kind": "monitoring_zone", "name": z.name, "zone_id": z.id,
            "zone_type": z.zone_type, "lat": c.y, "lon": c.x,
        })

    # 2. Nominatim geocoding (cached)
    cache_key = f"geocode:{q.lower()}"
    cached = cache_get(cache_key)
    if cached:
        results.extend(json.loads(cached))
        return {"query": q, "results": results}

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": q, "format": "jsonv2", "limit": 6, "countrycodes": ""},
            headers={"User-Agent": "Earthyy-Observation-Intelligence/1.0"},
            timeout=8,
        )
        resp.raise_for_status()
        geocoded = [
            {
                "kind": "place",
                "name": item.get("display_name", ""),
                "category": item.get("type", ""),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "bbox": [float(b) for b in item.get("boundingbox", [])] or None,
            }
            for item in resp.json()
        ]
        cache_set(cache_key, json.dumps(geocoded), ttl=86400)
        results.extend(geocoded)
    except Exception as exc:
        logger.warning("event=geocode_failed error=%s", exc)

    return {"query": q, "results": results}
