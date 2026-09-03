"""API tests: auth, validation, monitoring zones, alerts rules."""
from shapely.geometry import box, mapping

VALID_POLY = mapping(box(89.70, 23.72, 89.74, 23.76))


class TestAuth:
    def test_login_bad_password(self, client):
        r = client.post("/api/auth/login", json={"email": "test@earthyy.io", "password": "wrong"})
        assert r.status_code == 401

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == "test@earthyy.io"


class TestZones:
    def test_create_and_get_zone(self, client, auth_headers):
        r = client.post(
            "/api/monitoring-zones",
            json={"name": "Test Reach", "zone_type": "river", "geometry": VALID_POLY,
                  "baseline_date": "2022-01-01", "thresholds": {"erosion_km2": 0.1}},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        zone = r.json()
        assert zone["zone_type"] == "river"
        assert zone["area_km2"] > 10  # ~4x4 km
        assert zone["geometry"]["type"] == "MultiPolygon"

        r2 = client.get(f"/api/monitoring-zones/{zone['id']}", headers=auth_headers)
        assert r2.status_code == 200

    def test_invalid_geometry_rejected(self, client, auth_headers):
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
        }
        r = client.post(
            "/api/monitoring-zones",
            json={"name": "Bowtie", "zone_type": "general", "geometry": bowtie},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_point_geometry_rejected(self, client, auth_headers):
        r = client.post(
            "/api/monitoring-zones",
            json={"name": "Point", "zone_type": "general",
                  "geometry": {"type": "Point", "coordinates": [89.7, 23.7]}},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_oversized_aoi_rejected(self, client, auth_headers):
        huge = mapping(box(80, 15, 95, 30))
        r = client.post(
            "/api/monitoring-zones",
            json={"name": "Huge", "zone_type": "general", "geometry": huge},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert "too large" in r.json()["detail"].lower()


class TestAnalysisValidation:
    def test_requires_zone_or_geometry(self, client, auth_headers):
        r = client.post(
            "/api/analysis",
            json={"module": "river", "baseline_date": "2020-01-01", "current_date": "2024-01-01"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_date_ordering_enforced(self, client, auth_headers):
        r = client.post(
            "/api/analysis",
            json={"module": "river", "geometry": VALID_POLY,
                  "baseline_date": "2024-01-01", "current_date": "2020-01-01"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_unknown_module_rejected(self, client, auth_headers):
        r = client.post(
            "/api/analysis",
            json={"module": "volcano", "geometry": VALID_POLY,
                  "baseline_date": "2020-01-01", "current_date": "2024-01-01"},
            headers=auth_headers,
        )
        assert r.status_code == 422


class TestSatelliteSearchValidation:
    def test_bad_bbox_rejected(self, client, auth_headers):
        r = client.get(
            "/api/satellite/scenes?bbox=abc&start=2024-01-01&end=2024-02-01",
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_out_of_range_bbox_rejected(self, client, auth_headers):
        r = client.get(
            "/api/satellite/scenes?bbox=200,10,210,20&start=2024-01-01&end=2024-02-01",
            headers=auth_headers,
        )
        assert r.status_code == 422


class TestOverviewAndHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["components"]["database"] == "ok"

    def test_overview_shape(self, client, auth_headers):
        r = client.get("/api/overview", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "zones" in data and "detections" in data and "modules" in data
