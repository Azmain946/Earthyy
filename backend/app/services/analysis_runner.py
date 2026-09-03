"""Analysis job execution: dispatch to module analyzers and persist results.

Runs inside the worker process (RQ) or eagerly in-process when
EARTHYY_EAGER_JOBS=true.
"""
from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime, timezone

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping, shape
from sqlalchemy.orm import Session

from app.alerts.engine import evaluate_analysis
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.analysis import Analysis, Detection, Observation
from app.models.job import ProcessingJob
from app.models.zone import MonitoringZone
from app.services.modules import agriculture, brick_kiln, forest, river
from app.services.modules.base import AnalysisError

logger = logging.getLogger(__name__)
settings = get_settings()

ANALYZERS = {
    "river": river.analyze,
    "agriculture": agriculture.analyze,
    "forest": forest.analyze,
    "brick_kiln": brick_kiln.analyze,
}

STAGE_LABELS = {
    "queued": "Queued",
    "preparing_area": "Preparing area",
    "searching_imagery": "Finding satellite observations",
    "retrieving_imagery": "Preparing imagery",
    "processing": "Processing imagery",
    "analyzing": "Running analysis",
    "calculating_changes": "Calculating changes",
    "generating_layers": "Generating map layers",
    "completed": "Analysis complete",
    "failed": "Failed",
}


def run_analysis_job(job_id: str) -> None:
    """Entry point executed by the worker for a queued analysis job."""
    db = SessionLocal()
    try:
        _run(db, job_id)
    finally:
        db.close()


def _update_job(db: Session, job: ProcessingJob, stage: str, progress: float) -> None:
    job.stage = stage
    job.progress = progress
    job.status = "running" if stage not in ("completed", "failed") else stage
    db.commit()


def _run(db: Session, job_id: str) -> None:
    job = db.get(ProcessingJob, uuid.UUID(job_id))
    if job is None:
        logger.error("event=job_missing job=%s", job_id)
        return
    job.started_at = datetime.now(timezone.utc)
    _update_job(db, job, "preparing_area", 0.05)
    logger.info("event=job_started job=%s module=%s", job_id, job.module)

    try:
        params = dict(job.params or {})
        zone = db.get(MonitoringZone, job.zone_id) if job.zone_id else None
        if zone is not None:
            aoi_geojson = mapping(to_shape(zone.geometry))
        else:
            aoi_geojson = params["geometry"]

        analyzer = ANALYZERS.get(job.module)
        if analyzer is None:
            raise AnalysisError(f"Unknown module '{job.module}'")

        def progress(stage: str, frac: float) -> None:
            _update_job(db, job, stage, frac)

        result = analyzer(aoi_geojson, params, progress)

        analysis = Analysis(
            zone_id=zone.id if zone else None,
            module=job.module,
            status="completed",
            baseline_at=result["baseline_at"],
            observed_at=result["observed_at"],
            provenance=result["provenance"],
            measurements=result["measurements"],
            layers=result["layers"],
            confidence_score=result["confidence_score"],
            confidence_level=result["confidence_level"],
            method=result["method"],
            processing_version=settings.processing_version,
            limitations=result.get("limitations", ""),
        )
        db.add(analysis)
        db.flush()

        for det in result.get("detections", []):
            geom = shape(det["geometry"])
            db.add(Detection(
                analysis_id=analysis.id,
                zone_id=zone.id if zone else None,
                module=job.module,
                detection_type=det["detection_type"],
                geometry=from_shape(geom, srid=4326),
                area_m2=det.get("area_m2"),
                confidence=det.get("confidence"),
                status=det.get("status", "detected"),
                observed_at=det.get("observed_at"),
                first_detected_at=det.get("observed_at"),
                properties=det.get("properties", {}),
            ))

        if zone is not None:
            for obs in result.get("observations", []):
                exists = (
                    db.query(Observation)
                    .filter_by(zone_id=zone.id, module=job.module, observed_at=obs["observed_at"])
                    .first()
                )
                if not exists:
                    db.add(Observation(
                        zone_id=zone.id,
                        module=job.module,
                        observed_at=obs["observed_at"],
                        measurements=obs.get("measurements", {}),
                        preview_path=obs.get("preview_path"),
                    ))
            zone.latest_observation = result["observed_at"]

        evaluate_analysis(db, zone, analysis)

        job.result_analysis_id = analysis.id
        job.finished_at = datetime.now(timezone.utc)
        _update_job(db, job, "completed", 1.0)
        logger.info("event=job_completed job=%s analysis=%s", job_id, analysis.id)

    except AnalysisError as exc:
        db.rollback()
        job = db.get(ProcessingJob, uuid.UUID(job_id))
        job.error = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        _update_job(db, job, "failed", job.progress)
        logger.warning("event=job_failed job=%s error=%s", job_id, exc)
    except Exception as exc:
        db.rollback()
        job = db.get(ProcessingJob, uuid.UUID(job_id))
        job.error = f"Internal processing error: {exc}"
        job.finished_at = datetime.now(timezone.utc)
        _update_job(db, job, "failed", job.progress)
        logger.error("event=job_crashed job=%s error=%s trace=%s", job_id, exc, traceback.format_exc())
