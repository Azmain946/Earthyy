"""Concrete satellite catalogue providers.

- EarthSearchProvider: AWS Earth Search (Element 84) — public, no credentials.
  Sentinel-2 L2A COGs, Sentinel-1 GRD, Landsat Collection 2 L2.
- PlanetaryComputerProvider: Microsoft Planetary Computer — public STAC,
  asset hrefs require SAS signing via the planetary-computer SDK.
- CopernicusProvider: Copernicus Data Space STAC — catalogue search is public;
  asset download requires credentials (configured via env), so by default it
  is used for discovery/metadata only.
"""
from __future__ import annotations

import logging
from datetime import datetime

from pystac_client import Client

from app.core.config import get_settings
from app.satellite.base import ProviderError, SatelliteProvider, SceneMeta

logger = logging.getLogger(__name__)
settings = get_settings()

# Normalized band keys used by the processing layer for Sentinel-2.
S2_BAND_KEYS = {
    "blue": ["blue", "B02", "B02_10m"],
    "green": ["green", "B03", "B03_10m"],
    "red": ["red", "B04", "B04_10m"],
    "nir": ["nir", "B08", "B08_10m"],
    "swir16": ["swir16", "B11", "B11_20m"],
    "swir22": ["swir22", "B12", "B12_20m"],
    "rededge1": ["rededge1", "B05"],
    "scl": ["scl", "SCL", "SCL_20m"],
    "visual": ["visual", "TCI", "TCI_10m"],
}


def _normalize_assets(item_assets: dict) -> dict[str, str]:
    """Map provider-specific asset keys to Earthyy's normalized band keys."""
    normalized: dict[str, str] = {}
    for norm_key, candidates in S2_BAND_KEYS.items():
        for cand in candidates:
            if cand in item_assets:
                normalized[norm_key] = item_assets[cand].href
                break
    # Keep any remaining assets under their original keys for provenance.
    for key, asset in item_assets.items():
        if key not in normalized and asset.href and key not in ("thumbnail",):
            normalized.setdefault(key, asset.href)
    return normalized


class StacProvider(SatelliteProvider):
    """Shared pystac-client implementation."""

    stac_url: str = ""
    default_collections: list[str] = ["sentinel-2-l2a"]

    def __init__(self) -> None:
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = Client.open(self.stac_url)
        return self._client

    def search(
        self,
        geometry: dict,
        start: datetime,
        end: datetime,
        collections: list[str] | None = None,
        max_cloud_cover: float | None = None,
        limit: int = 50,
    ) -> list[SceneMeta]:
        collections = collections or self.default_collections
        query = {}
        if max_cloud_cover is not None:
            query["eo:cloud_cover"] = {"lt": max_cloud_cover}
        try:
            search = self.client.search(
                collections=collections,
                intersects=geometry,
                datetime=f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}",
                query=query or None,
                max_items=limit,
            )
            items = list(search.items())
        except Exception as exc:  # network/catalogue failure -> structured error
            logger.error("provider=%s event=search_failed error=%s", self.name, exc)
            raise ProviderError(f"{self.name} catalogue search failed: {exc}") from exc

        scenes = []
        for item in items:
            props = item.properties or {}
            acquired = item.datetime
            if acquired is None:
                continue
            scenes.append(
                SceneMeta(
                    provider=self.name,
                    external_id=item.id,
                    collection=item.collection_id or collections[0],
                    sensor=props.get("platform", item.collection_id or ""),
                    acquired_at=acquired,
                    cloud_cover=props.get("eo:cloud_cover"),
                    geometry=item.geometry,
                    assets=_normalize_assets(item.assets),
                    properties={
                        k: v
                        for k, v in props.items()
                        if isinstance(v, (str, int, float, bool))
                    },
                )
            )
        logger.info(
            "provider=%s event=search collections=%s found=%d", self.name, collections, len(scenes)
        )
        return scenes


class EarthSearchProvider(StacProvider):
    name = "earth_search"
    stac_url = settings.earth_search_url
    default_collections = ["sentinel-2-l2a"]


class PlanetaryComputerProvider(StacProvider):
    name = "planetary_computer"
    stac_url = settings.planetary_computer_url
    default_collections = ["sentinel-2-l2a"]

    def sign_href(self, href: str) -> str:
        import planetary_computer

        return planetary_computer.sign(href)


class CopernicusProvider(StacProvider):
    name = "copernicus"
    stac_url = settings.copernicus_stac_url
    default_collections = ["SENTINEL-2"]

    def sign_href(self, href: str) -> str:
        # Copernicus Data Space asset downloads require OAuth credentials.
        # Without credentials this provider is metadata/discovery only.
        if not settings.copernicus_client_id:
            raise ProviderError(
                "Copernicus asset access requires EARTHYY_COPERNICUS_CLIENT_ID / "
                "EARTHYY_COPERNICUS_CLIENT_SECRET. Use earth_search or "
                "planetary_computer for pixel access, or configure credentials."
            )
        return href


_PROVIDERS: dict[str, SatelliteProvider] = {}


def get_provider(name: str | None = None) -> SatelliteProvider:
    name = name or settings.default_provider
    if name not in _PROVIDERS:
        registry = {
            "earth_search": EarthSearchProvider,
            "planetary_computer": PlanetaryComputerProvider,
            "copernicus": CopernicusProvider,
        }
        if name not in registry:
            raise ProviderError(f"Unknown satellite provider: {name}")
        _PROVIDERS[name] = registry[name]()
    return _PROVIDERS[name]
