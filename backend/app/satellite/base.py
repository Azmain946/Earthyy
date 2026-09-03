"""Satellite provider abstraction.

Every provider exposes STAC-style search over real Earth-observation
catalogues and returns normalized `SceneMeta` records. Pixel access happens
later via windowed COG reads of the asset hrefs (AOI-only, never full scenes).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SceneMeta:
    provider: str
    external_id: str
    collection: str
    sensor: str
    acquired_at: datetime
    cloud_cover: float | None
    geometry: dict  # GeoJSON geometry (footprint, EPSG:4326)
    assets: dict[str, str]  # normalized band/asset key -> href
    properties: dict[str, Any] = field(default_factory=dict)


class SatelliteProvider(ABC):
    """Abstract satellite catalogue provider."""

    name: str = "abstract"

    @abstractmethod
    def search(
        self,
        geometry: dict,
        start: datetime,
        end: datetime,
        collections: list[str] | None = None,
        max_cloud_cover: float | None = None,
        limit: int = 50,
    ) -> list[SceneMeta]:
        """Search the catalogue for scenes intersecting `geometry` in the window."""

    def sign_href(self, href: str) -> str:
        """Return an access-ready URL for an asset href (override if signing needed)."""
        return href


class ProviderError(RuntimeError):
    """Raised when a satellite provider request fails."""
