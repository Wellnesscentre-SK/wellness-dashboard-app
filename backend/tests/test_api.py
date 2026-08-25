"""API integration tests for the import flow (Phase 2)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from tests.builders import build_workbook, fields
from wellness.models import Period, User
from wellness.services import parsing as P

FIXTURES = "fixtures"


@pytest.fixture
def admin_user(db):
    user = User.objects.create_user(
        username="admin1", email="admin1@x.local", password="Passw0rd!",
        role=User.Role.ADMIN,
    )
    return user


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        username="root", email="root@x.local", password="Passw0rd!",
        role=User.Role.SUPER_ADMIN,
    )


@pytest.fixture
def client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


def upload(client, path):
    with open(path, "rb") as fh:
        f = SimpleUploadedFile("report.xlsx", fh.read())
        return client.post("/api/imports/preview", {"file": f}, format="multipart")


def workbook_bytes(new_rows=None, fu_rows=None, include_followup=True, secondary=None, subteam_labels=None, report_type="weekly", start="29th July", end="04th August 2026"):
    wb = build_workbook(
        report_type=report_type, start=start, end=end,
        new_rows=new_rows, fu_rows=fu_rows, include_followup=include_followup,
        secondary=secondary, subteam_labels=subteam_labels,
    )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestAuth:
    def test_login_returns_tokens(self, db, admin_user):
        c = APIClient()
        resp = c.post("/api/auth/login", {"username": "admin1", "password": "Passw0rd!"})
        assert resp.status_code == 200
        assert "access" in resp.data and "refresh" in resp.data

    def test_me(self, db, client, admin_user):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.data["role"] == "admin"

    def test_unauthenticated_rejected(self, db):
        c = APIClient()
        assert c.get("/api/auth/me").status_code == 401
        assert c.get("/api/periods").status_code == 401


class TestImportPreview:
    def test_monthly_preview(self, db, client):
        resp = upload(client, f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        assert resp.status_code == 200
        meta = resp.data["meta"]
        assert meta["report_type"] == "monthly"
        assert meta["period_start"] == "2026-07-01"
        assert meta["period_end"] == "2026-07-30"
        assert resp.data["counts"] == {"ready": 8, "warned": 0, "rejected": 0}
        assert resp.data["vertical_totals"]["new"] == {"WC": 12, "TA": 15, "YD": 22, "MW": 23}
        assert resp.data["vertical_totals"]["followup"] == {"WC": 60, "TA": 41, "YD": 170, "MW": 41}
        assert resp.data["preview_id"]
        assert resp.data["duplicate"] is None

    def test_weekly_preview(self, db, client):
        resp = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        assert resp.status_code == 200
        assert resp.data["meta"]["report_type"] == "weekly"
        assert resp.data["vertical_totals"]["new"] == {"WC": 6, "TA": 5, "YD": 4, "MW": 9}
        assert resp.data["vertical_totals"]["followup"] == {"WC": 21, "TA": 9, "YD": 49, "MW": 12}

    def test_structure_reject(self, db, client):
        resp = upload(client, f"{FIXTURES}/reject_overall_report.xlsx")
        assert resp.status_code == 400
        assert resp.data["error"] == P.ERR_SHEET_STRUCTURE

    def test_missing_file(self, db, client):
        resp = client.post("/api/imports/preview", {}, format="multipart")
        assert resp.status_code == 400
        assert resp.data["error"] == "MISSING_FILE"


class TestImportConfirm:
    def test_confirm_creates_period(self, db, client, admin_user):
        preview = upload(client, f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        confirm = client.post("/api/imports/confirm", {"preview_id": preview.data["preview_id"]}, format="json")
        assert confirm.status_code == 200, confirm.data
        period = Period.objects.get(pk=confirm.data["period_id"])
        assert period.status == "complete"
        assert period.case_rows.count() == 8
        assert period.raw_rows.count() == 8
        wc_new = period.case_rows.get(case_type="new", vertical="WC")
        assert wc_new.total_cases == 12
        assert period.case_rows.get(case_type="new", vertical="TA").total_cases == 15

    def test_duplicate_blocked(self, db, client, admin_user):
        p1 = upload(client, f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        assert client.post("/api/imports/confirm", {"preview_id": p1.data["preview_id"]}, format="json").status_code == 200

        p2 = upload(client, f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        assert p2.data["duplicate"] is not None
        confirm = client.post("/api/imports/confirm", {"preview_id": p2.data["preview_id"]}, format="json")
        assert confirm.status_code == 409
        assert confirm.data["error"] == P.ERR_DUPLICATE_PERIOD

    def test_replace_supersedes(self, db, client, admin_user):
        p1 = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        first = client.post("/api/imports/confirm", {"preview_id": p1.data["preview_id"]}, format="json")
        old_id = first.data["period_id"]

        p2 = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        replace = client.post(
            "/api/imports/confirm",
            {"preview_id": p2.data["preview_id"], "replace": True},
            format="json",
        )
        assert replace.status_code == 200
        old = Period.objects.get(pk=old_id)
        new = Period.objects.get(pk=replace.data["period_id"])
        assert old.superseded_by_id == new.id  # versioned, never deleted
        assert old.case_rows.count() == 8  # old rows preserved
        assert Period.objects.filter(superseded_by__isnull=True, report_type="weekly",
                                     period_start="2026-07-29").count() == 1

    def test_warning_row_imports_as_needs_review(self, db, client, admin_user):
        bad = {
            "WLN Ctr": fields(total_cases=5, gender_male=5),  # session/others missing -> fails checks
            "Team A": fields(total_cases=1, gender_male=1, mode_in_person=1, referral_self=1,
                             concern_self_dev=1, stake_ug=1),
            "Your Dost": fields(),
            "Myndwell": fields(),
        }
        data = workbook_bytes(new_rows=bad)
        f = SimpleUploadedFile("bad.xlsx", data)
        preview = client.post("/api/imports/preview", {"file": f}, format="multipart")
        assert preview.status_code == 200
        assert preview.data["counts"]["warned"] >= 1
        confirm = client.post("/api/imports/confirm", {"preview_id": preview.data["preview_id"]}, format="json")
        period = Period.objects.get(pk=confirm.data["period_id"])
        assert period.status == "needs_review"
        assert period.raw_rows.filter(needs_review=True).count() >= 1

    def test_rejected_row_marks_incomplete(self, db, client, admin_user):
        bad = {
            "WLN Ctr": fields(total_cases=-1),  # negative -> rejected
            "Team A": fields(total_cases=1, gender_male=1, mode_in_person=1, referral_self=1,
                             concern_self_dev=1, stake_ug=1),
            "Your Dost": fields(),
            "Myndwell": fields(),
        }
        data = workbook_bytes(new_rows=bad)
        f = SimpleUploadedFile("neg.xlsx", data)
        preview = client.post("/api/imports/preview", {"file": f}, format="multipart")
        assert preview.data["counts"]["rejected"] == 1
        assert preview.data["incomplete"] is True
        confirm = client.post("/api/imports/confirm", {"preview_id": preview.data["preview_id"]}, format="json")
        period = Period.objects.get(pk=confirm.data["period_id"])
        assert period.status == "incomplete"
        assert period.raw_rows.count() == 7  # only the rejected row is skipped

    def test_preview_not_reusable(self, db, client, admin_user):
        preview = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        pid = preview.data["preview_id"]
        assert client.post("/api/imports/confirm", {"preview_id": pid}, format="json").status_code == 200
        assert client.post("/api/imports/confirm", {"preview_id": pid}, format="json").status_code == 409


class TestHistory:
    def test_import_history(self, db, client, admin_user):
        preview = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        client.post("/api/imports/confirm", {"preview_id": preview.data["preview_id"]}, format="json")
        resp = client.get("/api/imports/history")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["rows_imported"] == 8
        assert resp.data[0]["status"] == "complete"


class TestWeeklyComparisonSelection:
    def make_period(self, start, end, report_type="weekly"):
        return Period.objects.create(
            report_type=report_type, period_start=start, period_end=end,
            status=Period.Status.COMPLETE, source=Period.Source.MANUAL,
        )

    def test_ppt_rejects_non_immediate_prior_week(self, db, client):
        self.make_period("2026-07-18", "2026-07-24")
        older = self.make_period("2026-07-25", "2026-07-31")
        self.make_period("2026-08-01", "2026-08-07")
        current = self.make_period("2026-08-08", "2026-08-14")
        response = client.post("/api/reports/generate", {
            "period_id": current.id, "format": "ppt", "previous_period_id": older.id,
        }, format="json")
        assert response.status_code == 400
        assert response.data["error"] == "INVALID_PREVIOUS_PERIOD"

    def test_ppt_rejects_non_weekly_or_overlapping_prior(self, db, client):
        monthly = self.make_period("2026-07-01", "2026-07-31", report_type="monthly")
        overlap = self.make_period("2026-08-06", "2026-08-12")
        current = self.make_period("2026-08-08", "2026-08-14")
        for prior in (monthly, overlap):
            response = client.post("/api/reports/generate", {
                "period_id": current.id, "format": "ppt", "previous_period_id": prior.id,
            }, format="json")
            assert response.status_code == 400
            assert response.data["error"] == "INVALID_PREVIOUS_PERIOD"


class TestRoleEnforcement:
    def test_plain_user_rejected(self, db):
        user = User.objects.create_user(username="u1", password="x", role=User.Role.ADMIN)
        c = APIClient()
        c.force_authenticate(user=user)
        assert c.get("/api/periods").status_code == 200  # admin can view
        data = workbook_bytes()
        f = SimpleUploadedFile("r.xlsx", data)
        assert c.post("/api/imports/preview", {"file": f}, format="multipart").status_code == 200
        assert c.get("/api/imports/history").status_code == 200


def good_row(**kw):
    row = fields(total_cases=2, gender_male=1, gender_female=1, mode_online=2,
                 referral_self=2, concern_stress=2, stake_ug=2)
    row.update(kw)
    return row


class TestManualEntry:
    def _period(self, client, admin_user):
        p = upload(client, f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        return client.post("/api/imports/confirm", {"preview_id": p.data["preview_id"]}, format="json").data["period_id"]

    def test_valid_entry(self, db, client, admin_user):
        pid = self._period(client, admin_user)
        resp = client.post("/api/entries", {
            "period_id": pid, "case_type": "new", "sub_team": "Team A",
            "columns": good_row(),
        }, format="json")
        assert resp.status_code == 200, resp.data
        assert resp.data["needs_review"] is False
        assert resp.data["vertical"] == "TA"
        assert all(c["passed"] for c in resp.data["checks"])

    def test_failed_check_rejected(self, db, client, admin_user):
        pid = self._period(client, admin_user)
        resp = client.post("/api/entries", {
            "period_id": pid, "case_type": "new", "sub_team": "Team A",
            "columns": good_row(gender_male=1, gender_female=1, mode_online=10),  # session sum (10) != total (2)
        }, format="json")
        assert resp.status_code == 422
        assert any(not c["passed"] for c in resp.data["checks"])

    def test_force_save_flags_review(self, db, client, admin_user):
        pid = self._period(client, admin_user)
        resp = client.post("/api/entries", {
            "period_id": pid, "case_type": "new", "sub_team": "Your Dost",
            "columns": good_row(gender_male=1, gender_female=1, mode_online=10),
            "force_save_with_warnings": True,
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["needs_review"] is True
        assert resp.data["vertical"] == "YD"


    def test_negative_value_rejected(self, db, client, admin_user):
        pid = self._period(client, admin_user)
        resp = client.post("/api/entries", {
            "period_id": pid, "case_type": "new", "sub_team": "Myndwell",
            "columns": good_row(total_cases=-1),
        }, format="json")
        assert resp.status_code == 422

    def test_missing_period(self, db, client, admin_user):
        resp = client.post("/api/entries", {
            "period_id": 99999, "case_type": "new", "sub_team": "Team A",
            "columns": good_row(),
        }, format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "PERIOD_NOT_FOUND"
