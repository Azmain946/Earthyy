"""Earthyy Observation Intelligence — FastAPI application."""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger("earthyy.api")
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.processing_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    if not request.url.path.startswith("/api/files"):
        logger.info(
            "method=%s path=%s status=%s duration_ms=%.1f",
            request.method, request.url.path, response.status_code, duration_ms,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("event=unhandled_error path=%s error=%s", request.url.path, exc, exc_info=settings.debug)
    detail = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail})


@app.get("/api/health")
def health():
    """Basic system health: database, redis, storage."""
    from sqlalchemy import text

    from app.core.database import engine
    from app.services.cache import _client
    from app.services.storage import get_storage

    status: dict = {"api": "ok"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc}"
    status["redis"] = "ok" if _client() is not None else "unavailable"
    try:
        get_storage()
        status["storage"] = "ok"
    except Exception as exc:
        status["storage"] = f"error: {exc}"
    healthy = all(v == "ok" for v in status.values())
    return {"status": "ok" if healthy else "degraded", "components": status}


from app.api import alerts, analysis, auth, changes, files, jobs, overview, registry, reports, satellite, search, zones  # noqa: E402

for router in (
    auth.router, zones.router, analysis.router, jobs.router, satellite.router,
    changes.router, alerts.router, overview.router, reports.router, files.router,
    search.router, registry.router,
):
    app.include_router(router, prefix=settings.api_prefix)
