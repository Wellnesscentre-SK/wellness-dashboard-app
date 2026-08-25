"""Deterministic AI-style insights engine.

Builds natural-language insights, trend series, anomaly flags and category
breakdowns from the merged wellness data. No external API required.
"""

from statistics import mean, pstdev

from wellness.models import Period

CONCERN_LABELS = {
    "anxiety": "Anxiety / Depression / Panic / OCD",
    "stress": "Acute Stress / Trauma",
    "career": "Career / Academic",
    "interpersonal": "Inter-personal",
    "self_dev": "Self Development",
    "clinical": "Clinical",
    "addiction": "Addiction",
    "medical": "Medical / Health Issues",
    "suicidal": "Suicidal Ideation / Self-harm",
}
STAKE_LABELS = {
    "ug": "UG",
    "pg": "PG",
    "phd": "PhD",
    "dual": "Dual Degree",
    "faculty": "Faculty / Staff",
    "employee_family": "Employee Family",
    "postdoc": "Postdoc / Project Associate",
    "unidentified": "Not Able to Identify",
}
REFERRAL_LABELS = {
    "self": "Self",
    "director": "Director",
    "dean": "Dean / HoD / Faculty",
    "friend": "Friend / Family",
    "mitr": "Mitr / Saathi",
}
MODE_LABELS = {"online": "Online", "in_person": "In-person", "phone": "Phone"}
GENDER_LABELS = {"male": "Male", "female": "Female", "other": "Other"}
VERTICAL_LABELS = {"WC": "Wellness Centre", "TA": "Team A", "YD": "Your Dost", "MW": "Myndwell"}

CONCERN_KEYS = tuple(CONCERN_LABELS)
STAKE_KEYS = tuple(STAKE_LABELS)
REFERRAL_KEYS = tuple(REFERRAL_LABELS)
MODE_KEYS = tuple(MODE_LABELS)
GENDER_KEYS = tuple(GENDER_LABELS)
VERTICAL_KEYS = ("WC", "TA", "YD", "MW")

CONCERN_COLORS = {
    "anxiety": "#6366f1",
    "stress": "#f59e0b",
    "career": "#10b981",
    "interpersonal": "#ef4444",
    "self_dev": "#8b5cf6",
    "clinical": "#0ea5e9",
    "addiction": "#f43f5e",
    "medical": "#14b8a6",
    "suicidal": "#64748b",
}

# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _sum_field(rows, field):
    return sum(getattr(r, field) or 0 for r in rows)


def _cat(rows, prefix, keys):
    return {k: _sum_field(rows, f"{prefix}_{k}") for k in keys}


def _secondary(period):
    metrics = list(period.secondary_metrics.all())
    total_row = next((m for m in metrics if m.vertical == "Total"), None)
    sub_rows = [m for m in metrics if m.vertical != "Total"] or metrics

    def agg(field):
        if total_row is not None:
            return getattr(total_row, field) or 0
        return sum(getattr(m, field) or 0 for m in sub_rows)

    em = getattr(period, "enquiry_modes", None)
    return {
        "total_sessions": agg("total_sessions"),
        "early_prevention_warning": agg("early_prevention_warning"),
        "no_show_turn_up": agg("no_show_turn_up"),
        "active_cases": agg("active_cases"),
        "clients_over_4_sessions": agg("clients_over_4_sessions"),
        "enquiry": {
            "mail": em.mail if em else 0,
            "calls_recd": em.calls_recd if em else 0,
            "calls_out": em.calls_out if em else 0,
        },
    }


def snapshot(period):
    """Aggregate one period into a plain, serialisable dict."""
    rows = list(period.case_rows.all())
    new_rows = [r for r in rows if r.case_type == "new"]
    fu_rows = [r for r in rows if r.case_type == "followup"]

    def total_of(rset):
        return sum(r.total_cases or 0 for r in rset)

    data = {
        "period_id": period.id,
        "report_type": period.report_type,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "label": f"{period.report_type} {period.period_start} to {period.period_end}",
        "status": period.status,
        "new": total_of(new_rows),
        "followup": total_of(fu_rows),
        "total": total_of(new_rows) + total_of(fu_rows),
        "gender": _cat(rows, "gender", GENDER_KEYS),
        "mode": _cat(rows, "mode", MODE_KEYS),
        "referral": _cat(rows, "referral", REFERRAL_KEYS),
        "concern": _cat(rows, "concern", CONCERN_KEYS),
        "stakeholder": _cat(rows, "stake", STAKE_KEYS),
        "vertical": {v: sum(r.total_cases or 0 for r in rows if r.vertical == v) for v in VERTICAL_KEYS},
    }
    data.update(_secondary(period))
    return data


def shares(data, key):
    """[(label, value, pct)] sorted desc, zero values dropped."""
    total = sum(data[key].values())
    if not total:
        return []
    items = [(label, value, round(value / total * 100, 1)) for label, value in data[key].items() if value]
    return sorted(items, key=lambda x: -x[1])


def pct_change(prev, curr):
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 1)


def _fmt_num(n):
    return f"{n:,}"


def _insight(text, tone="info"):
    return {"text": text, "tone": tone}


def _dominant(items):
    return items[0] if items else None


def _top(merged):
    total = sum(merged.values())
    if not total:
        return None
    items = sorted(merged.items(), key=lambda x: -x[1])
    label, value = items[0]
    return [label, value, round(value / total * 100, 1)]


# ---------------------------------------------------------------------------
# Per-period analysis
# ---------------------------------------------------------------------------


def _period_bullets(cur, prev):
    bullets = []

    total = cur["total"]
    if total == 0:
        return [_insight("No cases were recorded for this period.", "warning")]

    bullets.append(_insight(
        f"{_fmt_num(total)} cases were recorded in this period "
        f"({_fmt_num(cur['new'])} new, {_fmt_num(cur['followup'])} follow-up)."
    ))

    if prev is not None:
        d = cur["total"] - prev["total"]
        pct = pct_change(prev["total"], cur["total"])
        direction = "up" if d >= 0 else "down"
        tone = "positive" if d >= 0 else "negative"
        pct_txt = f" ({pct:+.1f}%)" if pct is not None else ""
        bullets.append(_insight(
            f"Total cases are {direction} {_fmt_num(abs(d))} vs the previous period{pct_txt}.",
            tone,
        ))

    if cur["total"] and prev is not None and prev["total"]:
        share = cur["total"] / (cur["total"] + prev["total"])
        if share >= 0.62:
            bullets.append(_insight(
                "This period accounts for over 60% of combined case volume with the prior period — a notable surge.",
                "warning",
            ))

    if cur["followup"] and cur["total"]:
        fu_share = round(cur["followup"] / cur["total"] * 100)
        bullets.append(_insight(
            f"Follow-up cases make up {fu_share}% of total volume, "
            f"indicating {'ongoing care for an established client base' if fu_share >= 40 else 'a caseload weighted toward new presentations'}."
        ))

    vert = _dominant(shares(cur, "vertical"))
    if vert:
        bullets.append(_insight(
            f"{VERTICAL_LABELS[vert[0]]} carries the largest case load with {_fmt_num(vert[1])} cases ({vert[2]}%).",
            "info",
        ))

    concern = _dominant(shares(cur, "concern"))
    if concern and concern[2] >= 25:
        bullets.append(_insight(
            f"{CONCERN_LABELS[concern[0]]} is the leading concern, at {concern[2]}% of reported concerns.",
            "warning",
        ))

    sessions = cur["total_sessions"]
    if sessions:
        no_show = cur["no_show_turn_up"]
        ns_rate = round(no_show / sessions * 100) if sessions else 0
        if no_show and ns_rate >= 20:
            bullets.append(_insight(
                f"No-shows are elevated: {_fmt_num(no_show)} of {_fmt_num(sessions)} sessions ({ns_rate}%) did not turn up.",
                "warning",
            ))
        elif sessions:
            bullets.append(_insight(
                f"{_fmt_num(sessions)} sessions were delivered in this period."
            ))

        over4 = cur["clients_over_4_sessions"]
        if over4 and sessions:
            bullets.append(_insight(
                f"{_fmt_num(over4)} clients are in longer-term care (more than 4 sessions)."
            ))

    if cur["early_prevention_warning"]:
        bullets.append(_insight(
            f"{_fmt_num(cur['early_prevention_warning'])} early-prevention warnings were flagged.",
            "warning",
        ))

    if prev is not None:
        movers = []
        for group, labels in [
            ("concern", CONCERN_LABELS),
            ("stakeholder", STAKE_LABELS),
            ("referral", REFERRAL_LABELS),
            ("mode", MODE_LABELS),
            ("gender", GENDER_LABELS),
        ]:
            for key, label in labels.items():
                d = cur[group].get(key, 0) - prev[group].get(key, 0)
                if d:
                    movers.append((label, d, abs(d)))
        movers.sort(key=lambda x: -x[2])
        if movers:
            label, d, _ = movers[0]
            bullets.append(_insight(
                f"The largest category shift was in {label.lower()} "
                f"({'up' if d > 0 else 'down'} {_fmt_num(abs(d))} cases)."
            ))

    return bullets[:8]


def analyze_period(period, previous=None):
    cur = snapshot(period)
    prev = snapshot(previous) if previous is not None else None

    comparison = None
    if prev is not None:
        comparison = {
            "previous_id": prev["period_id"],
            "previous_label": prev["label"],
            "delta_total": cur["total"] - prev["total"],
            "pct_total": pct_change(prev["total"], cur["total"]),
            "delta_new": cur["new"] - prev["new"],
            "delta_followup": cur["followup"] - prev["followup"],
            "delta_sessions": cur["total_sessions"] - prev["total_sessions"],
        }

    return {
        "period": {
            "id": period.id,
            "report_type": period.report_type,
            "period_start": period.period_start.isoformat(),
            "period_end": period.period_end.isoformat(),
            "label": cur["label"],
            "status": period.status,
            "source": period.source,
        },
        "totals": {
            "new": cur["new"],
            "followup": cur["followup"],
            "total": cur["total"],
        },
        "secondary": {
            "total_sessions": cur["total_sessions"],
            "early_prevention_warning": cur["early_prevention_warning"],
            "no_show_turn_up": cur["no_show_turn_up"],
            "active_cases": cur["active_cases"],
            "clients_over_4_sessions": cur["clients_over_4_sessions"],
            "enquiry": cur["enquiry"],
        },
        "comparison": comparison,
        "shares": {
            "gender": shares(cur, "gender"),
            "mode": shares(cur, "mode"),
            "referral": shares(cur, "referral"),
            "concern": shares(cur, "concern"),
            "stakeholder": shares(cur, "stakeholder"),
            "vertical": shares(cur, "vertical"),
        },
        "top": {
            "concern": _dominant(shares(cur, "concern")),
            "stakeholder": _dominant(shares(cur, "stakeholder")),
            "referral": _dominant(shares(cur, "referral")),
            "vertical": _dominant(shares(cur, "vertical")),
        },
        "insights": _period_bullets(cur, prev),
    }


# ---------------------------------------------------------------------------
# Cross-period analysis
# ---------------------------------------------------------------------------


def _overall_bullets(snaps, anomalies, aggregates):
    bullets = []
    if not snaps:
        return bullets

    total_all = sum(s["total"] for s in snaps)
    new_all = sum(s["new"] for s in snaps)
    fu_all = sum(s["followup"] for s in snaps)
    avg = round(mean([s["total"] for s in snaps]), 1)

    bullets.append(_insight(
        f"Across {len(snaps)} reporting periods, {_fmt_num(total_all)} cases were handled "
        f"({_fmt_num(new_all)} new, {_fmt_num(fu_all)} follow-up), averaging {_fmt_num(int(avg))} per period."
    ))

    trend = [s["total"] for s in snaps]
    if len(trend) >= 2 and trend[-1] > trend[0]:
        pct = pct_change(trend[0], trend[-1])
        bullets.append(_insight(
            f"Case volume has grown {pct:+.1f}% from the first period to the latest.",
            "positive",
        ))
    elif len(trend) >= 2 and trend[-1] < trend[0]:
        pct = pct_change(trend[0], trend[-1])
        bullets.append(_insight(
            f"Case volume has declined {pct:+.1f}% from the first period to the latest.",
            "negative",
        ))

    fu_total_share = round(fu_all / total_all * 100) if total_all else 0
    if total_all:
        bullets.append(_insight(
            f"Follow-up cases represent {fu_total_share}% of all case volume over the period covered."
        ))

    agg_concern = _top(aggregates["concern"])
    if agg_concern:
        label, value, pct = agg_concern
        bullets.append(_insight(
            f"{CONCERN_LABELS[label]} is the most frequent concern overall, "
            f"{_fmt_num(value)} mentions ({pct}% of the concern total).",
            "warning",
        ))

    agg_vert = _top(aggregates["vertical"])
    if agg_vert:
        label, value, pct = agg_vert
        bullets.append(_insight(
            f"{VERTICAL_LABELS[label]} is the dominant service vertical with {_fmt_num(value)} cases ({pct}%)."
        ))

    sessions_all = sum(s["total_sessions"] for s in snaps)
    no_show_all = sum(s["no_show_turn_up"] for s in snaps)
    if sessions_all:
        ns_rate = round(no_show_all / sessions_all * 100)
        if no_show_all and ns_rate >= 20:
            bullets.append(_insight(
                f"Overall no-show rate is elevated at {ns_rate}% ({_fmt_num(no_show_all)} of {_fmt_num(sessions_all)} sessions).",
                "warning",
            ))

    for a in anomalies[:3]:
        label = a["label"]
        d = a["deviation"]
        tone = "warning" if a["kind"] == "spike" else "negative"
        bullets.append(_insight(
            f"{label} is an outlier: {'spike' if a['kind'] == 'spike' else 'dip'} of {_fmt_num(abs(d))} cases vs the period average.",
            tone,
        ))

    return bullets[:10]


def _detect_anomalies(snaps):
    totals = [s["total"] for s in snaps]
    if len(totals) < 3:
        return []
    m = mean(totals)
    try:
        sd = pstdev(totals)
    except Exception:
        sd = 0
    threshold = max(1.2 * sd, 0.4 * m) if m else 0
    anomalies = []
    for s in snaps:
        if not threshold:
            continue
        dev = s["total"] - m
        if abs(dev) >= threshold and s["total"] > 0:
            anomalies.append({
                "period_id": s["period_id"],
                "label": s["label"],
                "total": s["total"],
                "average": round(m, 1),
                "deviation": int(dev),
                "kind": "spike" if dev > 0 else "dip",
            })
    return sorted(anomalies, key=lambda x: -abs(x["deviation"]))


def analyze_all(periods):
    snaps = [snapshot(p) for p in periods]
    snaps.sort(key=lambda s: s["period_start"])
    if not snaps:
        return {"summary": None, "trend": [], "anomalies": [], "insights": []}

    totals = [s["total"] for s in snaps]
    sessions = [s["total_sessions"] for s in snaps]
    avg_total = round(mean(totals), 1)
    avg_new = round(mean(s["new"] for s in snaps), 1)
    avg_fu = round(mean(s["followup"] for s in snaps), 1)
    avg_sessions = round(mean(sessions), 1) if sessions else 0

    best = max(snaps, key=lambda s: s["total"])
    worst = min(snaps, key=lambda s: s["total"])

    def _agg(group):
        merged = {}
        for s in snaps:
            for key, value in s[group].items():
                merged[key] = merged.get(key, 0) + value
        return merged

    aggregates = {
        "gender": _agg("gender"),
        "mode": _agg("mode"),
        "referral": _agg("referral"),
        "concern": _agg("concern"),
        "stakeholder": _agg("stakeholder"),
        "vertical": _agg("vertical"),
    }

    anomalies = _detect_anomalies(snaps)

    return {
        "summary": {
            "period_count": len(snaps),
            "total_cases": sum(totals),
            "total_new": sum(s["new"] for s in snaps),
            "total_followup": sum(s["followup"] for s in snaps),
            "total_sessions": sum(sessions),
            "avg_total": avg_total,
            "avg_new": avg_new,
            "avg_followup": avg_fu,
            "avg_sessions": avg_sessions,
            "best_period": {"label": best["label"], "total": best["total"], "id": best["period_id"]},
            "worst_period": {"label": worst["label"], "total": worst["total"], "id": worst["period_id"]},
        },
        "trend": [
            {
                "period_id": s["period_id"],
                "label": s["label"],
                "short_label": f"{s['period_start']}",
                "period_start": s["period_start"],
                "total": s["total"],
                "new": s["new"],
                "followup": s["followup"],
                "total_sessions": s["total_sessions"],
            }
            for s in snaps
        ],
        "anomalies": anomalies,
        "aggregates": {
            "gender": shares(aggregates, "gender"),
            "mode": shares(aggregates, "mode"),
            "referral": shares(aggregates, "referral"),
            "concern": shares(aggregates, "concern"),
            "stakeholder": shares(aggregates, "stakeholder"),
            "vertical": shares(aggregates, "vertical"),
        },
        "top": {
            "concern": _top(aggregates["concern"]),
            "stakeholder": _top(aggregates["stakeholder"]),
            "referral": _top(aggregates["referral"]),
            "vertical": _top(aggregates["vertical"]),
        },
        "insights": _overall_bullets(snaps, anomalies, aggregates),
    }


def active_periods():
    return list(Period.objects.filter(superseded_by__isnull=True).order_by("period_start"))


# ---------------------------------------------------------------------------
# Period-over-period comparison (week / month / year)
# ---------------------------------------------------------------------------

COMPARISON_TYPES = {
    "week": "Week-over-Week",
    "month": "Month-over-Month",
    "year": "Year-over-Year",
}


def _period_meta(period, snap):
    return {
        "id": period.id,
        "report_type": period.report_type,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "label": snap["label"],
        "new": snap["new"],
        "followup": snap["followup"],
        "total": snap["total"],
        "total_sessions": snap["total_sessions"],
    }


def _compare_bullets(a, b, totals, movers, type_label):
    bullets = []

    if a["total"] == 0 and b["total"] == 0:
        return [_insight("No cases were recorded in either period.", "warning")]

    d = totals["delta_total"]
    pct = totals["pct_total"]
    direction = "rose" if d >= 0 else "fell"
    pct_txt = f" ({pct:+.1f}%)" if pct is not None else ""
    bullets.append(_insight(
        f"{type_label}, total cases {direction} by {_fmt_num(abs(d))} — "
        f"from {_fmt_num(a['total'])} to {_fmt_num(b['total'])}{pct_txt}.",
        "positive" if d >= 0 else "negative",
    ))

    if totals["delta_new"]:
        bullets.append(_insight(
            f"New cases moved {'up' if totals['delta_new'] > 0 else 'down'} "
            f"{_fmt_num(abs(totals['delta_new']))} ({_fmt_num(a['new'])} → {_fmt_num(b['new'])}).",
            "positive" if totals["delta_new"] > 0 else "negative",
        ))
    if totals["delta_followup"]:
        bullets.append(_insight(
            f"Follow-up cases moved {'up' if totals['delta_followup'] > 0 else 'down'} "
            f"{_fmt_num(abs(totals['delta_followup']))} ({_fmt_num(a['followup'])} → {_fmt_num(b['followup'])}).",
            "positive" if totals["delta_followup"] > 0 else "negative",
        ))
    if totals["delta_sessions"]:
        bullets.append(_insight(
            f"Sessions delivered {'increased' if totals['delta_sessions'] > 0 else 'decreased'} by "
            f"{_fmt_num(abs(totals['delta_sessions']))} "
            f"({_fmt_num(a['total_sessions'])} → {_fmt_num(b['total_sessions'])})."
        ))
    if pct is not None and abs(pct) >= 20:
        bullets.append(_insight(
            f"This is a {'sharp increase' if pct > 0 else 'sharp decline'} of {abs(pct):.1f}% between the two periods.",
            "warning",
        ))

    if movers:
        m = movers[0]
        bullets.append(_insight(
            f"The largest category shift was {m['label']}: {_fmt_num(m['a'])} → {_fmt_num(m['b'])} "
            f"({'up' if m['delta'] > 0 else 'down'} {_fmt_num(abs(m['delta']))}).",
            "warning" if abs(m["delta"]) >= 10 else "info",
        ))

    return bullets[:8]


def compare_periods(period_a, period_b, comparison_type="week"):
    """AI narrative comparison between two periods of the same reporting cadence.

    ``period_a`` is treated as the earlier/baseline period and ``period_b`` as
    the later/current one; arguments are sorted by date automatically.
    """
    if period_a.period_start > period_b.period_start:
        period_a, period_b = period_b, period_a
    a = snapshot(period_a)
    b = snapshot(period_b)
    type_label = COMPARISON_TYPES.get(comparison_type, "Period-over-Period")

    def _delta(cur, prev, key):
        return cur.get(key, 0) - prev.get(key, 0)

    totals = {
        "delta_total": _delta(b, a, "total"),
        "pct_total": pct_change(a["total"], b["total"]),
        "delta_new": _delta(b, a, "new"),
        "pct_new": pct_change(a["new"], b["new"]),
        "delta_followup": _delta(b, a, "followup"),
        "pct_followup": pct_change(a["followup"], b["followup"]),
        "delta_sessions": _delta(b, a, "total_sessions"),
        "pct_sessions": pct_change(a["total_sessions"], b["total_sessions"]),
        "active_a": a.get("active_cases", 0),
        "active_b": b.get("active_cases", 0),
        "pct_active": pct_change(a.get("active_cases", 0), b.get("active_cases", 0)),
        "delta_active": _delta(b, a, "active_cases"),
    }

    category_deltas = {}
    movers = []
    for group, labels in [
        ("gender", GENDER_LABELS),
        ("mode", MODE_LABELS),
        ("referral", REFERRAL_LABELS),
        ("concern", CONCERN_LABELS),
        ("stakeholder", STAKE_LABELS),
        ("vertical", VERTICAL_LABELS),
    ]:
        entries = []
        for key, label in labels.items():
            av = a[group].get(key, 0)
            bv = b[group].get(key, 0)
            d = bv - av
            entries.append({
                "key": key,
                "label": label,
                "a": av,
                "b": bv,
                "delta": d,
                "pct": pct_change(av, bv),
            })
            if d:
                movers.append({
                    "category": group,
                    "label": label,
                    "a": av,
                    "b": bv,
                    "delta": d,
                })
        category_deltas[group] = entries
    movers.sort(key=lambda x: -abs(x["delta"]))

    return {
        "comparison_type": comparison_type,
        "comparison_label": type_label,
        "period_a": _period_meta(period_a, a),
        "period_b": _period_meta(period_b, b),
        "totals": totals,
        "movers": movers[:12],
        "category_deltas": category_deltas,
        "insights": _compare_bullets(a, b, totals, movers, type_label),
    }
