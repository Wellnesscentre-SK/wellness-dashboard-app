"""API tests for manual period create / view / edit / delete."""

import pytest
from rest_framework.test import APIClient

from wellness.models import Period, User


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin1", email="admin1@x.local", password="Passw0rd!",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def payload(**overrides):
    data = {
        "report_type": "weekly",
        "period_start": "2026-08-10",
        "period_end": "2026-08-16",
        "status": "complete",
        "source": "manual",
        "title": "Test week",
    }
    data.update(overrides)
    return data


class TestPeriodCreate:
    def test_create_valid_period(self, db, client):
        resp = client.post("/api/periods", payload(), format="json")
        assert resp.status_code == 201
        p = resp.data
        assert p["report_type"] == "weekly"
        assert p["period_start"] == "2026-08-10"
        assert p["period_end"] == "2026-08-16"
        assert p["source"] == "manual"
        assert Period.objects.filter(pk=p["id"]).exists()

    def test_create_duplicate_rejected(self, db, client):
        assert client.post("/api/periods", payload(), format="json").status_code == 201
        resp = client.post("/api/periods", payload(), format="json")
        assert resp.status_code == 409
        assert resp.data["error"] == "PERIOD_EXISTS"

    def test_same_range_different_type_allowed(self, db, client):
        assert client.post("/api/periods", payload(report_type="weekly"), format="json").status_code == 201
        resp = client.post(
            "/api/periods", payload(report_type="monthly"), format="json"
        )
        assert resp.status_code == 201

    def test_invalid_report_type(self, db, client):
        resp = client.post("/api/periods", payload(report_type="yearly"), format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "INVALID_REPORT_TYPE"

    def test_invalid_dates(self, db, client):
        resp = client.post("/api/periods", payload(period_start="2026-08-20"), format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "INVALID_DATES"

    def test_invalid_status(self, db, client):
        resp = client.post("/api/periods", payload(status="archived"), format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "INVALID_STATUS"


class TestPeriodEditDelete:
    def _create(self, client):
        return client.post("/api/periods", payload(), format="json").data["id"]

    def test_edit_period(self, db, client):
        pid = self._create(client)
        resp = client.patch(f"/api/periods/{pid}", payload(period_start="2026-08-11"), format="json")
        assert resp.status_code == 200
        assert resp.data["period_start"] == "2026-08-11"

    def test_edit_to_duplicate_rejected(self, db, client):
        pid = self._create(client)
        client.post("/api/periods", payload(period_start="2026-08-17", period_end="2026-08-23"), format="json")
        resp = client.patch(f"/api/periods/{pid}", payload(period_start="2026-08-17", period_end="2026-08-23"), format="json")
        assert resp.status_code == 409

    def test_delete_period(self, db, client):
        pid = self._create(client)
        resp = client.delete(f"/api/periods/{pid}")
        assert resp.status_code == 204
        assert not Period.objects.filter(pk=pid).exists()

    def test_delete_missing_period(self, db, client):
        resp = client.delete("/api/periods/99999")
        assert resp.status_code == 400
        assert resp.data["error"] == "PERIOD_NOT_FOUND"

    def test_requires_auth(self, db, admin_user):
        c = APIClient()
        resp = c.post("/api/periods", payload(), format="json")
        assert resp.status_code in (401, 403)

