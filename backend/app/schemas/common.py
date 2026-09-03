"""Shared Pydantic schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GeoJSONGeometry(BaseModel):
    type: Literal[
        "Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"
    ]
    coordinates: Any

    @field_validator("coordinates")
    @classmethod
    def not_empty(cls, v: Any) -> Any:
        if v in (None, []):
            raise ValueError("coordinates must not be empty")
        return v


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


# ---------- Monitoring zones ----------
class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    zone_type: Literal["river", "agriculture", "forest", "brick_kiln", "general"]
    geometry: GeoJSONGeometry
    baseline_date: date | None = None
    thresholds: dict = Field(default_factory=dict)
    alert_configuration: dict = Field(default_factory=dict)
    description: str = ""


class ZoneUpdate(BaseModel):
    name: str | None = None
    status: Literal["active", "paused", "archived"] | None = None
    thresholds: dict | None = None
    alert_configuration: dict | None = None
    description: str | None = None


class ZoneOut(BaseModel):
    id: int
    name: str
    zone_type: str
    geometry: dict
    area_km2: float
    baseline_date: date | None
    latest_observation: datetime | None
    status: str
    thresholds: dict
    alert_configuration: dict
    description: str
    created_at: datetime


# ---------- Analysis / jobs ----------
class AnalysisRequest(BaseModel):
    module: Literal["river", "agriculture", "forest", "brick_kiln"]
    zone_id: int | None = None
    geometry: GeoJSONGeometry | None = None
    baseline_date: date
    current_date: date
    provider: str | None = None
    max_cloud_cover: float | None = Field(default=None, ge=0, le=100)


class JobOut(BaseModel):
    id: UUID
    zone_id: int | None
    module: str
    job_type: str
    status: str
    stage: str
    stage_label: str = ""
    progress: float
    error: str | None
    result_analysis_id: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AnalysisOut(BaseModel):
    id: int
    zone_id: int | None
    module: str
    status: str
    baseline_at: datetime | None
    observed_at: datetime | None
    provenance: dict
    measurements: dict
    layers: list
    confidence_score: float | None
    confidence_level: str
    method: str
    processing_version: str
    limitations: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectionOut(BaseModel):
    id: int
    analysis_id: int | None
    zone_id: int | None
    module: str
    detection_type: str
    geometry: dict
    area_m2: float | None
    confidence: float | None
    status: str
    observed_at: datetime | None
    properties: dict


class ObservationOut(BaseModel):
    id: int
    zone_id: int
    module: str
    observed_at: datetime
    measurements: dict
    preview_path: str | None


class AlertOut(BaseModel):
    id: int
    zone_id: int | None
    analysis_id: int | None
    alert_type: str
    severity: str
    title: str
    message: str
    location: dict | None
    measurement: dict
    threshold: dict
    status: str
    created_at: datetime


class SceneOut(BaseModel):
    id: int
    provider: str
    external_id: str
    collection: str
    sensor: str
    acquired_at: datetime
    cloud_cover: float | None
    geometry: dict | None = None
