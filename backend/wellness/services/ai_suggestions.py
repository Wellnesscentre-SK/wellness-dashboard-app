"""AI-powered report analysis and improvement suggestion engine.

Analyses wellness centre data and produces evidence-based, actionable
recommendations organised by category and priority.  No external API
is required — all analysis is deterministic and data-driven.
"""

from statistics import mean
from wellness.services.insights import snapshot, pct_change, shares, _fmt_num, active_periods


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = {
    "performance": "Performance Improvement",
    "engagement": "Client Engagement",
    "operational": "Operational Improvement",
    "team": "Team Development",
    "development": "Wellness Centre Development",
    "reporting": "Reporting & Data Quality",
    "opportunities": "Future Opportunities",
}

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"


def _suggestion(title, category, priority, why, evidence, action, benefit,
                timeline, metric, confidence="Medium"):
    return {
        "title": title,
        "category": category,
        "category_label": CATEGORIES.get(category, category),
        "priority": priority,
        "why": why,
        "evidence": evidence,
        "action": action,
        "benefit": benefit,
        "timeline": timeline,
        "success_metric": metric,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _delta(a, b):
    return b - a


def _pct(a, b):
    return pct_change(a, b)


def _max_change(cur, prev, labels_dict):
    """Return (label, delta, abs_delta) for the category with the biggest shift."""
    best = None
    for key, label in labels_dict.items():
        d = cur.get(key, 0) - prev.get(key, 0)
        if best is None or abs(d) > abs(best[2]):
            best = (label, d, abs(d))
    return best


def _concern_labels():
    return {
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


def _stake_labels():
    return {
        "ug": "UG", "pg": "PG", "phd": "PhD", "dual": "Dual Degree",
        "faculty": "Faculty / Staff", "employee_family": "Employee Family",
        "postdoc": "Postdoc / Project Associate",
        "unidentified": "Not Able to Identify",
    }


def _vert_labels():
    return {"WC": "Wellness Centre", "TA": "Team A", "YD": "Your Dost", "MW": "Myndwell"}


CONCERN_LABELS_MAP = _concern_labels()
STAKE_LABELS_MAP = _stake_labels()
VERT_LABELS_MAP = _vert_labels()


# ---------------------------------------------------------------------------
# Weekly suggestions
# ---------------------------------------------------------------------------

def generate_weekly_suggestions(cur_snap, prev_snap=None):
    """Generate suggestions for a single weekly period."""
    suggestions = []
    total = cur_snap["total"]

    if total == 0:
        return {
            "summary": "No cases were recorded for this period. Data entry may be incomplete.",
            "suggestions": [_suggestion(
                "Investigate Missing Data", "reporting", PRIORITY_HIGH,
                "No cases were recorded for this period.",
                "Period total = 0.",
                "Verify that data has been entered or uploaded for this period.",
                "Ensure accurate reporting and avoid data gaps.",
                "Immediate", "Period status changes from 0 to non-zero", "High",
            )],
            "kpi": {"total_suggestions": 1, "high": 1, "medium": 0, "low": 0, "opportunities": 0},
        }

    # --- Performance suggestions ---
    if prev_snap:
        pct_total = _pct(prev_snap["total"], total)
        if pct_total is not None and pct_total < -10:
            suggestions.append(_suggestion(
                "Investigate Decline in Total Cases",
                "performance", PRIORITY_HIGH,
                f"Total cases declined by {abs(pct_total):.1f}% compared to the previous period.",
                f"Previous: {_fmt_num(prev_snap['total'])} | Current: {_fmt_num(total)} | Change: {pct_total:+.1f}%",
                "Conduct a root-cause analysis: check for holiday effects, staffing issues, or data-entry gaps. Review follow-up scheduling to ensure continuity of care.",
                "Restore case volume to previous levels and maintain consistent client engagement.",
                "Within 1 week", "Total cases return to within 5% of previous period", "High",
            ))
        elif pct_total is not None and pct_total > 15:
            suggestions.append(_suggestion(
                "Manage Increased Case Load",
                "performance", PRIORITY_MEDIUM,
                f"Total cases increased by {pct_total:.1f}%, indicating higher demand.",
                f"Previous: {_fmt_num(prev_snap['total'])} | Current: {_fmt_num(total)} | Change: {pct_total:+.1f}%",
                "Review counsellor capacity and consider redistributing workload. Prioritise triage for new cases.",
                "Prevent burnout and maintain service quality during high-demand periods.",
                "Within 1 week", "Counsellor workload remains balanced", "High",
            ))

        pct_fu = _pct(prev_snap["followup"], cur_snap["followup"])
        if pct_fu is not None and pct_fu < -15:
            suggestions.append(_suggestion(
                "Improve Follow-Up Completion Rate",
                "operational", PRIORITY_HIGH,
                f"Follow-up cases dropped {abs(pct_fu):.1f}%, suggesting missed or delayed follow-ups.",
                f"Previous follow-ups: {_fmt_num(prev_snap['followup'])} | Current: {_fmt_num(cur_snap['followup'])}",
                "Implement a daily follow-up review dashboard. Assign a team member to contact clients with overdue follow-ups.",
                "Improved client retention and continuity of care.",
                "Within 1 week", "Follow-up rate returns to within 5% of previous period", "High",
            ))

    # --- Concern analysis ---
    concern_shares = shares(cur_snap, "concern")
    if concern_shares:
        top_concern = concern_shares[0]
        if top_concern[2] >= 30:
            suggestions.append(_suggestion(
                f"Address High Volume of {CONCERN_LABELS_MAP.get(top_concern[0], top_concern[0])} Cases",
                "engagement", PRIORITY_MEDIUM,
                f"{CONCERN_LABELS_MAP.get(top_concern[0], top_concern[0])} accounts for {top_concern[2]}% of all concerns.",
                f"Cases: {_fmt_num(top_concern[1])} out of {_fmt_num(total)} total ({top_concern[2]}%).",
                f"Develop targeted interventions for {CONCERN_LABELS_MAP.get(top_concern[0], top_concern[0]).lower()} concerns. Consider specialised counselling workshops.",
                "Better-targeted support for the most common client need.",
                "1-2 weeks", "Reduced proportion of top concern through early intervention", "Medium",
            ))

    # --- Secondary metrics ---
    sessions = cur_snap.get("total_sessions", 0)
    no_show = cur_snap.get("no_show_turn_up", 0)
    if sessions and no_show:
        ns_rate = round(no_show / sessions * 100)
        if ns_rate >= 20:
            suggestions.append(_suggestion(
                "Reduce No-Show Rate",
                "operational", PRIORITY_HIGH,
                f"No-show rate is {ns_rate}% ({_fmt_num(no_show)} of {_fmt_num(sessions)} sessions).",
                f"No-shows: {_fmt_num(no_show)} | Sessions: {_fmt_num(sessions)} | Rate: {ns_rate}%",
                "Introduce reminder calls/SMS 24 hours before appointments. Implement a waitlist system to fill cancelled slots.",
                "Increase effective session delivery and reduce wasted counsellor time.",
                "Within 1 week", "No-show rate drops below 15%", "High",
            ))

    early = cur_snap.get("early_prevention_warning", 0)
    if early and early >= 5:
        suggestions.append(_suggestion(
            "Review Early-Prevention Warnings",
            "engagement", PRIORITY_MEDIUM,
            f"{_fmt_num(early)} early-prevention warnings were flagged this period.",
            f"Warnings: {_fmt_num(early)} | Total sessions: {_fmt_num(sessions)}",
            "Establish a triage protocol for early-prevention cases. Ensure timely outreach to flagged individuals.",
            "Proactive intervention before cases escalate.",
            "Within 1 week", "All early-prevention warnings addressed within 48 hours", "Medium",
        ))

    # --- Vertical imbalance ---
    vert_data = cur_snap.get("vertical", {})
    if vert_data:
        total_v = sum(vert_data.values())
        if total_v:
            for v_key, v_total in vert_data.items():
                if v_total and v_total / total_v >= 0.60:
                    suggestions.append(_suggestion(
                        f"Balance Workload Across Verticals",
                        "team", PRIORITY_MEDIUM,
                        f"{VERT_LABELS_MAP.get(v_key, v_key)} carries {round(v_total / total_v * 100)}% of all cases.",
                        f"{VERT_LABELS_MAP.get(v_key, v_key)}: {_fmt_num(v_total)} of {_fmt_num(total_v)} total cases.",
                        "Review resource allocation across verticals. Consider cross-training counsellors to handle multiple verticals.",
                        "More balanced workload distribution and reduced risk of bottleneck in one vertical.",
                        "2-4 weeks", "No single vertical exceeds 50% of total cases", "Medium",
                    ))
                    break

    # --- Positive observations (opportunities) ---
    if prev_snap:
        for key, label in CONCERN_LABELS_MAP.items():
            prev_val = prev_snap.get("concern", {}).get(key, 0)
            cur_val = cur_snap.get("concern", {}).get(key, 0)
            if prev_val and cur_val:
                pct = _pct(prev_val, cur_val)
                if pct is not None and pct < -20:
                    suggestions.append(_suggestion(
                        f"Continue Focus on {label} Reduction",
                        "opportunities", PRIORITY_LOW,
                        f"{label} cases decreased by {abs(pct):.1f}%, showing positive improvement.",
                        f"Previous: {_fmt_num(prev_val)} | Current: {_fmt_num(cur_val)} | Change: {pct:+.1f}%",
                        "Document the strategies that led to this improvement and share best practices across the team.",
                        "Sustain and replicate successful interventions.",
                        "Ongoing", "Maintain downward trend in subsequent periods", "Low",
                    ))
                    break

    # --- Fallback if no suggestions generated ---
    if not suggestions:
        suggestions.append(_suggestion(
            "Maintain Current Performance",
            "opportunities", PRIORITY_LOW,
            "Performance metrics are within normal ranges with no significant issues detected.",
            f"Total cases: {_fmt_num(total)} | Follow-ups: {_fmt_num(cur_snap.get('followup', 0))}",
            "Continue monitoring key metrics. Review data quality and completeness for the next period.",
            "Sustain current performance levels.",
            "Ongoing", "Stable metrics in next period", "Low",
        ))

    high = sum(1 for s in suggestions if s["priority"] == PRIORITY_HIGH)
    med = sum(1 for s in suggestions if s["priority"] == PRIORITY_MEDIUM)
    low = sum(1 for s in suggestions if s["priority"] == PRIORITY_LOW)
    opps = sum(1 for s in suggestions if s["category"] == "opportunities")

    summary_parts = []
    if total:
        summary_parts.append(f"Total cases: {_fmt_num(total)}")
    if prev_snap:
        pct = _pct(prev_snap["total"], total)
        if pct is not None:
            summary_parts.append(f"{'up' if pct >= 0 else 'down'} {abs(pct):.1f}% vs previous period")
    summary = "; ".join(summary_parts) + "." if summary_parts else "Period analysed."

    return {
        "summary": summary,
        "suggestions": sorted(suggestions, key=lambda s: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[s["priority"]])),
        "kpi": {
            "total_suggestions": len(suggestions),
            "high": high,
            "medium": med,
            "low": low,
            "opportunities": opps,
        },
    }


# ---------------------------------------------------------------------------
# Monthly suggestions (aggregates weekly snapshots)
# ---------------------------------------------------------------------------

def generate_monthly_suggestions(weekly_snaps):
    """Generate suggestions from a list of weekly snapshots within a month."""
    if not weekly_snaps:
        return {"summary": "No weekly data available for this month.", "suggestions": [], "kpi": _zero_kpi()}

    totals = [s["total"] for s in weekly_snaps]
    avg_total = round(mean(totals), 1)
    best_week = max(weekly_snaps, key=lambda s: s["total"])
    worst_week = min(weekly_snaps, key=lambda s: s["total"])
    month_total = sum(totals)

    suggestions = []

    # Trend analysis
    if len(totals) >= 2:
        first_half = mean(totals[:len(totals) // 2])
        second_half = mean(totals[len(totals) // 2:])
        trend_pct = _pct(first_half, second_half) if first_half else None
        if trend_pct is not None and trend_pct < -15:
            suggestions.append(_suggestion(
                "Address Declining Monthly Trend",
                "performance", PRIORITY_HIGH,
                f"Case volume trended downward through the month: early average {_fmt_num(int(first_half))} vs later average {_fmt_num(int(second_half))} ({trend_pct:+.1f}%).",
                f"Month total: {_fmt_num(month_total)} | Average per week: {_fmt_num(int(avg_total))}",
                "Investigate whether the decline is seasonal, holiday-related, or indicative of an operational issue. Implement weekly check-ins to monitor recovery.",
                "Prevent sustained decline in client engagement.",
                "Within 1-2 weeks", "Weekly case volumes stabilise or recover", "High",
            ))
        elif trend_pct is not None and trend_pct > 15:
            suggestions.append(_suggestion(
                "Capitalise on Growing Momentum",
                "opportunities", PRIORITY_LOW,
                f"Case volume increased through the month ({trend_pct:+.1f}%), suggesting growing engagement.",
                f"Early avg: {_fmt_num(int(first_half))} | Later avg: {_fmt_num(int(second_half))}",
                "Continue current engagement strategies. Document what is working for replication.",
                "Sustain the positive growth trajectory.",
                "Ongoing", "Maintain upward trend into next month", "Low",
            ))

    # Best vs worst week
    if best_week["total"] and worst_week["total"]:
        diff_pct = _pct(worst_week["total"], best_week["total"])
        if diff_pct and diff_pct > 30:
            suggestions.append(_suggestion(
                "Investigate Weekly Variance",
                "operational", PRIORITY_MEDIUM,
                f"Significant variance between best week ({_fmt_num(best_week['total'])}) and worst week ({_fmt_num(worst_week['total'])}).",
                f"Best: {_fmt_num(best_week['total'])} | Worst: {_fmt_num(worst_week['total'])} | Gap: {diff_pct:.1f}%",
                "Analyse scheduling, holidays, or staffing patterns that may cause weekly fluctuations. Aim for more consistent weekly volumes.",
                "More predictable resource allocation and consistent service delivery.",
                "2-4 weeks", "Weekly variance reduced to under 20%", "Medium",
            ))

    # Aggregate concern analysis
    agg_concern = {}
    for s in weekly_snaps:
        for k, v in s.get("concern", {}).items():
            agg_concern[k] = agg_concern.get(k, 0) + v
    if agg_concern:
        top_c = max(agg_concern.items(), key=lambda x: x[1])
        top_pct = round(top_c[1] / month_total * 100, 1) if month_total else 0
        if top_pct >= 25:
            suggestions.append(_suggestion(
                f"Focus on {CONCERN_LABELS_MAP.get(top_c[0], top_c[0])} Through Targeted Programs",
                "engagement", PRIORITY_MEDIUM,
                f"{CONCERN_LABELS_MAP.get(top_c[0], top_c[0])} represents {top_pct}% of all monthly concerns ({_fmt_num(top_c[1])} cases).",
                f"Monthly total concerns: {_fmt_num(month_total)} | Top concern: {_fmt_num(top_c[1])} ({top_pct}%)",
                "Develop a dedicated programme or workshop addressing this concern. Partner with specialists if needed.",
                "Reduce the prevalence of this concern through proactive intervention.",
                "1-3 months", "Proportion of top concern decreases by 5+ percentage points", "Medium",
            ))

    # Follow-up analysis
    total_fu = sum(s.get("followup", 0) for s in weekly_snaps)
    total_new = sum(s.get("new", 0) for s in weekly_snaps)
    fu_ratio = round(total_fu / month_total * 100, 1) if month_total else 0
    if fu_ratio < 50:
        suggestions.append(_suggestion(
            "Strengthen Follow-Up Processes",
            "operational", PRIORITY_MEDIUM,
            f"Follow-ups represent only {fu_ratio}% of total cases, suggesting gaps in continuity of care.",
            f"Follow-ups: {_fmt_num(total_fu)} | New: {_fmt_num(total_new)} | Ratio: {fu_ratio}%",
            "Implement automated follow-up scheduling. Track follow-up completion rates weekly.",
            "Improved client outcomes through consistent care continuity.",
            "2-4 weeks", "Follow-up ratio increases above 60%", "Medium",
        ))

    # No-show aggregation
    total_ns = sum(s.get("no_show_turn_up", 0) for s in weekly_snaps)
    total_sessions = sum(s.get("total_sessions", 0) for s in weekly_snaps)
    if total_sessions and total_ns:
        ns_rate = round(total_ns / total_sessions * 100)
        if ns_rate >= 18:
            suggestions.append(_suggestion(
                "Implement Monthly No-Show Reduction Programme",
                "operational", PRIORITY_HIGH,
                f"Monthly no-show rate is {ns_rate}% ({_fmt_num(total_ns)} of {_fmt_num(total_sessions)} sessions).",
                f"No-shows: {_fmt_num(total_ns)} | Sessions: {_fmt_num(total_sessions)} | Rate: {ns_rate}%",
                "Introduce automated reminders (SMS/email) 48h and 2h before sessions. Track no-show patterns by day and counsellor.",
                "Reduce no-shows to below 12%, recovering wasted session capacity.",
                "1-2 months", "No-show rate drops below 12%", "High",
            ))

    # --- Positive achievements ---
    if len(totals) >= 2 and totals[-1] > totals[0]:
        suggestions.append(_suggestion(
            "Document and Replicate Monthly Success Factors",
            "opportunities", PRIORITY_LOW,
            "Case volume grew over the month, indicating effective engagement strategies.",
            f"First week: {_fmt_num(totals[0])} | Last week: {_fmt_num(totals[-1])}",
            "Identify and document the factors that contributed to growth (new referral sources, campaigns, etc.).",
            "Replicate success in subsequent months.",
            "Within 1 month", "Sustained or improved performance next month", "Low",
        ))

    if not suggestions:
        suggestions.append(_suggestion(
            "Continue Current Approach",
            "opportunities", PRIORITY_LOW,
            "Monthly performance is stable with no major issues detected.",
            f"Month total: {_fmt_num(month_total)} | Average: {_fmt_num(int(avg_total))}/week",
            "Maintain current operations and continue monitoring weekly trends.",
            "Sustain stable performance.",
            "Ongoing", "Stable metrics next month", "Low",
        ))

    return {
        "summary": (
            f"Monthly total: {_fmt_num(month_total)} cases across {len(weekly_snaps)} weeks "
            f"(avg {_fmt_num(int(avg_total))}/week). "
            f"Best week: {_fmt_num(best_week['total'])} | Weakest: {_fmt_num(worst_week['total'])}."
        ),
        "suggestions": sorted(suggestions, key=lambda s: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[s["priority"]])),
        "kpi": {
            "total_suggestions": len(suggestions),
            "high": sum(1 for s in suggestions if s["priority"] == PRIORITY_HIGH),
            "medium": sum(1 for s in suggestions if s["priority"] == PRIORITY_MEDIUM),
            "low": sum(1 for s in suggestions if s["priority"] == PRIORITY_LOW),
            "opportunities": sum(1 for s in suggestions if s["category"] == "opportunities"),
        },
    }


# ---------------------------------------------------------------------------
# Yearly suggestions
# ---------------------------------------------------------------------------

def generate_yearly_suggestions(monthly_snaps):
    """Generate suggestions from a list of monthly snapshots within a year."""
    if not monthly_snaps:
        return {"summary": "No monthly data available for this year.", "suggestions": [], "kpi": _zero_kpi()}

    totals = [s["total"] for s in monthly_snaps]
    year_total = sum(totals)
    avg_month = round(mean(totals), 1)
    best = max(monthly_snaps, key=lambda s: s["total"])
    worst = min(monthly_snaps, key=lambda s: s["total"])
    suggestions = []

    # Overall trend
    if len(totals) >= 4:
        first_q = mean(totals[:len(totals) // 4])
        last_q = mean(totals[-len(totals) // 4:])
        yoy_pct = _pct(first_q, last_q)
        if yoy_pct is not None and abs(yoy_pct) >= 15:
            direction = "grew" if yoy_pct > 0 else "declined"
            suggestions.append(_suggestion(
                f"Yearly Performance Trend: {direction.title()}",
                "performance",
                PRIORITY_HIGH if yoy_pct < -15 else PRIORITY_MEDIUM,
                f"Case volume {direction} {abs(yoy_pct):.1f}% from the beginning to the end of the year.",
                f"Early quarter avg: {_fmt_num(int(first_q))} | Late quarter avg: {_fmt_num(int(last_q))} | Change: {yoy_pct:+.1f}%",
                "Conduct a strategic review of the year's operations. Identify what changed and what drove the trend.",
                "Inform strategic planning for the next fiscal year.",
                "Within 1 month", "Strategic plan documented with actionable priorities", "High" if yoy_pct < -15 else "Medium",
            ))

    # Monthly volatility
    if len(totals) >= 3:
        try:
            from statistics import pstdev
            sd = pstdev(totals)
            cv = round(sd / avg_month * 100, 1) if avg_month else 0
            if cv >= 30:
                suggestions.append(_suggestion(
                    "Reduce Monthly Volume Volatility",
                    "operational", PRIORITY_MEDIUM,
                    f"Coefficient of variation is {cv}%, indicating high month-to-month inconsistency.",
                    f"Standard deviation: {_fmt_num(int(sd))} | Average: {_fmt_num(int(avg_month))} | CV: {cv}%",
                    "Analyse seasonal patterns. Develop capacity plans that account for peak and off-peak months.",
                    "More predictable resource planning and consistent service delivery.",
                    "1-3 months", "CV drops below 25%", "Medium",
                ))
        except Exception:
            pass

    # Best vs worst month
    if best["total"] and worst["total"]:
        gap = _pct(worst["total"], best["total"])
        if gap and gap > 50:
            suggestions.append(_suggestion(
                "Investigate Extreme Monthly Variation",
                "operational", PRIORITY_MEDIUM,
                f"The strongest month ({_fmt_num(best['total'])}) had {gap:.0f}% more cases than the weakest ({_fmt_num(worst['total'])}).",
                f"Best: {_fmt_num(best['total'])} | Worst: {_fmt_num(worst['total'])}",
                "Map monthly volumes against academic calendar, holidays, and staffing changes. Plan capacity accordingly.",
                "Reduce extreme swings and ensure adequate staffing year-round.",
                "1-3 months", "Gap between best and worst months narrows", "Medium",
            ))

    # Aggregate concerns
    agg_concern = {}
    for s in monthly_snaps:
        for k, v in s.get("concern", {}).items():
            agg_concern[k] = agg_concern.get(k, 0) + v
    if agg_concern:
        top = max(agg_concern.items(), key=lambda x: x[1])
        pct = round(top[1] / year_total * 100, 1) if year_total else 0
        if pct >= 25:
            suggestions.append(_suggestion(
                f"Develop Year-Round {CONCERN_LABELS_MAP.get(top[0], top[0])} Intervention Programme",
                "development", PRIORITY_MEDIUM,
                f"{CONCERN_LABELS_MAP.get(top[0], top[0])} is the top concern for the year at {pct}% ({_fmt_num(top[1])} cases).",
                f"Annual total: {_fmt_num(year_total)} | Top concern: {_fmt_num(top[1])} ({pct}%)",
                "Design a structured programme addressing this concern. Include workshops, early screening, and counsellor training.",
                "Reduce the prevalence of this concern at a systemic level.",
                "3-6 months", "Year-over-year reduction in this concern's proportion", "Medium",
            ))

    # Long-term opportunities
    suggestions.append(_suggestion(
        "Develop Strategic Improvement Plan for Next Year",
        "development", PRIORITY_LOW,
        "Use this year's data to inform next year's strategy.",
        f"Annual total: {_fmt_num(year_total)} cases across {len(monthly_snaps)} months.",
        "Compile a comprehensive annual review. Set measurable targets for key metrics. Plan new programmes based on identified needs.",
        "Data-driven strategic planning for improved outcomes.",
        "Within 3 months", "Annual strategic plan with measurable KPIs defined", "Low",
    ))

    if not suggestions:
        suggestions.append(_suggestion(
            "Maintain Current Operations",
            "opportunities", PRIORITY_LOW,
            "Yearly performance is stable.",
            f"Annual total: {_fmt_num(year_total)} | Average: {_fmt_num(int(avg_month))}/month",
            "Continue current operations and plan for next year based on trends.",
            "Sustain performance.",
            "Ongoing", "Stable metrics next year", "Low",
        ))

    return {
        "summary": (
            f"Annual total: {_fmt_num(year_total)} cases across {len(monthly_snaps)} months "
            f"(avg {_fmt_num(int(avg_month))}/month). "
            f"Best month: {best.get('label', '')} ({_fmt_num(best['total'])}) | "
            f"Weakest: {worst.get('label', '')} ({_fmt_num(worst['total'])})."
        ),
        "suggestions": sorted(suggestions, key=lambda s: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[s["priority"]])),
        "kpi": {
            "total_suggestions": len(suggestions),
            "high": sum(1 for s in suggestions if s["priority"] == PRIORITY_HIGH),
            "medium": sum(1 for s in suggestions if s["priority"] == PRIORITY_MEDIUM),
            "low": sum(1 for s in suggestions if s["priority"] == PRIORITY_LOW),
            "opportunities": sum(1 for s in suggestions if s["category"] == "opportunities"),
        },
    }


# ---------------------------------------------------------------------------
# Comparison suggestions
# ---------------------------------------------------------------------------

def generate_comparison_suggestions(snap_a, snap_b, comparison_type="week"):
    """Generate suggestions comparing two periods."""
    suggestions = []
    type_label = {"week": "Week-over-Week", "month": "Month-over-Month", "year": "Year-over-Year"}.get(comparison_type, "Period-over-Period")

    total_a = snap_a["total"]
    total_b = snap_b["total"]

    if total_a == 0 and total_b == 0:
        return {
            "summary": "No cases in either period for comparison.",
            "suggestions": [],
            "kpi": _zero_kpi(),
            "comparison_type": comparison_type,
        }

    pct_total = _pct(total_a, total_b)

    # Overall change
    if pct_total is not None and abs(pct_total) >= 15:
        suggestions.append(_suggestion(
            f"Address {type_label} Volume Change",
            "performance",
            PRIORITY_HIGH if pct_total < -15 else PRIORITY_MEDIUM,
            f"Total cases {'increased' if pct_total > 0 else 'decreased'} by {abs(pct_total):.1f}% between periods.",
            f"Period A: {_fmt_num(total_a)} | Period B: {_fmt_num(total_b)} | Change: {pct_total:+.1f}%",
            "Investigate root causes for the change. Adjust resource allocation if needed.",
            "Respond proactively to volume changes to maintain service quality.",
            "Within 1 week", "Stabilise or improve volume in next period", "High" if pct_total < -15 else "Medium",
        ))

    # Follow-up change
    fu_pct = _pct(snap_a.get("followup", 0), snap_b.get("followup", 0))
    if fu_pct is not None and fu_pct < -15:
        suggestions.append(_suggestion(
            "Improve Follow-Up Continuity",
            "operational", PRIORITY_HIGH,
            f"Follow-ups dropped {abs(fu_pct):.1f}% between periods.",
            f"Period A follow-ups: {_fmt_num(snap_a.get('followup', 0))} | Period B: {_fmt_num(snap_b.get('followup', 0))}",
            "Implement follow-up tracking dashboard. Schedule follow-up review meetings.",
            "Restore follow-up rates and improve client retention.",
            "Within 1 week", "Follow-up rate returns to previous level", "High",
        ))

    # Concern shifts
    concern_a = snap_a.get("concern", {})
    concern_b = snap_b.get("concern", {})
    for key, label in CONCERN_LABELS_MAP.items():
        va = concern_a.get(key, 0)
        vb = concern_b.get(key, 0)
        if va and vb:
            cpct = _pct(va, vb)
            if cpct is not None and cpct > 30:
                suggestions.append(_suggestion(
                    f"Address Rise in {label}",
                    "engagement", PRIORITY_MEDIUM,
                    f"{label} cases increased by {cpct:.1f}% ({_fmt_num(va)} to {_fmt_num(vb)}).",
                    f"Period A: {_fmt_num(va)} | Period B: {_fmt_num(vb)} | Change: {cpct:+.1f}%",
                    f"Develop targeted interventions for {label.lower()} concerns. Review referral pathways.",
                    "Prevent further escalation of this concern type.",
                    "1-2 weeks", f"Stabilise or reduce {label.lower()} cases", "Medium",
                ))
                break

    # Positive improvements
    for key, label in CONCERN_LABELS_MAP.items():
        va = concern_a.get(key, 0)
        vb = concern_b.get(key, 0)
        if va and vb:
            cpct = _pct(va, vb)
            if cpct is not None and cpct < -20:
                suggestions.append(_suggestion(
                    f"Sustain Improvement in {label}",
                    "opportunities", PRIORITY_LOW,
                    f"{label} cases decreased by {abs(cpct):.1f}%, showing positive progress.",
                    f"Period A: {_fmt_num(va)} | Period B: {_fmt_num(vb)} | Change: {cpct:+.1f}%",
                    "Document effective strategies. Share best practices with the team.",
                    "Maintain the positive trajectory.",
                    "Ongoing", f"Continue reducing {label.lower()} proportion", "Low",
                ))
                break

    if not suggestions:
        suggestions.append(_suggestion(
            "Monitor and Maintain",
            "opportunities", PRIORITY_LOW,
            f"Periods show similar performance with no major {type_label.lower()} changes.",
            f"Period A: {_fmt_num(total_a)} | Period B: {_fmt_num(total_b)}",
            "Continue monitoring. Review data quality for both periods.",
            "Maintain current performance levels.",
            "Ongoing", "Stable metrics in next period", "Low",
        ))

    return {
        "summary": (
            f"{type_label}: {_fmt_num(total_a)} cases in Period A vs {_fmt_num(total_b)} in Period B "
            f"({pct_total:+.1f}% change)." if pct_total is not None else
            f"{type_label}: {_fmt_num(total_a)} cases in Period A vs {_fmt_num(total_b)} in Period B."
        ),
        "suggestions": sorted(suggestions, key=lambda s: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[s["priority"]])),
        "kpi": {
            "total_suggestions": len(suggestions),
            "high": sum(1 for s in suggestions if s["priority"] == PRIORITY_HIGH),
            "medium": sum(1 for s in suggestions if s["priority"] == PRIORITY_MEDIUM),
            "low": sum(1 for s in suggestions if s["priority"] == PRIORITY_LOW),
            "opportunities": sum(1 for s in suggestions if s["category"] == "opportunities"),
        },
        "comparison_type": comparison_type,
    }


# ---------------------------------------------------------------------------
# Roadmap generation
# ---------------------------------------------------------------------------

def generate_roadmap(suggestions):
    """Generate an improvement roadmap from a list of suggestions."""
    immediate = []
    short_term = []
    medium_term = []
    long_term = []

    for s in suggestions:
        timeline = (s.get("timeline") or "").lower()
        entry = {
            "title": s["title"],
            "category": s.get("category_label", ""),
            "priority": s["priority"],
            "action": s.get("action", ""),
        }
        if "immediate" in timeline or "0-7" in timeline or "1 week" in timeline:
            immediate.append(entry)
        elif "1-2 week" in timeline or "2-4 week" in timeline or "short" in timeline:
            short_term.append(entry)
        elif "1-3 month" in timeline or "1 month" in timeline or "medium" in timeline:
            medium_term.append(entry)
        elif "3-6" in timeline or "3-12" in timeline or "long" in timeline or "ongoing" in timeline:
            long_term.append(entry)
        else:
            short_term.append(entry)

    return {
        "immediate": {"label": "Immediate (0-7 Days)", "items": immediate},
        "short_term": {"label": "Short Term (1-4 Weeks)", "items": short_term},
        "medium_term": {"label": "Medium Term (1-3 Months)", "items": medium_term},
        "long_term": {"label": "Long Term (3-12 Months)", "items": long_term},
    }


# ---------------------------------------------------------------------------
# PPT-ready summary
# ---------------------------------------------------------------------------

def ppt_summary(result):
    """Return a flat dict suitable for rendering on a PPT slide."""
    kpi = result.get("kpi", {})
    top_recs = result.get("suggestions", [])[:5]
    roadmap = result.get("roadmap", generate_roadmap(result.get("suggestions", [])))
    return {
        "summary": result.get("summary", ""),
        "kpi": kpi,
        "top_recommendations": [
            {
                "title": r["title"],
                "category": r.get("category_label", ""),
                "priority": r["priority"],
                "evidence": r.get("evidence", ""),
                "action": r.get("action", ""),
                "benefit": r.get("benefit", ""),
            }
            for r in top_recs
        ],
        "roadmap": roadmap,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zero_kpi():
    return {"total_suggestions": 0, "high": 0, "medium": 0, "low": 0, "opportunities": 0}
