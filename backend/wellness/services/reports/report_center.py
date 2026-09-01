"""Report Center engine — separate Weekly / Monthly / Yearly report modules.

Weekly  : one weekly period (auto-detected entries).
Monthly : ALL weekly data of a calendar month (1st .. last day, 28/29/30/31)
          combined into a single monthly report.
Yearly  : ALL monthly data of a calendar year (Jan 1 .. Dec 31) combined into
          a single annual analysis.

Everything is computed on demand from the stored periods, so Monthly and
Yearly reports automatically reflect newly added Weekly data — no stale
copies, no duplicate data.
"""

from __future__ import annotations

import calendar
from datetime import date

from wellness.models import Period
from wellness.services.reports import reference_ppt


# ═══════════════════════════════════════════════════════════════════════════════
# PERIOD LOOKUPS (auto-detection)
# ═══════════════════════════════════════════════════════════════════════════════

def _active():
    return Period.objects.filter(superseded_by__isnull=True)


def weeks_in_month(year: int, month: int):
    """Weekly periods that overlap the given calendar month."""
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    return sorted(
        [p for p in _active().filter(report_type=Period.ReportType.WEEKLY)
         if p.period_start <= month_end and p.period_end >= month_start],
        key=lambda p: p.period_start,
    )


def months_in_year(year: int):
    """Monthly periods inside the calendar year Jan 1 .. Dec 31."""
    return list(
        _active().filter(
            report_type=Period.ReportType.MONTHLY,
            period_start__year=year,
        ).order_by("period_start")
    )


def weeklies_by_year():
    return list(
        _active().filter(report_type=Period.ReportType.WEEKLY).order_by("period_start")
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DICT MERGING (weekly -> monthly, monthly -> yearly)
# ═══════════════════════════════════════════════════════════════════════════════

_RAW_VERTS = ("WC", "TA", "YD", "MW")


def merge_period_dicts(dicts: list, label: str = "") -> dict:
    """Combine several period dicts (ppt_generator format) into one aggregate.
    Vertical keys stay raw (WC/TA/YD/MW) so downstream combine_verticals works."""
    agg = {
        "label": label,
        "new": 0, "followup": 0, "grand": 0,
        "gender": {}, "mode": {}, "referral": {},
        "concern": {}, "stakeholder": {},
        "vertical": {v: {"new": 0, "followup": 0, "total": 0} for v in _RAW_VERTS},
        "by_vertical": {},
    }
    starts, ends = [], []
    for d in dicts:
        agg["new"] += int(d.get("new", 0) or 0)
        agg["followup"] += int(d.get("followup", 0) or 0)
        agg["grand"] += int(d.get("grand", 0) or 0)
        for dim in ("gender", "mode", "referral", "concern", "stakeholder"):
            for k, v in (d.get(dim) or {}).items():
                agg[dim][k] = agg[dim].get(k, 0) + int(v or 0)
        raw = d.get("vertical") or {}
        for v in _RAW_VERTS:
            src = raw.get(v) or {}
            tgt = agg["vertical"][v]
            for sub in ("new", "followup", "total"):
                tgt[sub] += int(src.get(sub, 0) or 0)
        for src_key, dims in (d.get("by_vertical") or {}).items():
            tgt_dims = agg["by_vertical"].setdefault(src_key, {})
            for dim, cats in dims.items():
                t = tgt_dims.setdefault(dim, {})
                for k, v in cats.items():
                    t[k] = t.get(k, 0) + int(v or 0)
        if d.get("start"):
            starts.append(str(d["start"])[:10])
        if d.get("end"):
            ends.append(str(d["end"])[:10])
    if starts:
        agg["start"] = min(starts)
    if ends:
        agg["end"] = max(ends)
    return agg


def combined_month_dict(year: int, month: int) -> tuple[dict, list]:
    """Merge every weekly report of the month into one monthly dict.
    Falls back to the stored MONTHLY period when no weeklies exist."""
    weeks = weeks_in_month(year, month)
    if weeks:
        dicts = [reference_ppt._period_to_dict(p) for p in weeks]
        label = f"{calendar.month_name[month]} {year} (combined from {len(weeks)} weekly reports)"
        return merge_period_dicts(dicts, label), weeks
    stored = months_in_year(year)
    exact = [p for p in stored if p.period_start.month == month]
    if exact:
        return reference_ppt._period_to_dict(exact[0]), exact
    raise ValueError(f"No weekly or monthly data found for {calendar.month_name[month]} {year}.")


def combined_year_dicts(year: int) -> tuple[list, list]:
    """Return one dict per month of the year (Jan..Dec order).
    Prefers stored MONTHLY periods; synthesises pseudo-months by combining
    that month's weekly reports whenever a monthly period is missing."""
    result, sources = [], []

    def _rank(p):
        has_data = any(
            (r.gender_male or 0) + (r.gender_female or 0) + (r.gender_other or 0)
            for r in p.case_rows.all()
        ) or any(r.total_cases for r in p.case_rows.all())
        return (has_data, p.period_start)

    stored: dict[int, Period] = {}
    for p in sorted(months_in_year(year), key=_rank):
        stored[p.period_start.month] = p
    all_weeks = weeklies_by_year()
    for month in range(1, 13):
        if month in stored:
            result.append(reference_ppt._period_to_dict(stored[month]))
            sources.append(stored[month])
            continue
        weeks = [p for p in all_weeks
                 if p.period_start <= date(year, month, calendar.monthrange(year, month)[1])
                 and p.period_end >= date(year, month, 1)]
        if not weeks:
            continue
        dicts = [reference_ppt._period_to_dict(p) for p in weeks]
        merged = merge_period_dicts(
            dicts, f"{calendar.month_abbr[month]} {year}")
        merged["start"] = f"{year:04d}-{month:02d}-01"
        merged["end"] = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
        result.append(merged)
        sources.extend(weeks)
    if not result:
        raise ValueError(f"No monthly or weekly data found for {year}.")
    return result, sources


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONS PAYLOAD (drives the frontend filters)
# ═══════════════════════════════════════════════════════════════════════════════

def options() -> dict:
    weeks = weeklies_by_year()
    monthlies = {}
    for p in _active().filter(report_type=Period.ReportType.MONTHLY):
        monthlies.setdefault(p.period_start.year, set()).add(p.period_start.month)

    years = sorted({p.period_start.year for p in weeks}
                   | set(monthlies.keys()), reverse=True)

    months_payload = {}
    for y in years:
        entries = []
        for m in range(1, 13):
            wk = [p for p in weeks
                  if p.period_start <= date(y, m, calendar.monthrange(y, m)[1])
                  and p.period_end >= date(y, m, 1)]
            if not wk and m not in monthlies.get(y, set()):
                continue
            entries.append({
                "month": m,
                "label": calendar.month_name[m],
                "week_count": len(wk),
                "week_ids": [p.id for p in wk],
                "has_monthly_period": m in monthlies.get(y, set()),
            })
        months_payload[str(y)] = entries

    return {
        "years": years,
        "weekly": [{
            "id": p.id,
            "label": str(p.title or f"{p.period_start} to {p.period_end}"),
            "start": str(p.period_start),
            "end": str(p.period_end),
        } for p in weeks],
        "months": months_payload,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

_PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_single(report_type: str, fmt: str,
                 period_id: int = None, year: int = None, month: int = None):
    """Generate one report. Returns (filename, bytes, content_type, source_ids)."""
    if report_type == "weekly":
        period = _active().filter(pk=period_id,
                                  report_type=Period.ReportType.WEEKLY).first()
        if period is None:
            raise ValueError("Weekly period not found.")
        if fmt == "xlsx":
            from wellness.services.reports import exports
            data = exports.build_excel(period)
            return f"weekly_{period.period_start}_{period.period_end}.xlsx", data, _XLSX_TYPE, [period.id]
        data = reference_ppt.build_normal_week(period)
        return f"weekly_{period.period_start}_{period.period_end}.pptx", data, _PPTX_TYPE, [period.id]

    if report_type == "monthly":
        if not year or not month:
            raise ValueError("year and month are required for the monthly report.")
        merged, sources = combined_month_dict(int(year), int(month))
        if fmt == "xlsx":
            from wellness.services.reports import exports
            data = exports.build_aggregate_excel(
                f"Monthly Wellness Report - {calendar.month_name[int(month)]} {year}",
                merged["label"], merged, _source_rows(sources))
            return f"monthly_{year}_{int(month):02d}_combined.xlsx", data, _XLSX_TYPE, [p.id for p in sources]
        data = reference_ppt.build_normal_monthly(merged)
        return f"monthly_{year}_{int(month):02d}_combined.pptx", data, _PPTX_TYPE, [p.id for p in sources]

    if report_type == "yearly":
        if not year:
            raise ValueError("year is required for the yearly report.")
        month_dicts, sources = combined_year_dicts(int(year))
        merged_all = merge_period_dicts(month_dicts, f"{year} Data Analysis")
        if fmt == "xlsx":
            from wellness.services.reports import exports
            data = exports.build_aggregate_excel(
                f"Yearly Wellness Report - {year} Data Analysis",
                f"January 1 to December 31, {year}", merged_all,
                _month_rows(month_dicts))
            return f"annual_{year}_data_analysis.xlsx", data, _XLSX_TYPE, [p.id for p in sources]
        data = reference_ppt.build_normal_yearly(month_dicts)
        return f"annual_{year}_data_analysis.pptx", data, _PPTX_TYPE, [p.id for p in sources]

    raise ValueError("report_type must be 'weekly', 'monthly' or 'yearly'.")


def _source_rows(periods):
    rows = []
    for p in periods:
        d = reference_ppt._period_to_dict(p)
        rows.append({"label": f"{p.period_start} .. {p.period_end}",
                     "new": d["new"], "followup": d["followup"], "total": d["grand"]})
    return rows


def _month_rows(month_dicts):
    return [{"label": d.get("label"), "new": d["new"],
             "followup": d["followup"], "total": d["grand"]}
            for d in month_dicts]


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARISON (week-to-week / month-to-month / year-to-year)
# ═══════════════════════════════════════════════════════════════════════════════

def build_compare(compare_type: str, fmt: str,
                  from_id=None, to_id=None,
                  from_ym=None, to_ym=None,
                  from_year=None, to_year=None):
    """Compare two periods. Returns (filename, bytes, content_type)."""
    if compare_type == "week":
        a = _active().filter(pk=from_id, report_type=Period.ReportType.WEEKLY).first()
        b = _active().filter(pk=to_id, report_type=Period.ReportType.WEEKLY).first()
        if a is None or b is None:
            raise ValueError("Two existing weekly reports are required.")
        data = reference_ppt.build_weekly_comparison(a, b)
        return f"compare_week_{a.period_start}_{b.period_end}.pptx", data, _PPTX_TYPE

    if compare_type == "month":
        ya, ma = _parse_ym(from_ym)
        yb, mb = _parse_ym(to_ym)
        da, _ = combined_month_dict(ya, ma)
        db, _ = combined_month_dict(yb, mb)
        data = reference_ppt.build_monthly_comparison(da, db)
        return f"compare_month_{ya}_{ma:02d}_vs_{yb}_{mb:02d}.pptx", data, _PPTX_TYPE

    if compare_type == "year":
        if not from_year or not to_year:
            raise ValueError("Two years are required.")
        da, _ = combined_year_dicts(int(from_year))
        db, _ = combined_year_dicts(int(to_year))
        lbl_a = str(from_year) if from_year != to_year else f"{from_year} (Baseline)"
        lbl_b = str(to_year) if from_year != to_year else f"{to_year} (Current)"
        data = reference_ppt.build_yearly(da, db, lbl_a, lbl_b)
        return f"compare_year_{from_year}_vs_{to_year}.pptx", data, _PPTX_TYPE

    raise ValueError("compare type must be 'week', 'month' or 'year'.")


def _parse_ym(value):
    try:
        y, m = str(value).split("-")
        return int(y), int(m)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Month must be in 'YYYY-MM' format.")
