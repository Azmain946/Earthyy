from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping, shape
from shapely.validation import explain_validity
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.geospatial.measure import geodesic_area_km2
from app.models.analysis import Observation
from app.models.user import User
from app.models.zone import MonitoringZone
from app.schemas.common import ObservationOut, ZoneCreate, ZoneOut, ZoneUpdate

router = APIRouter(prefix="/monitoring-zones", tags=["monitoring-zones"])
settings = get_settings()


def _zone_out(z: MonitoringZone) -> ZoneOut:
    return ZoneOut(
        id=z.id,
        name=z.name,
        zone_type=z.zone_type,
        geometry=mapping(to_shape(z.geometry)),
        area_km2=z.area_km2,
        baseline_date=z.baseline_date,
        latest_observation=z.latest_observation,
        status=z.status,
        thresholds=z.thresholds or {},
        alert_configuration=z.alert_configuration or {},
        description=z.description or "",
        created_at=z.created_at,
    )


def validate_aoi(geometry: dict) -> "shape":
    geom = shape(geometry)
    if geom.is_empty:
        raise HTTPException(422, "Geometry is empty")
    if not geom.is_valid:
        raise HTTPException(422, f"Invalid geometry: {explain_validity(geom)}")
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise HTTPException(422, "Zone geometry must be a Polygon or MultiPolygon")
    area = geodesic_area_km2(geometry)
    if area > settings.max_aoi_km2:
        raise HTTPException(422, f"AOI too large: {area:.0f} km² (max {settings.max_aoi_km2:.0f} km²)")
    if area < 0.001:
        raise HTTPException(422, "AOI too small (< 0.001 km²)")
    return geom


@router.get("", response_model=list[ZoneOut])
def list_zones(zone_type: str | None = None, status: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(MonitoringZone)
    if zone_type:
        q = q.filter(MonitoringZone.zone_type == zone_type)
    if status:
        q = q.filter(MonitoringZone.status == status)
    return [_zone_out(z) for z in q.order_by(MonitoringZone.created_at.desc()).all()]


@router.post("", response_model=ZoneOut, status_code=201)
def create_zone(body: ZoneCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    geom = validate_aoi(body.geometry.model_dump())
    if geom.geom_type == "Polygon":
        from shapely.geometry import MultiPolygon

        geom = MultiPolygon([geom])
    zone = MonitoringZone(
        name=body.name,
        zone_type=body.zone_type,
        geometry=from_shape(geom, srid=4326),
        area_km2=round(geodesic_area_km2(mapping(geom)), 3),
        baseline_date=body.baseline_date,
        thresholds=body.thresholds,
        alert_configuration=body.alert_configuration,
        description=body.description,
        user_id=user.id,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _zone_out(zone)


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    zone = db.get(MonitoringZone, zone_id)
    if zone is None:
        raise HTTPException(404, "Monitoring zone not found")
    return _zone_out(zone)


@router.patch("/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: int, body: ZoneUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    zone = db.get(MonitoringZone, zone_id)
    if zone is None:
        raise HTTPException(404, "Monitoring zone not found")
    for field in ("name", "status", "thresholds", "alert_configuration", "description"):
        value = getattr(body, field)
        if value is not None:
            setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return _zone_out(zone)


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    zone = db.get(MonitoringZone, zone_id)
    if zone is None:
        raise HTTPException(404, "Monitoring zone not found")
    zone.status = "archived"
    db.commit()


@router.get("/{zone_id}/observations", response_model=list[ObservationOut])
def zone_observations(zone_id: int, module: str | None = None,
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Historical Earth record for a zone (Earth Time timeline)."""
    q = db.query(Observation).filter(Observation.zone_id == zone_id)
    if module:
        q = q.filter(Observation.module == module)
    obs = q.order_by(Observation.observed_at.asc()).all()
    return [
        ObservationOut(
            id=o.id, zone_id=o.zone_id, module=o.module, observed_at=o.observed_at,
            measurements=o.measurements or {}, preview_path=o.preview_path,
        )
        for o in obs
    ]
