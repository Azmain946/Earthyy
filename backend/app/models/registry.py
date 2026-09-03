from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModelRegistryEntry(Base):
    """Registry of algorithms/models so implementations can be swapped later.

    `metrics` stores *measured* validation metrics only; it stays empty until a
    real evaluation against ground truth has been run.
    """

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(255), unique=True)
    version: Mapped[str] = mapped_column(String(50))
    module: Mapped[str] = mapped_column(String(50), index=True)
    # index_threshold | segmentation | object_detection | change_detection | anomaly
    model_type: Mapped[str] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(500), default="")
    input_requirements: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_type: Mapped[str] = mapped_column(String(100), default="")
    # active | experimental | deprecated
    status: Mapped[str] = mapped_column(String(50), default="active")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    limitations: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
