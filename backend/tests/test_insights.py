"""Tests for the AI insights engine and API (Phase: AI insights)."""

import pytest
from rest_framework.test import APIClient

from tests.builders import fields
from tests.test_reports import _save
from wellness.models import User
from wellness.services.insights import analyze_all, analyze_period, snapshot


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username="ai1", password="x", role=User.Role.ADMIN)


def _row(total=0, m=0, f=0, **kw):
    d = fields()
    d.update({"total_cases": total, "gender_male": m, "gender_female": f, "gender_other": 0})
    d.update(kw)
    return d


@pytest.fixture
def two_weeklies(db, admin_user):
    a = _save(
        admin_user, "weekly", "15th July", "21st July 2026",
        {"WLN Ctr": _row(10, 6, 4, concern_anxiety=6, stake_ug=10, referral_self=10, mode_online=10),
         "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()},
        {"WLN Ctr": _row(20, 10, 10), "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()},
        secondary={"total_sessions": {"Total": 90}, "no_show_turn_up": {"Total": 10},
                   "active_cases": {"Total": 25}, "clients_over_4_sessions": {"Total": 15},
                   "enquiry_modes": {"mail": 5, "calls_recd": 3, "calls_out": 2}},
    )
    b = _save(
        admin_user, "weekly", "22nd July", "28th July 2026",
        {"WLN Ctr": _row(20, 12, 8, concern_stress=14, concern_anxiety=6, stake_pg=20, referral_mitr=20),
         "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()},
        {"WLN Ctr": _row(25, 15, 10), "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()},
        secondary={"total_sessions": {"Total": 120}, "no_show_turn_up": {"Total": 40},
                   "active_cases": {"Total": 30}, "clients_over_4_sessions": {"Total": 18},
                   "enquiry_modes": {"mail": 8, "calls_recd": 4, "calls_out": 3}},
    )
    return a, b


class TestSnapshot:
    def test_totals(self, two_weeklies):
        a, _ = two_weeklies
        s = snapshot(a)
        assert s["new"] == 10
        assert s["followup"] == 20
        assert s["total"] == 30
        assert s["concern"]["anxiety"] == 6
        assert s["vertical"]["WC"] == 30
        assert s["vertical"]["TA"] == 0
        assert s["total_sessions"] == 90
        assert s["no_show_turn_up"] == 10


class TestAnalyzePeriod:
    def test_period_without_previous(self, two_weeklies):
        a, _ = two_weeklies
        r = analyze_period(a)
        assert r["totals"]["total"] == 30
        assert r["comparison"] is None
        assert r["top"]["concern"][0] == "anxiety"
        assert any("Follow-up cases make up" in i["text"] for i in r["insights"])

    def test_period_with_previous(self, two_weeklies):
        a, b = two_weeklies
        r = analyze_period(b, a)
        assert r["comparison"]["delta_total"] == 15
        assert r["comparison"]["delta_sessions"] == 30
        assert any("Total cases are up 15" in i["text"] for i in r["insights"])

    def test_no_show_warning(self, two_weeklies):
        a, b = two_weeklies
        r = analyze_period(b, a)
        # 40 no-shows out of 120 sessions = 33% -> elevated warning
        assert any("No-shows are elevated" in i["text"] for i in r["insights"])


class TestAnalyzeAll:
    def test_summary(self, two_weeklies):
        a, b = two_weeklies
        r = analyze_all([a, b])
        assert r["summary"]["period_count"] == 2
        assert r["summary"]["total_cases"] == 75
        assert r["summary"]["total_new"] == 30
        assert r["summary"]["total_sessions"] == 210
        assert len(r["trend"]) == 2
        assert r["top"]["concern"][0] in ("anxiety", "stress")
        assert r["anomalies"] == []

    def test_anomaly_detection(self, db, admin_user):
        rows = {"WLN Ctr": _row(5, 3, 2), "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()}
        p1 = _save(admin_user, "weekly", "15th July", "21st July 2026",
                   rows, {t: fields() for t in ("WLN Ctr", "Team A", "Your Dost", "Myndwell")})
        p2 = _save(admin_user, "weekly", "22nd July", "28th July 2026",
                   rows, {t: fields() for t in ("WLN Ctr", "Team A", "Your Dost", "Myndwell")})
        p3 = _save(admin_user, "weekly", "29th July", "04th August 2026",
                   {"WLN Ctr": _row(60, 30, 30), "Team A": _row(), "Your Dost": _row(), "Myndwell": _row()},
                   {t: fields() for t in ("WLN Ctr", "Team A", "Your Dost", "Myndwell")})
        r = analyze_all([p1, p2, p3])
        assert r["anomalies"] and r["anomalies"][0]["period_id"] == p3.id
        assert r["anomalies"][0]["kind"] == "spike"


class TestInsightsAPI:
    def test_overall_endpoint(self, two_weeklies):
        c = APIClient()
        c.force_authenticate(user=two_weeklies[0].created_by)
        r = c.get("/api/insights")
        assert r.status_code == 200
        assert r.data["summary"]["period_count"] == 2
        assert len(r.data["insights"]) > 0

    def test_period_endpoint(self, two_weeklies):
        a, b = two_weeklies
        c = APIClient()
        c.force_authenticate(user=a.created_by)
        r = c.get(f"/api/insights/{b.id}")
        assert r.status_code == 200
        assert r.data["comparison"]["previous_id"] == a.id

    def test_period_endpoint_missing(self, admin_user):
        c = APIClient()
        c.force_authenticate(user=admin_user)
        assert c.get("/api/insights/99999").status_code == 400

    def test_requires_auth(self):
        c = APIClient()
        assert c.get("/api/insights").status_code == 401
