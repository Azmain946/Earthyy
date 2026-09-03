"""Alert engine rule tests using an in-memory-ish DB session."""
from datetime import datetime, timezone

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, box

from app.alerts.engine import evaluate_analysis
from app.core.database import SessionLocal
from app.models.analysis import Analysis
from app.models.zone import MonitoringZone


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _zone(db, zone_type: str, thresholds: dict) -> MonitoringZone:
    z = MonitoringZone(
        name=f"alert-test-{zone_type}",
        zone_type=zone_type,
        geometry=from_shape(MultiPolygon([box(89.7, 23.7, 89.75, 23.75)]), srid=4326),
        thresholds=thresholds,
    )
    db.add(z)
    db.flush()
    return z


def _analysis(db, zone, module: str, measurements: dict) -> Analysis:
    a = Analysis(
        zone_id=zone.id, module=module, measurements=measurements,
        baseline_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(a)
    db.flush()
    return a


def test_forest_loss_triggers_alert(db):
    zone = _zone(db, "forest", {"forest_loss_ha": 1.0})
    analysis = _analysis(db, zone, "forest", {"forest_loss_ha": 4.8})
    alerts = evaluate_analysis(db, zone, analysis)
    assert len(alerts) == 1
    assert alerts[0].alert_type == "forest_loss"
    assert alerts[0].severity == "critical"  # 4.8 >= 3x threshold
    assert "potential" in alerts[0].title.lower() or "forest" in alerts[0].title.lower()


def test_forest_below_threshold_no_alert(db):
    zone = _zone(db, "forest", {"forest_loss_ha": 10.0})
    analysis = _analysis(db, zone, "forest", {"forest_loss_ha": 2.0})
    assert evaluate_analysis(db, zone, analysis) == []


def test_river_erosion_alert(db):
    zone = _zone(db, "river", {"erosion_km2": 0.05})
    analysis = _analysis(db, zone, "river", {"erosion_km2": 0.08})
    alerts = evaluate_analysis(db, zone, analysis)
    assert any(a.alert_type == "river_erosion" for a in alerts)
    # careful language: no legal claims
    for a in alerts:
        assert "illegal" not in a.message.lower()
        assert "proof" not in a.message.lower()


def test_agriculture_ndvi_drop_alert(db):
    zone = _zone(db, "agriculture", {"ndvi_drop_pct": 15.0})
    analysis = _analysis(db, zone, "agriculture", {"ndvi_change_pct": -25.0})
    alerts = evaluate_analysis(db, zone, analysis)
    assert any(a.alert_type == "vegetation_stress" for a in alerts)


def test_new_kiln_candidate_alert(db):
    zone = _zone(db, "brick_kiln", {"new_candidates": 1})
    analysis = _analysis(db, zone, "brick_kiln", {"new_candidate_count": 3})
    alerts = evaluate_analysis(db, zone, analysis)
    assert any(a.alert_type == "new_kiln_candidate" for a in alerts)
    assert all("verification" in a.message.lower() for a in alerts)
