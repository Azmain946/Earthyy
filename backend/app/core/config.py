"""Application configuration loaded from environment variables (.env supported)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EARTHYY_", extra="ignore")

    app_name: str = "Earthyy Observation Intelligence"
    api_prefix: str = "/api"
    environment: str = "development"
    debug: bool = True

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    database_url: str = "postgresql+psycopg2://earthyy:earthyy@localhost:5432/earthyy"

    # Redis / job queue
    redis_url: str = "redis://localhost:6379/0"
    job_queue_name: str = "earthyy-analysis"
    # Run jobs synchronously in-process (useful for tests / single-process dev).
    eager_jobs: bool = False

    # Object storage (local filesystem by default; S3-compatible later)
    storage_backend: str = "local"
    storage_root: str = str(Path(__file__).resolve().parents[3] / "data" / "storage")

    # Satellite providers
    default_provider: str = "earth_search"
    earth_search_url: str = "https://earth-search.aws.element84.com/v1"
    planetary_computer_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac"
    # Copernicus asset download needs credentials; catalogue search does not.
    copernicus_client_id: str = ""
    copernicus_client_secret: str = ""

    # Processing constraints
    max_aoi_km2: float = 5000.0
    default_max_cloud_cover: float = 30.0
    processing_version: str = "1.0.0"

    # Cache TTLs (seconds)
    stac_search_cache_ttl: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
