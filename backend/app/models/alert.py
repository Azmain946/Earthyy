from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alert(Base):
    """Rule-generated alert. Alerts are only created from real detections."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring_zones.id"), nullable=True, index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id"), nullable=True)
    detection_id: Mapped[int | None] = mapped_column(ForeignKey("detections.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50), index=True)
    # info | warning | critical
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(2000), default="")
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)
    measurement: Mapped[dict] = mapped_column(JSONB, default=dict)
    threshold: Mapped[dict] = mapped_column(JSONB, default=dict)
    # unread | acknowledged | resolved
    status: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
