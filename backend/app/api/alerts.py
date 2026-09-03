from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.common import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _alert_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id, zone_id=a.zone_id, analysis_id=a.analysis_id, alert_type=a.alert_type,
        severity=a.severity, title=a.title, message=a.message,
        location=mapping(to_shape(a.location)) if a.location is not None else None,
        measurement=a.measurement or {}, threshold=a.threshold or {},
        status=a.status, created_at=a.created_at,
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(status: str | None = None, zone_id: int | None = None, limit: int = 50,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    if zone_id is not None:
        q = q.filter(Alert.zone_id == zone_id)
    return [_alert_out(a) for a in q.order_by(Alert.created_at.desc()).limit(min(limit, 200)).all()]


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Alert not found")
    a.status = "acknowledged"
    db.commit()
    return _alert_out(a)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Alert not found")
    a.status = "resolved"
    db.commit()
    return _alert_out(a)
