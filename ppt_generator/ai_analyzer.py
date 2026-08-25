"""
AI Data Analyzer — OpenRouter-powered insights for Wellness Centre reports.

Uses OpenRouter API for rich natural-language analysis.
Falls back to rule-based analysis if API is unavailable.

Usage:
    from ai_analyzer import analyze
    insights = analyze(period_data, comparison_data=None)
"""

import json
from openrouter_client import chat, is_available


def _pct(part, whole):
    if whole > 0:
        return part / whole * 100
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# OPENROUTER-POWERED ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a senior data analyst for a university Wellness Centre (IIT Madras).
Analyse the wellness data and provide EXACTLY 8 concise, actionable bullet-point insights.

Rules:
- Each insight MUST start with a specific number or percentage
- Focus on: distribution patterns, notable concentrations, areas of concern
- End with 1-2 actionable recommendations
- Be specific: use actual counts and percentages
- Return ONLY the numbered list, no intro/outro text"""


def _openrouter_analysis(period_a: dict, period_b: dict = None) -> list:
    """Use OpenRouter API to generate rich insights."""
    if not is_available():
        return []

    if period_b:
        user_msg = f"""Compare these two wellness periods:

PERIOD A ({period_a.get('label', 'Previous')}):
- Total: {period_a.get('grand', 0)} cases (New: {period_a.get('new', 0)}, Follow-up: {period_a.get('followup', 0)})
- Verticals: {json.dumps(period_a.get('vertical', {}))}
- Concerns: {json.dumps(period_a.get('concern', {}))}
- Stakeholders: {json.dumps(period_a.get('stakeholder', {}))}

PERIOD B ({period_b.get('label', 'Current')}):
- Total: {period_b.get('grand', 0)} cases (New: {period_b.get('new', 0)}, Follow-up: {period_b.get('followup', 0)})
- Verticals: {json.dumps(period_b.get('vertical', {}))}
- Concerns: {json.dumps(period_b.get('concern', {}))}
- Stakeholders: {json.dumps(period_b.get('stakeholder', {}))}"""
    else:
        user_msg = f"""Analyse this wellness period:

PERIOD ({period_a.get('label', 'Current')}):
- Total: {period_a.get('grand', 0)} cases (New: {period_a.get('new', 0)}, Follow-up: {period_a.get('followup', 0)})
- Verticals: {json.dumps(period_a.get('vertical', {}))}
- Concerns: {json.dumps(period_a.get('concern', {}))}
- Stakeholders: {json.dumps(period_a.get('stakeholder', {}))}
- Gender: {json.dumps(period_a.get('gender', {}))}
- Mode: {json.dumps(period_a.get('mode', {}))}
- Referral: {json.dumps(period_a.get('referral', {}))}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]

    response = chat(messages, temperature=0.2, max_tokens=1024)
    if not response:
        return []

    lines = []
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue
        for prefix in [f"{i}." for i in range(1, 20)] + [f"{i})" for i in range(1, 20)]:
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        if line.startswith("- "):
            line = line[2:]
        if line:
            lines.append(line)
    return lines[:8]


# ═══════════════════════════════════════════════════════════════════════════════
# RULE-BASED FALLBACK (when no API key)
# ═══════════════════════════════════════════════════════════════════════════════

def _top_n(d, n=3):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]


def _largest_change(a_dict, b_dict):
    all_keys = set(list(a_dict.keys()) + list(b_dict.keys()))
    deltas = [(k, a_dict.get(k, 0), b_dict.get(k, 0),
               b_dict.get(k, 0) - a_dict.get(k, 0)) for k in all_keys]
    if not deltas:
        return None, None
    return max(deltas, key=lambda x: x[3]), min(deltas, key=lambda x: x[3])


def _fallback_single(period: dict) -> list:
    insights = []
    grand = period.get("grand", 0)
    new_n = period.get("new", 0)
    fu_n = period.get("followup", 0)

    insights.append(
        f"Total cases: {grand} (New: {new_n} [{_pct(new_n, grand):.1f}%], "
        f"Follow-up: {fu_n} [{_pct(fu_n, grand):.1f}%])."
    )

    vertical = period.get("vertical", {})
    if vertical:
        totals = {v: d.get("total", 0) for v, d in vertical.items()}
        top_v = max(totals, key=totals.get)
        if totals[top_v] > 0:
            insights.append(
                f"Highest-volume vertical: {top_v} with {totals[top_v]} cases "
                f"({_pct(totals[top_v], grand):.1f}% of total)."
            )

    concern = period.get("concern", {})
    if concern:
        top3 = _top_n(concern, 3)
        c_strs = [f"{c} ({v}, {_pct(v, grand):.1f}%)" for c, v in top3 if v > 0]
        if c_strs:
            insights.append(f"Top concerns: {'; '.join(c_strs)}.")

    stake = period.get("stakeholder", {})
    if stake:
        top3 = _top_n(stake, 3)
        s_strs = [f"{s} ({v}, {_pct(v, grand):.1f}%)" for s, v in top3 if v > 0]
        if s_strs:
            insights.append(f"Largest stakeholder groups: {'; '.join(s_strs)}.")

    gender = period.get("gender", {})
    if gender:
        parts = []
        for g in ["Male", "Female", "Others / Not to Say"]:
            val = gender.get(g, 0)
            if val > 0:
                parts.append(f"{g}: {val} ({_pct(val, grand):.1f}%)")
        if parts:
            insights.append(f"Gender distribution: {'; '.join(parts)}.")

    mode = period.get("mode", {})
    if mode:
        top3 = _top_n(mode, 3)
        m_strs = [f"{m} ({v}, {_pct(v, grand):.1f}%)" for m, v in top3 if v > 0]
        if m_strs:
            insights.append(f"Session modes: {'; '.join(m_strs)}.")

    referral = period.get("referral", {})
    if referral:
        top3 = _top_n(referral, 3)
        r_strs = [f"{r} ({v}, {_pct(v, grand):.1f}%)" for r, v in top3 if v > 0]
        if r_strs:
            insights.append(f"Referral sources: {'; '.join(r_strs)}.")

    recs = []
    if grand > 0:
        if fu_n / grand > 0.75:
            recs.append("High follow-up ratio — ensure adequate session capacity.")
    top_concern = max(concern, key=concern.get) if concern else None
    if top_concern and grand > 0:
        tc_pct = _pct(concern[top_concern], grand)
        if tc_pct > 30:
            recs.append(f"{top_concern} dominates ({tc_pct:.1f}%) — prioritise specialised intervention.")
    if recs:
        insights.append("Recommendation: " + " ".join(recs))

    return insights


def _fallback_comparison(a: dict, b: dict) -> list:
    insights = []
    a_grand = a.get("grand", 0)
    b_grand = b.get("grand", 0)

    delta = b_grand - a_grand
    pct = _pct(delta, a_grand)
    direction = "increased" if delta > 0 else "decreased"
    insights.append(f"Total cases {direction} from {a_grand} to {b_grand} ({delta:+d}, {pct:+.1f}%).")

    for key, name in [("new", "New cases"), ("followup", "Follow-up cases")]:
        a_val = a.get(key, 0)
        b_val = b.get(key, 0)
        d = b_val - a_val
        insights.append(f"{name}: {a_val} to {b_val} ({d:+d}, {_pct(d, a_val):+.1f}%).")

    a_vert = a.get("vertical", {})
    b_vert = b.get("vertical", {})
    if a_vert and b_vert:
        inc, dec = _largest_change(
            {v: d.get("total", 0) for v, d in a_vert.items()},
            {v: d.get("total", 0) for v, d in b_vert.items()},
        )
        if inc and inc[3] > 0:
            insights.append(f"Largest increase: {inc[0]} ({inc[1]} to {inc[2]}, {inc[3]:+d}).")
        if dec and dec[3] < 0:
            insights.append(f"Largest decrease: {dec[0]} ({dec[1]} to {dec[2]}, {dec[3]:+d}).")

    a_conc = a.get("concern", {})
    b_conc = b.get("concern", {})
    if a_conc and b_conc:
        inc_c, dec_c = _largest_change(a_conc, b_conc)
        if inc_c and inc_c[3] > 0:
            insights.append(f"Biggest concern rise: {inc_c[0]} ({inc_c[1]} to {inc_c[2]}, {inc_c[3]:+d}).")
        if dec_c and dec_c[3] < 0:
            insights.append(f"Biggest concern drop: {dec_c[0]} ({dec_c[1]} to {dec_c[2]}, {dec_c[3]:+d}).")

    return insights


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def analyze(period_a: dict, period_b: dict = None) -> list:
    """Generate insights — OpenRouter AI primary, rule-based fallback.

    Args:
        period_a: PeriodData dict
        period_b: optional PeriodData dict for comparison

    Returns:
        list of insight strings
    """
    # Try OpenRouter first
    result = _openrouter_analysis(period_a, period_b)
    if result:
        return result

    # Fallback to rules
    if period_b:
        return _fallback_comparison(period_a, period_b)
    return _fallback_single(period_a)
