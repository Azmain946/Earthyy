from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.alert import Alert
from app.models.analysis import Analysis, Detection
from app.models.job import ProcessingJob
from app.models.scene import SatelliteScene
from app.models.user import User
from app.models.zone import MonitoringZone

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Live platform summary aggregated from the database (no hard-coded values)."""
    zones_total = db.query(func.count(MonitoringZone.id)).filter(MonitoringZone.status == "active").scalar()
    zones_by_type = dict(
        db.query(MonitoringZone.zone_type, func.count(MonitoringZone.id))
        .filter(MonitoringZone.status == "active")
        .group_by(MonitoringZone.zone_type)
        .all()
    )
    monitored_km2 = db.query(func.coalesce(func.sum(MonitoringZone.area_km2), 0.0)).filter(
        MonitoringZone.status == "active"
    ).scalar()

    detections_by_type = dict(
        db.query(Detection.detection_type, func.count(Detection.id)).group_by(Detection.detection_type).all()
    )
    kiln_candidates = (
        db.query(func.count(Detection.id))
        .filter(Detection.detection_type == "kiln_candidate")
        .scalar()
    )

    unread_alerts = db.query(func.count(Alert.id)).filter(Alert.status == "unread").scalar()
    analyses_total = db.query(func.count(Analysis.id)).scalar()
    scenes_cached = db.query(func.count(SatelliteScene.id)).scalar()
    last_scene = db.query(func.max(SatelliteScene.acquired_at)).scalar()
    running_jobs = db.query(func.count(ProcessingJob.id)).filter(ProcessingJob.status == "running").scalar()

    # Latest measurements per module for the summary cards.
    module_latest: dict = {}
    for module in ("river", "agriculture", "forest", "brick_kiln"):
        a = (
            db.query(Analysis)
            .filter(Analysis.module == module, Analysis.status == "completed")
            .order_by(Analysis.created_at.desc())
            .first()
        )
        if a:
            module_latest[module] = {
                "analysis_id": a.id,
                "zone_id": a.zone_id,
                "observed_at": a.observed_at,
                "baseline_at": a.baseline_at,
                "measurements": a.measurements,
                "confidence_score": a.confidence_score,
                "confidence_level": a.confidence_level,
                "provenance": a.provenance,
            }

    return {
        "zones": {"total": zones_total, "by_type": zones_by_type, "monitored_km2": round(monitored_km2 or 0, 1)},
        "detections": {"by_type": detections_by_type, "kiln_candidates": kiln_candidates},
        "alerts": {"unread": unread_alerts},
        "analyses": {"total": analyses_total},
        "jobs": {"running": running_jobs},
        "scenes": {"cached": scenes_cached, "latest_acquisition": last_scene},
        "modules": module_latest,
    }
