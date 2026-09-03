from fastapi import APIRouter, Depends
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.analysis import Detection
from app.models.user import User
from app.schemas.common import DetectionOut

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("", response_model=list[DetectionOut])
def recent_changes(module: str | None = None, detection_type: str | None = None,
                   zone_id: int | None = None, limit: int = 100,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Recent detected physical changes (real detection records)."""
    q = db.query(Detection)
    if module:
        q = q.filter(Detection.module == module)
    if detection_type:
        q = q.filter(Detection.detection_type == detection_type)
    if zone_id is not None:
        q = q.filter(Detection.zone_id == zone_id)
    dets = q.order_by(Detection.created_at.desc()).limit(min(limit, 500)).all()
    return [
        DetectionOut(
            id=d.id, analysis_id=d.analysis_id, zone_id=d.zone_id, module=d.module,
            detection_type=d.detection_type, geometry=mapping(to_shape(d.geometry)),
            area_m2=d.area_m2, confidence=d.confidence, status=d.status,
            observed_at=d.observed_at, properties=d.properties or {},
        )
        for d in dets
    ]
