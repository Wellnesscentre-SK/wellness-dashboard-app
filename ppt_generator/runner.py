"""
CLI entry point for generating all Wellness Report PPTs.

Usage:
    cd ppt_generator
    python -m runner

Generates:
    output/Normal_Weekly_Wellness_Report.pptx
    output/Normal_Monthly_Wellness_Report.pptx
    output/Normal_Yearly_Wellness_Report.pptx
    output/Weekly_Comparison_Report.pptx
    output/Monthly_Comparison_Report.pptx
    output/Yearly_Comparison_Report.pptx
"""

import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import config as C
import components as CM
from normal_week import build as build_normal_week
from normal_monthly import build as build_normal_monthly
from normal_yearly import build as build_normal_yearly
from weekly import build as build_weekly
from monthly import build as build_monthly
from yearly import build as build_yearly


# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA  (matches the reference PPT values)
# ═══════════════════════════════════════════════════════════════════════════════

WEEKLY_A = {
    "label": "15th to 21st July 2026",
    "new": 12, "followup": 85, "grand": 97,
    "gender": {"Male": 52, "Female": 43, "Others / Not to Say": 2},
    "mode": {"Online": 28, "In-Person": 58, "Phone": 11},
    "referral": {"Self": 78, "Director / Kushal Calls": 8,
                 "Dean / HoD / Faculty / Insti Hosp": 11,
                 "Friend / Family": 0, "Mitr / Saathi": 0},
    "vertical": {
        "WC": {"new": 4, "followup": 33, "total": 37},
        "TA": {"new": 5, "followup": 48, "total": 53},
        "YD": {"new": 8, "followup": 7, "total": 15},
        "MW": {"new": 0, "followup": 0, "total": 0},
    },
    "concern": {
        "Anxiety/Depresn/Panic/OCD": 27, "Acute Stress/Trauma": 52,
        "Career/Acad": 15, "Inter-personal": 18, "Self-Devlp": 8,
        "Clinical": 5, "Addiction": 3, "Medical/Health Issues": 4,
        "Suicidal Ideation/Self-harm": 4,
    },
    "stakeholder": {
        "UG": 34, "PG": 20, "Ph.D.": 24, "Dual Degree": 7,
        "IIT Faculty/Staff": 9, "Employee Family": 2,
        "Post Doc/Proj Asso": 3, "Not Able to Identify": 4,
    },
}

WEEKLY_B = {
    "label": "22nd to 28th July 2026",
    "new": 15, "followup": 78, "grand": 93,
    "gender": {"Male": 48, "Female": 42, "Others / Not to Say": 3},
    "mode": {"Online": 25, "In-Person": 55, "Phone": 13},
    "referral": {"Self": 72, "Director / Kushal Calls": 10,
                 "Dean / HoD / Faculty / Insti Hosp": 11,
                 "Friend / Family": 0, "Mitr / Saathi": 0},
    "vertical": {
        "WC": {"new": 9, "followup": 32, "total": 41},
        "TA": {"new": 3, "followup": 38, "total": 41},
        "YD": {"new": 7, "followup": 14, "total": 21},
        "MW": {"new": 0, "followup": 0, "total": 0},
    },
    "concern": {
        "Anxiety/Depresn/Panic/OCD": 20, "Acute Stress/Trauma": 25,
        "Career/Acad": 16, "Inter-personal": 20, "Self-Devlp": 3,
        "Clinical": 8, "Addiction": 2, "Medical/Health Issues": 3,
        "Suicidal Ideation/Self-harm": 6,
    },
    "stakeholder": {
        "UG": 36, "PG": 16, "Ph.D.": 21, "Dual Degree": 8,
        "IIT Faculty/Staff": 13, "Employee Family": 2,
        "Post Doc/Proj Asso": 5, "Not Able to Identify": 4,
    },
}

MONTHLY_A = {
    "label": "MAY 2026",
    "new": 65, "followup": 448, "grand": 513,
    "gender": {"Male": 298, "Female": 202, "Others / Not to Say": 13},
    "mode": {"Online": 120, "In-Person": 357, "Phone": 36},
    "referral": {"Self": 463, "Director / Kushal Calls": 17,
                 "Dean / HoD / Faculty / Insti Hosp": 19,
                 "Friend / Family": 14, "Mitr / Saathi": 0},
    "vertical": {
        "WC": {"new": 12, "followup": 102, "total": 114},
        "TA": {"new": 19, "followup": 143, "total": 162},
        "YD": {"new": 34, "followup": 203, "total": 237},
        "MW": {"new": 30, "followup": 51, "total": 81},
    },
    "concern": {
        "Anxiety/Depresn/Panic/OCD": 180, "Acute Stress/Trauma": 45,
        "Career/Acad": 65, "Inter-personal": 107, "Self-Devlp": 42,
        "Clinical": 28, "Addiction": 15, "Medical/Health Issues": 18,
        "Suicidal Ideation/Self-harm": 15,
    },
    "stakeholder": {
        "UG": 244, "PG": 98, "Ph.D.": 91, "Dual Degree": 22,
        "IIT Faculty/Staff": 32, "Employee Family": 15,
        "Post Doc/Proj Asso": 11, "Not Able to Identify": 0,
    },
}

MONTHLY_B = {
    "label": "JUNE 2026",
    "new": 69, "followup": 304, "grand": 373,
    "gender": {"Male": 195, "Female": 159, "Others / Not to Say": 19},
    "mode": {"Online": 105, "In-Person": 224, "Phone": 44},
    "referral": {"Self": 308, "Director / Kushal Calls": 19,
                 "Dean / HoD / Faculty / Insti Hosp": 45,
                 "Friend / Family": 0, "Mitr / Saathi": 0},
    "vertical": {
        "WC": {"new": 6, "followup": 52, "total": 58},
        "TA": {"new": 20, "followup": 45, "total": 65},
        "YD": {"new": 25, "followup": 162, "total": 187},
        "MW": {"new": 18, "followup": 45, "total": 63},
    },
    "concern": {
        "Anxiety/Depresn/Panic/OCD": 67, "Acute Stress/Trauma": 35,
        "Career/Acad": 55, "Inter-personal": 127, "Self-Devlp": 38,
        "Clinical": 22, "Addiction": 10, "Medical/Health Issues": 12,
        "Suicidal Ideation/Self-harm": 1,
    },
    "stakeholder": {
        "UG": 121, "PG": 102, "Ph.D.": 109, "Dual Degree": 15,
        "IIT Faculty/Staff": 18, "Employee Family": 5,
        "Post Doc/Proj Asso": 3, "Not Able to Identify": 0,
    },
}

YEARLY_A = [
    {**MONTHLY_A, "label": "Apr 2024"},
    {**MONTHLY_A, "label": "May 2024"},
    {**MONTHLY_A, "label": "Jun 2024"},
    {**MONTHLY_A, "label": "Jul 2024"},
    {**MONTHLY_A, "label": "Aug 2024"},
    {**MONTHLY_A, "label": "Sep 2024"},
    {**MONTHLY_A, "label": "Oct 2024"},
    {**MONTHLY_A, "label": "Nov 2024"},
    {**MONTHLY_A, "label": "Dec 2024"},
    {**MONTHLY_A, "label": "Jan 2025"},
    {**MONTHLY_A, "label": "Feb 2025"},
    {**MONTHLY_A, "label": "Mar 2025"},
]

YEARLY_B = [
    {**MONTHLY_B, "label": "Apr 2025"},
    {**MONTHLY_B, "label": "May 2025"},
    {**MONTHLY_B, "label": "Jun 2025"},
    {**MONTHLY_B, "label": "Jul 2025"},
    {**MONTHLY_B, "label": "Aug 2025"},
    {**MONTHLY_B, "label": "Sep 2025"},
    {**MONTHLY_B, "label": "Oct 2025"},
    {**MONTHLY_B, "label": "Nov 2025"},
    {**MONTHLY_B, "label": "Dec 2025"},
    {**MONTHLY_B, "label": "Jan 2026"},
    {**MONTHLY_B, "label": "Feb 2026"},
    {**MONTHLY_B, "label": "Mar 2026"},
]

PROPOSED_POINTS = [
    "Continue weekly data tracking across all verticals (WLC, YourDOST, Myndwell)",
    "Monitor anxiety/depression trends - slight decrease observed this week",
    "Increase outreach to PG and Ph.D. scholars for early intervention",
    "Conduct follow-up sessions for cases with ongoing concerns",
    "Coordinate with HoDs for faculty referral pipeline",
]


def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("WELLNESS CENTRE PPT REPORT GENERATOR")
    print("=" * 60)

    # ── NORMAL REPORTS (single period) ────────────────────────────────────────

    print("\n[1/6] Generating Normal Weekly Report...")
    try:
        path = os.path.join(output_dir, "Normal_Weekly_Wellness_Report.pptx")
        ppt = build_normal_week(WEEKLY_A)
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[2/6] Generating Normal Monthly Report...")
    try:
        path = os.path.join(output_dir, "Normal_Monthly_Wellness_Report.pptx")
        ppt = build_normal_monthly(MONTHLY_A)
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[3/6] Generating Normal Yearly Report (merged Jan-Dec analysis)...")
    try:
        path = os.path.join(output_dir, "Normal_Yearly_Wellness_Report.pptx")
        ppt = build_normal_yearly(YEARLY_A)
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # ── COMPARISON REPORTS (two periods) ──────────────────────────────────────

    print("\n[4/6] Generating Weekly Comparison Report...")
    try:
        path = os.path.join(output_dir, "Weekly_Comparison_Report.pptx")
        ppt = build_weekly(WEEKLY_A, WEEKLY_B, proposed_points=PROPOSED_POINTS)
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[5/6] Generating Monthly Comparison Report...")
    try:
        path = os.path.join(output_dir, "Monthly_Comparison_Report.pptx")
        ppt = build_monthly(MONTHLY_A, MONTHLY_B,
                            key_insights=[
                                "Overall cases fell 27.3% (513 to 373), driven by fewer follow-ups",
                                "Your Dost remained highest-volume vertical",
                                "Anxiety/Depression cases dropped sharply (180 to 67)",
                                "Interpersonal concerns rose (107 to 127)",
                            ],
                            proposed_points=PROPOSED_POINTS)
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[6/6] Generating Yearly Comparison Report...")
    try:
        path = os.path.join(output_dir, "Yearly_Comparison_Report.pptx")
        ppt = build_yearly(YEARLY_A, YEARLY_B,
                           fy1_label="FY 2024-25",
                           fy2_label="FY 2025-26")
        with open(path, "wb") as f:
            f.write(ppt)
        print(f"  Saved: {path} ({len(ppt):,} bytes)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    print("ALL REPORTS GENERATED!")
    print(f"Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
