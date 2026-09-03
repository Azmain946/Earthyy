# Earthyy — Earth Observation Intelligence Platform

Earthyy continuously monitors changes on Earth's surface using real satellite
imagery (Sentinel-2 via public STAC catalogues), geospatial processing, and a
persistent historical record. First operational geography: **Bangladesh**;
the geographic engine is globally reusable.

Four intelligence modules run on one shared pipeline:

| Module | What it measures | Method |
|---|---|---|
| **River** | water extent, erosion, accretion, bank movement | MNDWI (Xu 2006) + Otsu segmentation, post-classification comparison |
| **Agriculture** | cultivated area, NDVI/EVI/NDMI condition, stress anomalies | Sentinel-2 spectral indices vs baseline |
| **Forest** | canopy extent, loss/gain, change rate | NDVI-threshold canopy mask + NBR disturbance |
| **Brick Kiln** | candidate kiln sites, new-site detection | BSI+NDVI spectral gate + footprint morphology screening (candidates only) |

The core loop: **Acquire → Process → Analyze → Compare → Measure → Store →
Monitor → Alert → Visualize.**

---

## Architecture

```
React (Vite, MapLibre GL)  ──► FastAPI ──► PostgreSQL + PostGIS
                                 │              ▲
                                 ▼              │
                            RQ queue (Redis) ── Worker
                                 │
                     Satellite providers (STAC):
                     Earth Search (AWS) · Planetary Computer · Copernicus Data Space
                                 │
                     AOI-windowed COG reads (rasterio /vsicurl)
                                 │
                     Geospatial engine (indices → masks → change engine)
                                 │
                     Object storage (local FS, S3-compatible interface)
```

Key design decisions:

- **AOI-only pixel access.** Imagery is read via HTTP range requests from
  Cloud Optimized GeoTIFFs onto a common UTM grid. Full scenes are never
  downloaded; baseline and current arrays are pixel-aligned for change
  detection.
- **One change engine.** All modules call the same mask-transition change
  engine (`app/services/change_engine.py`); each module contributes only its
  segmentation and measurement logic.
- **Provider abstraction.** `SatelliteProvider` → `EarthSearchProvider`
  (default, no credentials), `PlanetaryComputerProvider` (SAS signing),
  `CopernicusProvider` (catalogue search; asset access needs credentials).
- **Background jobs.** Analyses run in an RQ worker with staged progress
  (queued → searching imagery → retrieving → analyzing → calculating changes
  → generating layers → completed/failed) surfaced live in the UI.
- **Scientific honesty.** Confidence scores are data-quality measures
  (valid-pixel fraction, cloud cover) — never fabricated model accuracy.
  Every analysis stores method, provenance (provider/scene/date), processing
  version and explicit limitations. Kiln detections are always `candidate`
  status pending verification. Alert language avoids legal claims.

### Repository layout

```
backend/
  app/
    api/          REST routers (zones, analysis, jobs, alerts, changes, overview, reports, search, files)
    core/         config, database, security, logging
    models/       SQLAlchemy + GeoAlchemy2 models (PostGIS geometry types, spatial indexes)
    schemas/      Pydantic request/response schemas
    services/     change engine, analysis runner, storage, cache, module analyzers
    satellite/    provider abstraction + STAC discovery/ranking
    geospatial/   raster access, spectral indices, masks, vectorize, measure, previews
    workers/      RQ queue + worker entry point
    alerts/       rule-based alert engine
    reports/      PDF/CSV/GeoJSON generation
  alembic/        migrations
  scripts/seed.py Bangladesh zones + model registry + default user
  tests/          geospatial unit tests, API tests, alert rule tests
frontend/
  src/
    components/   map system (MapLibre), compare slider, layer panel, job progress, Earth Time, alerts
    pages/        Overview + shared Module workspace (river/agriculture/forest/brick kilns)
    services/     typed API data-access layer
    hooks/        auth context, job polling
    lib/          API client, types, formatting
docker/           Dockerfiles
docker-compose.yml
.env.example
```

---

## Quick start (Docker)

```bash
cp .env.example .env          # optional; defaults work for local dev
docker compose up --build
```

Then open http://localhost:5173 and sign in with the seeded analyst account:

- **email:** `analyst@earthyy.io`
- **password:** `earthyy-analyst`

## Manual setup (no Docker)

Prerequisites: Python 3.12, Node 22, PostgreSQL 16 + PostGIS, Redis.

```bash
# 1. Database
sudo -u postgres psql -c "CREATE USER earthyy WITH PASSWORD 'earthyy';" \
                      -c "CREATE DATABASE earthyy OWNER earthyy;"
sudo -u postgres psql -d earthyy -c "CREATE EXTENSION postgis;"

# 2. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head          # migrations
.venv/bin/python scripts/seed.py        # default user, model registry, Bangladesh zones
.venv/bin/uvicorn app.main:app --port 8000   # API
.venv/bin/python -m app.workers.worker       # worker (separate terminal)

# 3. Frontend
cd ../frontend
npm install
npm run dev                              # http://localhost:5173 (proxies /api to :8000)
```

API docs: http://localhost:8000/api/docs · Health: http://localhost:8000/api/health

## Running an analysis

1. Open a module (e.g. **River Hydrology**), pick a monitoring zone (or
   “Draw new area…” and draw a polygon on the map).
2. Choose baseline/current dates and a cloud-cover limit, then
   **Run Satellite Analysis**.
3. The job status panel shows each pipeline stage. On completion the map loads
   the generated layers (boundaries, erosion/accretion or loss/gain polygons,
   index rasters, true-color previews) and the inspector shows measurements,
   confidence, provenance and limitations.
4. Use **Split Compare** for the before/after slider, **Earth Time** for the
   stored observation history, and export **PDF / CSV / GeoJSON** reports.
5. Save any drawn AOI as a monitoring zone; threshold breaches create alerts.

## Satellite providers

| Provider | Credentials | Used for |
|---|---|---|
| Earth Search (AWS Element 84) | none | default: Sentinel-2 L2A COGs (search + pixels) |
| Microsoft Planetary Computer | none (SAS signing automatic) | fallback: Sentinel-2, Landsat |
| Copernicus Data Space | `EARTHYY_COPERNICUS_CLIENT_ID/SECRET` | catalogue search (asset download once credentials are configured) |

Select per request with the `provider` parameter, or set
`EARTHYY_DEFAULT_PROVIDER`.

## Adding a new module

1. Create `backend/app/services/modules/<name>.py` exposing
   `analyze(aoi_geojson, params, progress) -> dict` (see `river.py`).
2. Register it in `ANALYZERS` (`app/services/analysis_runner.py`) and add
   alert rules in `app/alerts/engine.py`.
3. Register its method in the model registry (seed script) with honest
   limitations.
4. Frontend: add the module to `MODULE_META`, `MODULE_CARDS` and a route —
   the shared `ModulePage` workspace does the rest.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -q     # geospatial, API, alert rules
cd frontend && npx tsc -b && npm run build             # typecheck + build
```

## Model registry & validation

`GET /api/models` lists every algorithm with version, inputs, status and
limitations. The `metrics` field holds **measured** validation results only
and stays empty until an evaluation against ground truth has been run — no
fabricated accuracy numbers.

## Known limitations (by design, documented in-product)

- Optical water masks respond to river stage; SAR (Sentinel-1) fusion is the
  planned next step for the river module.
- Forest masks are NDVI-threshold proxies; dense cropland can be confused
  with canopy in some seasons.
- Brick-kiln outputs are **candidates** from spectral-morphological screening,
  not verified detections; the registry entry documents how to swap in a
  trained object detector.
- No yield prediction, disease diagnosis, pollution attribution or legality
  claims — the data cannot support them.
