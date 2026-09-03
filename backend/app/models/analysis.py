from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Analysis(Base):
    """A completed module analysis over a zone for a given time window.

    Provenance fields make each result traceable: which scenes, which method,
    which processing version, and when it ran.
    """

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("monitoring_zones.id"), index=True)
    module: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    baseline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # {"baseline": {...scene provenance...}, "current": {...}}
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Module-specific measurements (areas, indices, rates, ...)
    measurements: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Map layers produced: [{"key","kind":"geojson|raster","path","bounds","style"}]
    layers: Mapped[list] = mapped_column(JSONB, default=list)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # high | medium | low | unavailable
    confidence_level: Mapped[str] = mapped_column(String(20), default="unavailable")
    method: Mapped[str] = mapped_column(String(255), default="")
    processing_version: Mapped[str] = mapped_column(String(50), default="")
    limitations: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Observation(Base):
    """Historical Earth record: one derived observation of a zone at a date."""

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("monitoring_zones.id"), index=True)
    module: Mapped[str] = mapped_column(String(50), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("satellite_scenes.id"), nullable=True)
    measurements: Mapped[dict] = mapped_column(JSONB, default=dict)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Detection(Base):
    """A discrete detected feature/change with its own geometry."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analyses.id"), nullable=True, index=True)
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring_zones.id"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(50), index=True)
    # erosion | accretion | forest_loss | forest_gain | vegetation_stress | kiln_candidate | ...
    detection_type: Mapped[str] = mapped_column(String(50), index=True)
    geometry = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True))
    area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # detected | candidate | historical | confirmed
    status: Mapped[str] = mapped_column(String(50), default="detected")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
