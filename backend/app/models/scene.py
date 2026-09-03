from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SatelliteScene(Base):
    """Cached metadata for a satellite scene discovered via a STAC catalogue.

    Asset hrefs are stored so imagery can be windowed-read later without
    re-querying the provider. Only metadata is cached here — pixels are read
    on demand for the AOI only.
    """

    __tablename__ = "satellite_scenes"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_scene_provider_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    collection: Mapped[str] = mapped_column(String(100), index=True)
    # e.g. sentinel-2-l2a, landsat-c2-l2, sentinel-1-grd
    sensor: Mapped[str] = mapped_column(String(100))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True))
    assets: Mapped[dict] = mapped_column(JSONB, default=dict)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
