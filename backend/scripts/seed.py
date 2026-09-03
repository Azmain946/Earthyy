"""Seed Earthyy with the default analyst user, model registry and
Bangladesh-first monitoring zones.

Zones are real geographic areas (Padma reach, Rajshahi paddy belt, Sundarbans
buffer, Gazipur kiln belt). Measurements/analyses are NOT seeded — those come
exclusively from running the real pipeline against live satellite data.

Run:  python scripts/seed.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, box, mapping

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.geospatial.measure import geodesic_area_km2
from app.models import ModelRegistryEntry, MonitoringZone, User

DEFAULT_EMAIL = "analyst@earthyy.io"
DEFAULT_PASSWORD = "earthyy-analyst"

ZONES = [
    {
        "name": "Padma Reach 04 — Rajbari / Goalanda Sector",
        "zone_type": "river",
        # Padma river near Goalanda Ghat confluence
        "bbox": (89.68, 23.70, 89.84, 23.82),
        "baseline_date": date(2020, 1, 15),
        "thresholds": {"erosion_km2": 0.05, "movement_m_per_year": 25.0},
        "description": "High geomorphic activity reach at the Padma-Jamuna confluence.",
    },
    {
        "name": "Rajshahi Division Boro Paddy Belt",
        "zone_type": "agriculture",
        # Godagari, Rajshahi
        "bbox": (88.28, 24.34, 88.40, 24.44),
        "baseline_date": date(2022, 2, 1),
        "thresholds": {"ndvi_drop_pct": 15.0, "stress_area_ha": 5.0},
        "description": "Boro-season irrigated rice belt in the Barind Tract.",
    },
    {
        "name": "Sundarbans Northern Buffer — Shyamnagar Sector",
        "zone_type": "forest",
        # Northern Sundarbans mangrove edge, Satkhira
        "bbox": (89.20, 22.28, 89.36, 22.40),
        "baseline_date": date(2022, 2, 15),
        "thresholds": {"forest_loss_ha": 1.0},
        "description": "Mangrove buffer corridor north of the protected Sundarbans core.",
    },
    {
        "name": "Gazipur Outer Ring Kiln Cluster — Turag Basin",
        "zone_type": "brick_kiln",
        # Gazipur / Turag basin brick kiln belt north of Dhaka
        "bbox": (90.34, 23.93, 90.46, 24.02),
        "baseline_date": date(2021, 12, 1),
        "thresholds": {"new_candidates": 1},
        "description": "Peri-urban kiln belt along the Turag river corridor.",
    },
]

MODELS = [
    {
        "model_name": "mndwi-otsu-water-v1",
        "version": "1.0.0",
        "module": "river",
        "model_type": "index_threshold",
        "source": "MNDWI (Xu, 2006) + Otsu (1979) segmentation",
        "input_requirements": {"bands": ["green", "swir16"], "sensor": "Sentinel-2 L2A", "resolution_m": 10},
        "output_type": "water_mask",
        "limitations": "Optical only; river stage differences appear as change. SAR fusion planned.",
    },
    {
        "model_name": "ndvi-spectral-agriculture-v1",
        "version": "1.0.0",
        "module": "agriculture",
        "model_type": "index_threshold",
        "source": "NDVI (Rouse 1974), EVI (Huete 2002), NDMI (Gao 1996)",
        "input_requirements": {"bands": ["blue", "green", "red", "nir", "swir16"], "sensor": "Sentinel-2 L2A"},
        "output_type": "vegetation_statistics",
        "limitations": "No crop-type classification or yield estimation without ground truth.",
    },
    {
        "model_name": "ndvi-threshold-canopy-v1",
        "version": "1.0.0",
        "module": "forest",
        "model_type": "index_threshold",
        "source": "NDVI threshold (0.6) + morphological cleaning; NBR disturbance",
        "input_requirements": {"bands": ["red", "nir", "swir22"], "sensor": "Sentinel-2 L2A"},
        "output_type": "canopy_mask",
        "limitations": "Proxy canopy mask; dense cropland can be confused with forest seasonally.",
    },
    {
        "model_name": "bsi-morphology-kiln-screening-v1",
        "version": "1.0.0",
        "module": "brick_kiln",
        "model_type": "object_detection",
        "source": "BSI (Rikimaru 2002) + NDVI gate + footprint morphology filter",
        "input_requirements": {"bands": ["blue", "green", "red", "nir", "swir16"], "sensor": "Sentinel-2 L2A"},
        "output_type": "candidate_points",
        "status": "experimental",
        "limitations": (
            "Candidate screening only — no validated detection accuracy. Bright bare "
            "surfaces cause false positives. Designed to be replaced by a trained "
            "detector (e.g. YOLO on high-res imagery) via this registry."
        ),
    },
    {
        "model_name": "mask-transition-change-engine-v1",
        "version": "1.0.0",
        "module": "core",
        "model_type": "change_detection",
        "source": "Post-classification comparison of pixel-aligned class masks",
        "input_requirements": {"inputs": "two boolean masks on a common UTM grid"},
        "output_type": "gain/loss polygons + areas",
        "limitations": "Sensitive to per-date segmentation errors; cloud pixels excluded on both dates.",
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=DEFAULT_EMAIL).first()
        if user is None:
            user = User(
                email=DEFAULT_EMAIL,
                hashed_password=hash_password(DEFAULT_PASSWORD),
                full_name="Earthyy Analyst",
                role="analyst",
            )
            db.add(user)
            db.flush()
            print(f"Created user {DEFAULT_EMAIL}")

        for m in MODELS:
            if not db.query(ModelRegistryEntry).filter_by(model_name=m["model_name"]).first():
                db.add(ModelRegistryEntry(**m))
                print(f"Registered model {m['model_name']}")

        for z in ZONES:
            if db.query(MonitoringZone).filter_by(name=z["name"]).first():
                continue
            w, s, e, n = z["bbox"]
            geom = MultiPolygon([box(w, s, e, n)])
            db.add(MonitoringZone(
                name=z["name"],
                zone_type=z["zone_type"],
                geometry=from_shape(geom, srid=4326),
                area_km2=round(geodesic_area_km2(mapping(geom)), 3),
                baseline_date=z["baseline_date"],
                thresholds=z["thresholds"],
                description=z["description"],
                user_id=user.id,
                status="active",
            ))
            print(f"Created zone {z['name']}")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
