"""Shared validate-and-save layer.

Both the Excel-import path and the manual-entry path converge here (spec
3B: "Never let manual entry and Excel import diverge into two different
validation implementations"). The server re-runs validation unconditionally.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction

from wellness.models import (
    AuditLog,
    CaseRow,
    EnquiryModes,
    ImportEvent,
    Period,
    RawSubteamRow,
    SecondaryMetrics,
)
from wellness.services import parsing as P
from wellness.services.parsing import COLUMN_NAMES, run_checks, VERTICALS


class DuplicatePeriodError(Exception):
    def __init__(self, existing: Period):
        self.existing = existing
        super().__init__("A report for this exact period already exists.")


class ValidationFailedError(Exception):
    def __init__(self, checks, message):
        self.checks = checks
        self.message = message
        super().__init__(message)


def active_period_for(report_type, period_start, period_end) -> Period | None:
    return Period.objects.filter(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        superseded_by__isnull=True,
    ).first()


def next_entry_no(period: Period) -> str:
    count = period.raw_rows.count()
    return f"#{count + 1:04d}"


def check_results_dict(checks) -> dict:
    return {
        c.name: {"passed": c.passed, "expected": c.expected, "actual": c.actual}
        for c in checks
    }


def merge_and_upsert_case_rows(period: Period) -> None:
    """Recompute four independent CaseRows from the source sub-team rows."""
    # Raw rows are an append-only version log; ordering by created_at,id makes
    # the dict below keep the NEWEST row per (case_type, sub_team).
    rows = list(period.raw_rows.order_by("created_at", "id"))
    merged = {}
    for case_type in ("new", "followup"):
        by_team = {r.sub_team: r for r in rows if r.case_type == case_type}
        for vertical, members in {
            "WC": ["WLN Ctr"],
            "TA": ["Team A"],
            "YD": ["Your Dost"],
            "MW": ["Myndwell"],
        }.items():
            member_rows = [by_team[t] for t in members if t in by_team]
            columns = {
                field: sum(r.raw_payload.get(field, 0) for r in member_rows)
                for field in COLUMN_NAMES
            }
            needs_review = any(r.needs_review for r in member_rows)
            reasons = [r.reason for r in member_rows if r.reason]
            merged[(case_type, vertical)] = columns

            CaseRow.objects.update_or_create(
                period=period,
                case_type=case_type,
                vertical=vertical,
                defaults={
                    **columns,
                    "needs_review": needs_review,
                    "review_reason": "; ".join(reasons) if reasons else None,
                },
            )


def _write_secondary(period: Period, report: P.ParsedReport) -> None:
    sec = report.secondary
    for vertical, total in [
        ("WC", sec.total_sessions["WC"]),
        ("TA", sec.total_sessions["TA"]),
        ("YD", sec.total_sessions["YD"]),
        ("MW", sec.total_sessions["MW"]),
        ("Total", sec.total_sessions["Total"]),
    ]:
        SecondaryMetrics.objects.update_or_create(
            period=period,
            vertical=vertical,
            defaults={
                "total_sessions": sec.total_sessions[vertical],
                "early_prevention_warning": sec.early_prevention_warning[vertical],
                "no_show_turn_up": sec.no_show_turn_up[vertical],
                "active_cases": sec.active_cases[vertical],
                "clients_over_4_sessions": sec.clients_over_4_sessions[vertical],
            },
        )
    EnquiryModes.objects.update_or_create(
        period=period,
        defaults={
            "mail": sec.enquiry_modes["mail"],
            "calls_recd": sec.enquiry_modes["calls_recd"],
            "calls_out": sec.enquiry_modes["calls_out"],
        },
    )


def _determine_status(needs_review: bool, rejected_count: int) -> str:
    if rejected_count > 0:
        return Period.Status.INCOMPLETE
    if needs_review:
        return Period.Status.NEEDS_REVIEW
    return Period.Status.COMPLETE


def save_import(report, user, filename: str, raw_bytes: bytes, replace: bool = False) -> ImportEvent:
    """Commit a parsed import. Raises DuplicatePeriodError unless replace."""
    with transaction.atomic():
        dup = active_period_for(report.report_type, report.period_start, report.period_end)
        if dup and not replace:
            raise DuplicatePeriodError(dup)

        # When replacing, the new period shares the (type, start, end) key of an
        # active period. The partial unique index (superseded_by IS NULL) would
        # reject the INSERT, so the new row starts "superseded by" the old one
        # (inactive in the index), then the roles flip below.
        period = Period.objects.create(
            report_type=report.report_type,
            period_start=report.period_start,
            period_end=report.period_end,
            source=Period.Source.UPLOAD,
            title=report.title,
            created_by=user,
            superseded_by=dup if (dup and replace) else None,
        )

        warned = rejected = imported = 0
        for row in report.rows:
            if row.status == "rejected":
                rejected += 1
                continue
            if row.status == "warning":
                warned += 1
            else:
                imported += 1
            RawSubteamRow.objects.create(
                period=period,
                case_type=row.case_type,
                sub_team=row.sub_team,
                entry_no=next_entry_no(period),
                source="upload",
                raw_payload=row.columns,
                check_results=check_results_dict(row.checks),
                needs_review=row.needs_review,
                reason=row.reason,
                created_by=user,
            )

        merge_and_upsert_case_rows(period)
        _write_secondary(period, report)

        if dup and replace:
            dup.superseded_by = period
            dup.save(update_fields=["superseded_by"])
            period.superseded_by = None
            period.save(update_fields=["superseded_by"])

        period.status = _determine_status(warned > 0, rejected)
        period.save(update_fields=["status"])

        imp = ImportEvent.objects.create(
            period=period,
            source="upload",
            original_filename=filename,
            file_hash=report.file_sha256,
            file=ContentFile(raw_bytes, name=filename),
            rows_imported=imported,
            rows_warned=warned,
            rows_rejected=rejected,
            imported_by=user,
        )

        log_audit(
            user, "imported", "period", period.id,
            {"filename": filename, "replace": replace,
             "imported": imported, "warned": warned, "rejected": rejected,
             "file_hash": report.file_sha256},
        )
        return imp


def bulk_save_manual_entries(
    period: Period,
    rows_data: list[dict],
    user,
    force_save_with_warnings: bool = False,
) -> tuple[list[RawSubteamRow], dict]:
    """Bulk update or create the worksheet sub-team rows for a period.

    Recalculates Total Cases = Male + Female + Others for every row,
    upserts RawSubteamRow records, recomputes merged CaseRows, and logs audit entries.
    """
    if period.superseded_by_id:
        raise PermissionError("Cannot edit a superseded period.")

    processed_rows = []
    all_checks = {}
    any_failed = False
    all_issues = []

    for row_info in rows_data:
        case_type = row_info.get("case_type", "new")
        sub_team = row_info.get("sub_team", "")
        columns = row_info.get("columns", {})

        clean = {}
        for field in COLUMN_NAMES:
            raw_val = columns.get(field)
            if raw_val is not None:
                val, issue = _coerce_cell(raw_val, field)
                if issue:
                    all_issues.append(f"{case_type}/{sub_team}: {issue}")
                if field != "total_cases":
                    clean[field] = val
            else:
                if field != "total_cases":
                    clean[field] = 0

        # Total Cases is strictly derived from Gender (Section 6 & 30)
        clean["total_cases"] = (
            clean.get("gender_male", 0)
            + clean.get("gender_female", 0)
            + clean.get("gender_other", 0)
        )


        checks = run_checks(clean)
        failed = any(not c.passed for c in checks)
        if failed:
            any_failed = True

        all_checks[f"{case_type}_{sub_team}"] = checks
        processed_rows.append({
            "case_type": case_type,
            "sub_team": sub_team,
            "clean": clean,
            "checks": checks,
            "failed": failed,
        })

    if all_issues:
        raise ValidationFailedError([], "; ".join(all_issues))

    if any_failed and not force_save_with_warnings:
        failed_checks_list = [c for check_list in all_checks.values() for c in check_list]
        raise ValidationFailedError(
            failed_checks_list,
            "Verification checks failed for one or more rows. Submit with force_save_with_warnings=true or correct values.",
        )


    saved_raws = []
    with transaction.atomic():
        for item in processed_rows:
            case_type = item["case_type"]
            sub_team = item["sub_team"]
            clean = item["clean"]
            checks = item["checks"]
            failed = item["failed"]

            existing = RawSubteamRow.objects.filter(
                period=period, case_type=case_type, sub_team=sub_team
            ).order_by("-created_at").first()

            old_payload = existing.raw_payload if existing else {}

            raw = RawSubteamRow.objects.create(
                period=period,
                case_type=case_type,
                sub_team=sub_team,
                entry_no=next_entry_no(period),
                source="manual",
                raw_payload=clean,
                check_results=check_results_dict(checks),
                needs_review=failed,
                reason=None if not failed else _reason_for(checks),
                created_by=user,
            )
            saved_raws.append(raw)

            # Audit diff logging
            diffs = {}
            for k, v in clean.items():
                old_v = old_payload.get(k, 0)
                if old_v != v:
                    diffs[k] = {"old": old_v, "new": v}

            if diffs or not existing:
                log_audit(
                    user,
                    "worksheet_cell_edit" if existing else "worksheet_entry_created",
                    "raw_subteam_row",
                    raw.id,
                    {
                        "period_id": period.id,
                        "case_type": case_type,
                        "sub_team": sub_team,
                        "diffs": diffs,
                        "needs_review": failed,
                    },
                )

        merge_and_upsert_case_rows(period)

        if any_failed:
            period.status = Period.Status.NEEDS_REVIEW
            period.save(update_fields=["status"])
        else:
            period.status = Period.Status.COMPLETE
            period.save(update_fields=["status"])

    return saved_raws, all_checks


def save_manual_entry(
    period: Period,
    case_type: str,
    sub_team: str,
    columns: dict,
    user,
    force_save_with_warnings: bool = False,
) -> tuple[RawSubteamRow, CaseRow, list]:
    """Create one manual sub-team entry (spec 3B)."""
    raws, checks_dict = bulk_save_manual_entries(
        period,
        [{"case_type": case_type, "sub_team": sub_team, "columns": columns}],
        user,
        force_save_with_warnings,
    )
    raw = raws[0]
    case_row = CaseRow.objects.get(
        period=period,
        case_type=case_type,
        vertical=("WC" if sub_team == "WLN Ctr" else "TA" if sub_team == "Team A"
                  else "YD" if sub_team == "Your Dost" else "MW"),
    )
    checks = checks_dict.get(f"{case_type}_{sub_team}", [])
    return raw, case_row, checks



def _reason_for(checks) -> str:
    return "; ".join(
        f"{c.name} off by {c.off_by}" for c in checks if not c.passed
    )


def _coerce_cell(value, field: str):
    if value is None:
        return 0, None
    if isinstance(value, bool):
        return 0, f"{field}: value is missing or not a number."
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return 0, f"{field}: value is missing or not a number."
        return 0, f"{field}: value is missing or not a number."
    if isinstance(value, float):
        if value < 0:
            return 0, f"{field}: negative values aren't allowed."
        if not value.is_integer():
            return 0, f"{field}: non-integer value isn't allowed."
        return int(value), None
    if isinstance(value, int):
        if value < 0:
            return 0, f"{field}: negative values aren't allowed."
        return value, None
    return 0, f"{field}: value is missing or not a number."


def log_audit(actor, action: str, target_type: str, target_id=None, details=None) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
