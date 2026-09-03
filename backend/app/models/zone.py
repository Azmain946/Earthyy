from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonitoringZone(Base):
    """A user-defined geographic area under continuous observation.

    The core Earthyy primitive: every module analysis, historical observation,
    detection and alert hangs off a monitoring zone.
    """

    __tablename__ = "monitoring_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # river | agriculture | forest | brick_kiln | general
    zone_type: Mapped[str] = mapped_column(String(50), index=True)
    geometry = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))
    area_km2: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    latest_observation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # active | paused | archived
    status: Mapped[str] = mapped_column(String(50), default="active")
    # e.g. {"forest_loss_ha": 1.0, "river_movement_m": 25, "ndvi_drop_pct": 15}
    thresholds: Mapped[dict] = mapped_column(JSONB, default=dict)
    alert_configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[str] = mapped_column(String(2000), default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
