from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.analysis import Analysis
from app.models.report import Report
from app.models.user import User
from app.models.zone import MonitoringZone
from app.reports.generator import generate_csv, generate_geojson, generate_pdf

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("")
def create_report(analysis_id: int, format: str = "pdf",
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if format not in ("pdf", "csv", "geojson"):
        raise HTTPException(422, "format must be pdf, csv or geojson")
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found")
    zone = db.get(MonitoringZone, analysis.zone_id) if analysis.zone_id else None

    if format == "pdf":
        key = generate_pdf(db, analysis, zone)
    elif format == "csv":
        key = generate_csv(analysis)
    else:
        key = generate_geojson(db, analysis)

    report = Report(
        zone_id=analysis.zone_id, analysis_id=analysis.id, format=format, path=key,
        title=f"{analysis.module} analysis #{analysis.id}",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "format": format, "path": key, "download_url": f"/api/files/{key}"}


@router.get("")
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(100).all()
    return [
        {"id": r.id, "zone_id": r.zone_id, "analysis_id": r.analysis_id, "format": r.format,
         "title": r.title, "download_url": f"/api/files/{r.path}", "created_at": r.created_at}
        for r in reports
    ]
