"""Serve stored objects (raster previews, layer PNGs, reports)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage import get_storage

router = APIRouter(prefix="/files", tags=["files"])

MEDIA_TYPES = {".png": "image/png", ".pdf": "application/pdf", ".csv": "text/csv",
               ".geojson": "application/geo+json", ".json": "application/json"}


@router.get("/{key:path}")
def get_file(key: str):
    storage = get_storage()
    try:
        path = storage.path(key)
    except ValueError:
        raise HTTPException(400, "Invalid file key")
    if path is None:
        raise HTTPException(404, "File not found")
    suffix = path.suffix.lower()
    return FileResponse(path, media_type=MEDIA_TYPES.get(suffix, "application/octet-stream"))
