"""Parser + validator regression tests (Phase 1)."""

import datetime as dt

import pytest

from wellness.services import parsing as P
from tests.builders import build_workbook, fields

FIXTURES = "fixtures"


# ---------------------------------------------------------------------------
# Title / date parsing
# ---------------------------------------------------------------------------

class TestTitleParsing:
    def test_weekly_two_month_names(self):
        assert P.parse_title("Weekly Wellness Report From 29th July to 04th August 2026") == (
            "weekly", dt.date(2026, 7, 29), dt.date(2026, 8, 4),
        )

    def test_monthly_shared_month(self):
        assert P.parse_title("Monthly Wellness Report From 01st to 30th July 2026") == (
            "monthly", dt.date(2026, 7, 1), dt.date(2026, 7, 30),
        )

    def test_no_ordinal_suffix(self):
        assert P.parse_title("Weekly Wellness Report From 1 July to 7 July 2026") == (
            "weekly", dt.date(2026, 7, 1), dt.date(2026, 7, 7),
        )

    def test_year_attached_to_start(self):
        assert P.parse_title("Weekly Wellness Report From 29th July 2026 to 04th August 2026") == (
            "weekly", dt.date(2026, 7, 29), dt.date(2026, 8, 4),
        )

    def test_ordinal_edge_forms(self):
        assert P.parse_title_date("01st July 2026") == (dt.date(2026, 7, 1), 2026)
        assert P.parse_title_date("2nd June")[1] is None
        assert P.parse_title_date("23rd May 2025")[0].day == 23
        assert P.parse_title_date("31st Dec 2025")[0].month == 12

    def test_not_a_wellness_title(self):
        assert P.parse_title("Overall report for July") is None


# ---------------------------------------------------------------------------
# Real fixture regression (spec section 14 / 22)
# ---------------------------------------------------------------------------

class TestRealFixtures:
    def test_monthly_grand_total_and_verticals(self):
        r = P.parse_excel(f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        assert r.report_type == "monthly"
        assert (r.period_start, r.period_end) == (dt.date(2026, 7, 1), dt.date(2026, 7, 30))
        m = r.merged_rows()
        for ct in ("new", "followup"):
            assert sum(m[ct, v]["total_cases"] for v in P.VERTICALS) == sum(
                row.columns["total_cases"] for row in r.rows if row.case_type == ct and row.status != "rejected"
            )
        assert m["new", "WC"]["total_cases"] + m["followup", "WC"]["total_cases"] == 72
        assert m["new", "TA"]["total_cases"] + m["followup", "TA"]["total_cases"] == 56
        assert m["new", "YD"]["total_cases"] + m["followup", "YD"]["total_cases"] == 192
        assert m["new", "MW"]["total_cases"] + m["followup", "MW"]["total_cases"] == 64

        # Grand total = 384, gender 193 / 167 / 24
        gt = {}
        for f in P.COLUMN_NAMES:
            gt[f] = sum(m[ct, v][f] for ct in ("new", "followup") for v in P.VERTICALS)
        assert gt["total_cases"] == 384
        assert (gt["gender_male"], gt["gender_female"], gt["gender_other"]) == (193, 167, 24)

    def test_monthly_secondary_metrics(self):
        r = P.parse_excel(f"{FIXTURES}/monthly_01jul_30jul_2026.xlsx")
        sec = r.secondary
        assert sec.total_sessions == {"WC": 31, "TA": 30, "YD": 346, "MW": 85, "Total": 492}
        assert sec.early_prevention_warning["Total"] == 2
        assert sec.no_show_turn_up["Total"] == 2
        assert sec.active_cases["Total"] == 405
        assert sec.clients_over_4_sessions["Total"] == 105
        assert sec.enquiry_modes == {"mail": 0, "calls_recd": 3, "calls_out": 5}
        assert sec.stray_cells  # B20 stray cell present in the real file

    def test_weekly_fixture(self):
        r = P.parse_excel(f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        assert r.report_type == "weekly"
        assert (r.period_start, r.period_end) == (dt.date(2026, 7, 29), dt.date(2026, 8, 4))
        m = r.merged_rows()
        new_total = sum(m["new", v]["total_cases"] for v in P.VERTICALS)
        fu_total = sum(m["followup", v]["total_cases"] for v in P.VERTICALS)
        assert (new_total, fu_total, new_total + fu_total) == (24, 91, 115)
        assert r.secondary.total_sessions["Total"] == 169

    def test_mislabeled_weekly_title_flagged(self):
        r = P.parse_excel(f"{FIXTURES}/weekly_mislabeled_22jul_28jul_2026.xlsx")
        assert r.report_type == "monthly"  # title string is authoritative
        assert r.title_range_mismatch is True  # ...but range contradicts it
        m = r.merged_rows()
        for v, expected in [("WC", 25), ("TA", 16), ("YD", 41), ("MW", 21)]:
            assert m["new", v]["total_cases"] + m["followup", v]["total_cases"] == expected

    def test_structure_reject_unrelated_file(self):
        with pytest.raises(P.SheetStructureError) as exc:
            P.parse_excel(f"{FIXTURES}/reject_overall_report.xlsx")
        assert exc.value.code == P.ERR_SHEET_STRUCTURE

    def test_file_hash_computed(self):
        r = P.parse_excel(f"{FIXTURES}/weekly_29jul_04aug_2026.xlsx")
        assert len(r.file_sha256) == 64


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

class TestChecks:
    def test_all_five_pass(self):
        row = fields(
            total_cases=6,
            gender_male=5, gender_female=1,
            mode_in_person=6,
            referral_self=5, referral_friend=1,
            concern_interpersonal=2, concern_self_dev=3, concern_clinical=1,
            stake_ug=2, stake_pg=1, stake_faculty=1,
            stake_employee_family=1, stake_postdoc=1,
        )
        checks = P.run_checks(row)
        assert all(c.passed for c in checks)
        assert [c.name for c in checks] == ["gender", "session", "referral", "concern", "stakeholder"]

    def test_stakeholder_uses_all_8_columns(self):
        # 7-col sum matches total, but the 8th column (unidentified) breaks it.
        row = fields(
            total_cases=5,
            stake_ug=2, stake_pg=1, stake_faculty=1, stake_employee_family=1,  # 5
            stake_unidentified=1,  # -> 6, must FAIL
        )
        checks = P.run_checks(row)
        stakeholder = next(c for c in checks if c.name == "stakeholder")
        assert stakeholder.passed is False
        assert stakeholder.off_by == 1

    def test_off_by_negative(self):
        row = fields(total_cases=6, gender_male=4, gender_female=1)
        gender = next(c for c in P.run_checks(row) if c.name == "gender")
        assert gender.off_by == -1

    def test_zero_denominator_edge(self):
        row = fields(total_cases=0)
        assert all(c.passed for c in P.run_checks(row))

    def test_stakeholder_check_on_buggy_template_rows(self):
        # Row 6 is one of the template's buggy SUM(Y:AE) rows. Our app must
        # still flag it when the 8th column breaks the sum.
        new_rows = {
            "WLN Ctr": fields(total_cases=2, stake_ug=2, stake_unidentified=1),
            "Team A": fields(),
            "Your Dost": fields(),
            "Myndwell": fields(),
        }
        wb = build_workbook(new_rows=new_rows)
        import io

        buf = io.BytesIO()
        wb.save(buf)
        r = P.parse_excel(buf.getvalue())
        wln = next(row for row in r.rows if row.sub_team == "WLN Ctr")
        assert wln.status == "warning"
        st = next(c for c in wln.checks if c.name == "stakeholder")
        assert st.passed is False


class TestCellRules:
    def test_negative_rejected(self):
        new_rows = {"WLN Ctr": fields(total_cases=5, gender_male=-1)}
        r = parse_bytes(build_workbook(new_rows=new_rows))
        wln = next(row for row in r.rows if row.sub_team == "WLN Ctr")
        assert wln.status == "rejected"
        assert wln.issues[0].code == P.ERR_NEGATIVE_VALUE

    def test_blank_total_rejected(self):
        import copy

        rows = {t: fields() for t in P.TEAMS}
        rows["WLN Ctr"] = fields()
        wb = build_workbook(new_rows=rows)
        wb.active["D6"] = None  # blank total for WLN Ctr new
        r = parse_bytes(wb)
        wln = next(row for row in r.rows if row.sub_team == "WLN Ctr")
        assert wln.status == "rejected"
        assert wln.issues[0].code == P.ERR_MISSING_MANDATORY

    def test_decimal_rejected(self):
        new_rows = {"Team A": fields(total_cases=5, gender_male=2.5)}
        r = parse_bytes(build_workbook(new_rows=new_rows))
        ta = next(row for row in r.rows if row.sub_team == "Team A")
        assert ta.status == "rejected"
        assert ta.issues[0].code == P.ERR_NON_INTEGER

    def test_float_whole_number_accepted(self):
        new_rows = {
            "Team A": fields(total_cases=5, gender_male=5.0, mode_in_person=5,
                             referral_self=5, concern_self_dev=5, stake_ug=5),
        }
        r = parse_bytes(build_workbook(new_rows=new_rows))
        ta = next(row for row in r.rows if row.sub_team == "Team A")
        assert ta.status == "ready"


class TestMerges:
    def test_verticals_remain_separate_every_group(self):
        wln = fields(total_cases=3, concern_anxiety=1, gender_male=2, mode_online=3,
                     referral_self=3, stake_ug=3)
        ta = fields(total_cases=4, concern_anxiety=1, gender_female=4, mode_in_person=4,
                    referral_dean=4, stake_pg=4)
        r = parse_bytes(build_workbook(new_rows={"WLN Ctr": wln, "Team A": ta}))
        m = r.merged_rows()
        assert m["new", "WC"]["total_cases"] == 3
        assert m["new", "TA"]["total_cases"] == 4
        assert m["new", "WC"]["gender_male"] == 2 and m["new", "TA"]["gender_female"] == 4
        assert m["new", "WC"]["mode_online"] == 3 and m["new", "TA"]["mode_in_person"] == 4
        assert m["new", "WC"]["referral_self"] == 3 and m["new", "TA"]["referral_dean"] == 4
        assert m["new", "WC"]["concern_anxiety"] == 1 and m["new", "TA"]["concern_anxiety"] == 1
        assert m["new", "WC"]["stake_ug"] == 3 and m["new", "TA"]["stake_pg"] == 4

    def test_rejected_rows_excluded_from_merge(self):
        new_rows = {
            "WLN Ctr": fields(total_cases=-1),  # rejected
            "Team A": fields(total_cases=5),
        }
        r = parse_bytes(build_workbook(new_rows=new_rows))
        m = r.merged_rows()
        assert m["new", "WC"]["total_cases"] == 0
        assert m["new", "TA"]["total_cases"] == 5

    def test_secondary_metrics_merge(self):
        secondary = {
            "total_sessions": {"WLN Ctr": 27, "Team A": 14, "Your Dost": 100, "Myndwell": 28, "Total": 169},
            "active_cases": {"WLN Ctr": 21, "Team A": 9, "Your Dost": 26, "Myndwell": 65, "Total": 121},
        }
        r = parse_bytes(build_workbook(secondary=secondary))
        sec = r.secondary
        assert sec.total_sessions == {"WC": 27, "TA": 14, "YD": 100, "MW": 28, "Total": 169}
        assert sec.active_cases == {"WC": 21, "TA": 9, "YD": 26, "MW": 65, "Total": 121}

    def test_enquiry_modes_totals_only(self):
        secondary = {
            "enquiry_modes": {"mail": 1, "calls_recd": 2, "calls_out": 3},
        }
        r = parse_bytes(build_workbook(secondary=secondary))
        assert r.secondary.enquiry_modes == {"mail": 1, "calls_recd": 2, "calls_out": 3}


class TestPartialPeriod:
    def test_missing_followup_block(self):
        r = parse_bytes(build_workbook(include_followup=False))
        assert any("incomplete" in w for w in r.warnings)
        fu_rows = [row for row in r.rows if row.case_type == "followup"]
        assert all(row.status == "rejected" for row in fu_rows)

    def test_missing_subteam_row_rejected(self):
        new_rows = {t: fields() for t in P.TEAMS}
        r = parse_bytes(build_workbook(new_rows=new_rows, subteam_labels={"Your Dost": None}))
        yd = next(row for row in r.rows if row.case_type == "new" and row.sub_team == "<missing>")
        assert yd.status == "rejected"


def parse_bytes(wb):
    import io

    buf = io.BytesIO()
    wb.save(buf)
    return P.parse_excel(buf.getvalue())
