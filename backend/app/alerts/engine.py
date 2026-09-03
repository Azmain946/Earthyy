"""Rule-based alert engine.

Alerts are generated only from real analysis measurements crossing
zone-configured (or default) thresholds. Language is scientifically careful:
"potential", "detected change" — never legal claims.
"""
from __future__ import annotations

import logging

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.analysis import Analysis
from app.models.zone import MonitoringZone

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "river": {"erosion_km2": 0.05, "movement_m_per_year": 25.0},
    "agriculture": {"ndvi_drop_pct": 15.0, "stress_area_ha": 5.0},
    "forest": {"forest_loss_ha": 1.0},
    "brick_kiln": {"new_candidates": 1},
}


def _severity(value: float, threshold: float) -> str:
    if threshold <= 0:
        return "warning"
    ratio = value / threshold
    if ratio >= 3:
        return "critical"
    if ratio >= 1:
        return "warning"
    return "info"


def _mk_alert(db: Session, zone: MonitoringZone, analysis: Analysis, alert_type: str,
              severity: str, title: str, message: str, measurement: dict, threshold: dict) -> Alert:
    location = None
    if zone is not None and zone.geometry is not None:
        from geoalchemy2.shape import to_shape

        centroid = to_shape(zone.geometry).centroid
        location = from_shape(centroid, srid=4326)
    alert = Alert(
        zone_id=zone.id if zone else None,
        analysis_id=analysis.id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        location=location,
        measurement=measurement,
        threshold=threshold,
        status="unread",
    )
    db.add(alert)
    logger.info("event=alert_created type=%s severity=%s zone=%s", alert_type, severity, zone.id if zone else None)
    return alert


def evaluate_analysis(db: Session, zone: MonitoringZone | None, analysis: Analysis) -> list[Alert]:
    """Apply module alert rules to a completed analysis."""
    m = analysis.measurements or {}
    module = analysis.module
    thresholds = dict(DEFAULT_THRESHOLDS.get(module, {}))
    if zone and zone.thresholds:
        thresholds.update(zone.thresholds)
    alerts: list[Alert] = []
    zone_name = zone.name if zone else "ad-hoc area"

    if module == "river":
        erosion = m.get("erosion_km2") or 0.0
        t = thresholds.get("erosion_km2", 0.05)
        if erosion > t:
            alerts.append(_mk_alert(
                db, zone, analysis, "river_erosion", _severity(erosion, t),
                "Riverbank change detected",
                f"Land-to-water transition of {erosion:.2f} km² detected in {zone_name} "
                f"between {analysis.baseline_at.date() if analysis.baseline_at else '—'} and "
                f"{analysis.observed_at.date() if analysis.observed_at else '—'}. "
                "Potential riverbank erosion / land-use change within historical river boundary.",
                {"erosion_km2": erosion}, {"erosion_km2": t},
            ))
        rate = m.get("movement_rate_m_per_year")
        t2 = thresholds.get("movement_m_per_year", 25.0)
        if rate is not None and rate > t2:
            alerts.append(_mk_alert(
                db, zone, analysis, "river_movement", _severity(rate, t2),
                "Rapid bank movement detected",
                f"Estimated mean bank movement rate {rate:.0f} m/yr exceeds the "
                f"{t2:.0f} m/yr threshold in {zone_name}.",
                {"movement_rate_m_per_year": rate}, {"movement_m_per_year": t2},
            ))

    elif module == "agriculture":
        drop = m.get("ndvi_change_pct")
        t = thresholds.get("ndvi_drop_pct", 15.0)
        if drop is not None and drop <= -t:
            alerts.append(_mk_alert(
                db, zone, analysis, "vegetation_stress", _severity(abs(drop), t),
                "Vegetation stress detected",
                f"Mean NDVI dropped {abs(drop):.1f}% vs baseline in {zone_name}. "
                "Spectral indicator only — field verification recommended.",
                {"ndvi_change_pct": drop}, {"ndvi_drop_pct": t},
            ))
        stress_ha = m.get("stress_area_ha") or 0.0
        t2 = thresholds.get("stress_area_ha", 5.0)
        if stress_ha > t2:
            alerts.append(_mk_alert(
                db, zone, analysis, "stress_area", _severity(stress_ha, t2),
                "Vegetation stress area above threshold",
                f"{stress_ha:.1f} ha of vegetation shows significant NDVI decline in {zone_name}.",
                {"stress_area_ha": stress_ha}, {"stress_area_ha": t2},
            ))

    elif module == "forest":
        loss = m.get("forest_loss_ha") or 0.0
        t = thresholds.get("forest_loss_ha", 1.0)
        if loss > t:
            alerts.append(_mk_alert(
                db, zone, analysis, "forest_loss", _severity(loss, t),
                "Potential forest-cover loss detected",
                f"Canopy loss of {loss:.1f} ha detected in {zone_name} between "
                f"{analysis.baseline_at.date() if analysis.baseline_at else '—'} and "
                f"{analysis.observed_at.date() if analysis.observed_at else '—'}. "
                "Forest-cover change detected — no claim of cause is made.",
                {"forest_loss_ha": loss}, {"forest_loss_ha": t},
            ))

    elif module == "brick_kiln":
        new = m.get("new_candidate_count") or 0
        t = thresholds.get("new_candidates", 1)
        if new >= t:
            alerts.append(_mk_alert(
                db, zone, analysis, "new_kiln_candidate", "warning",
                "New brick kiln candidate site(s)",
                f"{new} candidate kiln site(s) not present in the baseline observation "
                f"detected in {zone_name}. Candidates require verification.",
                {"new_candidate_count": new}, {"new_candidates": t},
            ))

    return alerts
