"""Report generation from real analysis records (PDF / CSV / GeoJSON)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from geoalchemy2.shape import to_shape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.models.analysis import Analysis, Detection
from app.models.zone import MonitoringZone
from app.services.storage import get_storage

MODULE_TITLES = {
    "river": "River Hydrology & Morphodynamics",
    "agriculture": "Agriculture & Crop Intelligence",
    "forest": "Forest Canopy Change Detection",
    "brick_kiln": "Brick Kiln Intelligence",
}


def _fmt(v) -> str:
    if v is None:
        return "unavailable"
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".")
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)


def generate_pdf(db: Session, analysis: Analysis, zone: MonitoringZone | None) -> str:
    """Earthyy-branded PDF report with measurements, provenance and limitations."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("EH1", parent=styles["Heading1"], textColor=colors.HexColor("#00507d"))
    h2 = ParagraphStyle("EH2", parent=styles["Heading2"], textColor=colors.HexColor("#141d23"), spaceBefore=10)
    body = ParagraphStyle("EBody", parent=styles["BodyText"], fontSize=9, leading=13)
    mono = ParagraphStyle("EMono", parent=styles["BodyText"], fontName="Courier", fontSize=8, leading=11)

    story = [
        Paragraph("EARTHYY — Observation Intelligence", h1),
        Paragraph(MODULE_TITLES.get(analysis.module, analysis.module), h2),
        Paragraph(
            f"Report generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
            f"Processing version {analysis.processing_version} · Analysis #{analysis.id}",
            mono,
        ),
        Spacer(1, 6),
    ]

    if zone is not None:
        centroid = to_shape(zone.geometry).centroid
        story += [
            Paragraph("Monitored Area", h2),
            Paragraph(
                f"{zone.name} ({zone.zone_type}) — {zone.area_km2:.2f} km² · "
                f"centroid {centroid.y:.4f}°N, {centroid.x:.4f}°E", body,
            ),
        ]

    story.append(Paragraph("Observation Window", h2))
    story.append(Paragraph(
        f"Baseline: {analysis.baseline_at.date() if analysis.baseline_at else '—'} · "
        f"Current: {analysis.observed_at.date() if analysis.observed_at else '—'}", body))

    # Preview imagery
    storage = get_storage()
    for layer in analysis.layers or []:
        if layer.get("kind") == "raster" and layer.get("path") and "rgb" in layer.get("key", ""):
            p = storage.path(layer["path"])
            if p:
                story.append(Spacer(1, 4))
                story.append(Paragraph(layer.get("title", ""), body))
                story.append(Image(str(p), width=150 * mm, height=90 * mm, kind="proportional"))

    story.append(Paragraph("Measurements", h2))
    rows = [["Measurement", "Value"]]
    for k, v in (analysis.measurements or {}).items():
        if isinstance(v, (dict, list)):
            continue
        rows.append([k.replace("_", " "), _fmt(v)])
    table = Table(rows, colWidths=[95 * mm, 75 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eff8")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c0c7d1")),
        ("FONTNAME", (1, 1), (1, -1), "Courier"),
    ]))
    story.append(table)

    n_det = db.query(Detection).filter(Detection.analysis_id == analysis.id).count()
    story.append(Paragraph("Detections", h2))
    story.append(Paragraph(f"{n_det} detection feature(s) stored for this analysis.", body))

    story.append(Paragraph("Confidence", h2))
    conf = f"{analysis.confidence_score:.2f} ({analysis.confidence_level})" if analysis.confidence_score is not None else f"unavailable ({analysis.confidence_level})"
    story.append(Paragraph(
        f"Confidence: {conf}. Derived from valid-data fraction and scene cloud cover — "
        "a data-quality measure, not a validated model accuracy.", body))

    story.append(Paragraph("Methodology & Source Data", h2))
    story.append(Paragraph(f"Method: {analysis.method}", body))
    for role, prov in (analysis.provenance or {}).items():
        story.append(Paragraph(
            f"{role}: {prov.get('provider')} · {prov.get('scene_id')} · "
            f"{prov.get('collection')} · acquired {prov.get('acquired_at', '')[:10]} · "
            f"cloud {prov.get('cloud_cover')}%", mono))

    if analysis.limitations:
        story.append(Paragraph("Limitations", h2))
        story.append(Paragraph(analysis.limitations, body))

    doc.build(story)
    key = f"reports/analysis_{analysis.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    get_storage().put(key, buf.getvalue())
    return key


def generate_csv(analysis: Analysis) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["measurement", "value"])
    for k, v in (analysis.measurements or {}).items():
        writer.writerow([k, _fmt(v)])
    writer.writerow([])
    writer.writerow(["provenance_role", "provider", "scene_id", "acquired_at", "cloud_cover"])
    for role, prov in (analysis.provenance or {}).items():
        writer.writerow([role, prov.get("provider"), prov.get("scene_id"), prov.get("acquired_at"), prov.get("cloud_cover")])
    key = f"reports/analysis_{analysis.id}.csv"
    get_storage().put(key, buf.getvalue().encode())
    return key


def generate_geojson(db: Session, analysis: Analysis) -> str:
    dets = db.query(Detection).filter(Detection.analysis_id == analysis.id).all()
    features = [
        {
            "type": "Feature",
            "geometry": mapping(to_shape(d.geometry)),
            "properties": {
                "detection_type": d.detection_type,
                "area_m2": d.area_m2,
                "confidence": d.confidence,
                "status": d.status,
                "observed_at": d.observed_at.isoformat() if d.observed_at else None,
                **(d.properties or {}),
            },
        }
        for d in dets
    ]
    fc = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "analysis_id": analysis.id,
            "module": analysis.module,
            "method": analysis.method,
            "processing_version": analysis.processing_version,
        },
    }
    key = f"reports/analysis_{analysis.id}.geojson"
    get_storage().put(key, json.dumps(fc).encode())
    return key
