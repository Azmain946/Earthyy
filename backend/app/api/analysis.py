from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.zones import validate_aoi
from app.core.database import get_db
from app.models.analysis import Analysis, Detection
from app.models.job import ProcessingJob
from app.models.user import User
from app.models.zone import MonitoringZone
from app.schemas.common import AnalysisOut, AnalysisRequest, DetectionOut, JobOut
from app.services.analysis_runner import STAGE_LABELS
from app.workers.queue import enqueue_analysis

router = APIRouter(tags=["analysis"])


def job_out(job: ProcessingJob) -> JobOut:
    return JobOut(
        id=job.id, zone_id=job.zone_id, module=job.module, job_type=job.job_type,
        status=job.status, stage=job.stage, stage_label=STAGE_LABELS.get(job.stage, job.stage),
        progress=job.progress, error=job.error, result_analysis_id=job.result_analysis_id,
        created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at,
    )


@router.post("/analysis", response_model=JobOut, status_code=202)
def request_analysis(body: AnalysisRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Create an analysis job. Heavy processing happens in the worker."""
    if body.zone_id is None and body.geometry is None:
        raise HTTPException(422, "Provide either zone_id or geometry")
    if body.baseline_date >= body.current_date:
        raise HTTPException(422, "baseline_date must be before current_date")

    params: dict = {
        "baseline_date": body.baseline_date.isoformat(),
        "current_date": body.current_date.isoformat(),
    }
    if body.provider:
        params["provider"] = body.provider
    if body.max_cloud_cover is not None:
        params["max_cloud_cover"] = body.max_cloud_cover

    zone_id = None
    if body.zone_id is not None:
        zone = db.get(MonitoringZone, body.zone_id)
        if zone is None:
            raise HTTPException(404, "Monitoring zone not found")
        zone_id = zone.id
    else:
        geom_dict = body.geometry.model_dump()
        validate_aoi(geom_dict)
        params["geometry"] = geom_dict

    job = ProcessingJob(zone_id=zone_id, module=body.module, job_type="analysis", params=params)
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_analysis(str(job.id))
    return job_out(job)


@router.get("/analysis/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(404, "Analysis not found")
    return a


@router.get("/analysis", response_model=list[AnalysisOut])
def list_analyses(zone_id: int | None = None, module: str | None = None, limit: int = 20,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Analysis)
    if zone_id is not None:
        q = q.filter(Analysis.zone_id == zone_id)
    if module:
        q = q.filter(Analysis.module == module)
    return q.order_by(Analysis.created_at.desc()).limit(min(limit, 100)).all()


@router.get("/analysis/{analysis_id}/detections", response_model=list[DetectionOut])
def analysis_detections(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dets = db.query(Detection).filter(Detection.analysis_id == analysis_id).all()
    return [
        DetectionOut(
            id=d.id, analysis_id=d.analysis_id, zone_id=d.zone_id, module=d.module,
            detection_type=d.detection_type, geometry=mapping(to_shape(d.geometry)),
            area_m2=d.area_m2, confidence=d.confidence, status=d.status,
            observed_at=d.observed_at, properties=d.properties or {},
        )
        for d in dets
    ]
