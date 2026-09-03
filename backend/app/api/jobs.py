import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.analysis import job_out
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.job import ProcessingJob
from app.models.user import User
from app.schemas.common import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(status: str | None = None, limit: int = 25,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(ProcessingJob)
    if status:
        q = q.filter(ProcessingJob.status == status)
    jobs = q.order_by(ProcessingJob.created_at.desc()).limit(min(limit, 100)).all()
    return [job_out(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job_out(job)
