"""
Central configuration for the Wellness Centre PPT report generator.

Excel Report Sheet Design System:
  - Header Blue: #2F5597 (section headers, table headers)
  - Orange: #ED7D31 (New Cases)
  - Green: #548235 (Follow-up Cases)
  - Gray: #7F7F7F (Top Vertical card)
  - Title Red: #C00000
  - Subtitle Gray: #595959
  - WC (WLN + Team A): #2F5597
  - Your Dost: #ED7D31
  - Myndwell: #548235
"""

import os
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(_ASSETS_DIR, "logo.png")

SLIDE_W = 12192000
SLIDE_H = 6858000

WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
BLACK       = RGBColor(0x00, 0x00, 0x00)
DARK_GRAY   = RGBColor(0x37, 0x41, 0x51)
GRAY        = RGBColor(0x59, 0x59, 0x59)
LIGHT_GRAY  = RGBColor(0xE2, 0xE8, 0xF0)
VERY_LIGHT  = RGBColor(0xF8, 0xFA, 0xFC)

PRIMARY     = RGBColor(0x2F, 0x55, 0x97)
PRIMARY_LT  = RGBColor(0x5B, 0x9B, 0xD5)
PRIMARY_XLT = RGBColor(0xDB, 0xEA, 0xFE)

WC_COLOR    = RGBColor(0x44, 0x72, 0xC4)
TEAM_A_CLR  = RGBColor(0xED, 0x7D, 0x31)
YD_COLOR    = RGBColor(0xA5, 0xA5, 0xA5)
MW_COLOR    = RGBColor(0xFF, 0xC0, 0x00)
ACCENT      = RGBColor(0xED, 0x7D, 0x31)

SUCCESS     = RGBColor(0x54, 0x82, 0x35)
WARNING     = RGBColor(0xED, 0x7D, 0x31)
DANGER      = RGBColor(0xC0, 0x00, 0x00)
INFO        = RGBColor(0x2F, 0x55, 0x97)

NEW_CASE_CLR    = RGBColor(0xED, 0x7D, 0x31)
FOLLOWUP_CLR    = RGBColor(0x54, 0x82, 0x35)
TOTAL_CLR       = RGBColor(0x2F, 0x55, 0x97)
TOP_VERT_CLR    = RGBColor(0x7F, 0x7F, 0x7F)

VERT_COLORS = {"WLC": WC_COLOR, "YD": YD_COLOR, "MW": MW_COLOR}
SERIES_COLORS = [WC_COLOR, TEAM_A_CLR, YD_COLOR, MW_COLOR]
PIE_COLORS = [
    WC_COLOR, TEAM_A_CLR, YD_COLOR, MW_COLOR,
    RGBColor(0x7F, 0x7F, 0x7F), PRIMARY_LT, DARK_GRAY,
    RGBColor(0x7C, 0x3A, 0xED), RGBColor(0x06, 0xB6, 0xD4),
]

FONT_NAME     = "Calibri"
COVER_FONT    = Pt(36)
SECTION_FONT  = Pt(16)
HEADING_FONT  = Pt(20)
SLIDE9_FONT   = Pt(18)
PROPOSED_FONT = Pt(22)
BODY_FONT     = Pt(14)
TABLE_FONT    = Pt(11)
LABEL_FONT    = Pt(10)
LEGEND_FONT   = Pt(10)
SMALL_FONT    = Pt(9)

LOGO_WIDTH  = Inches(2.5)
LOGO_HEIGHT = Inches(0.5)
LOGO_LEFT   = (SLIDE_W - int(LOGO_WIDTH)) // 2
LOGO_TOP    = Inches(0.15)

LABEL_LEFT_LEFT   = Inches(0.25)
LABEL_LEFT_TOP    = Inches(0.75)
LABEL_LEFT_WIDTH  = Inches(6.0)
LABEL_LEFT_HEIGHT = Inches(0.75)
LABEL_RIGHT_LEFT   = Inches(6.85)
LABEL_RIGHT_TOP    = Inches(0.75)
LABEL_RIGHT_WIDTH  = Inches(6.0)
LABEL_RIGHT_HEIGHT = Inches(0.75)

PIE_HALF_LEFT   = Inches(0.15)
PIE_HALF_TOP    = Inches(1.60)
PIE_HALF_WIDTH  = Inches(6.2)
PIE_HALF_HEIGHT = Inches(5.6)
PIE_HALF_RIGHT_LEFT   = Inches(6.95)
PIE_HALF_RIGHT_TOP    = Inches(1.60)
PIE_HALF_RIGHT_WIDTH  = Inches(6.2)
PIE_HALF_RIGHT_HEIGHT = Inches(5.6)

PIE_FULL_LEFT   = Inches(0.15)
PIE_FULL_TOP    = Inches(1.60)
PIE_FULL_WIDTH  = Inches(13.0)
PIE_FULL_HEIGHT = Inches(5.6)

COL_LEFT   = Inches(0.15)
COL_TOP    = Inches(1.20)
COL_WIDTH  = Inches(13.0)
COL_HEIGHT = Inches(5.95)

COL_HALF_LEFT   = Inches(0.15)
COL_HALF_TOP    = Inches(1.20)
COL_HALF_WIDTH  = Inches(6.2)
COL_HALF_HEIGHT = Inches(5.95)
COL_HALF_RIGHT_LEFT = Inches(6.95)

TABLE_HEADER_BG    = PRIMARY
TABLE_HEADER_FG    = WHITE
TABLE_ALT_ROW_BG   = RGBColor(0xF1, 0xF5, 0xF9)
TABLE_BORDER_COLOR = LIGHT_GRAY

VERTICALS = {"WLC": "WLN Ctr", "YD": "Your Dost", "MW": "Myndwell"}
_LEGACY_WC = "WC"
_LEGACY_TA = "TA"

def combine_verticals(raw_vertical: dict) -> dict:
    wc = raw_vertical.get(_LEGACY_WC, {})
    ta = raw_vertical.get(_LEGACY_TA, {})
    wlc_new = wc.get("new", 0) + ta.get("new", 0)
    wlc_fu = wc.get("followup", 0) + ta.get("followup", 0)
    wlc_total = wc.get("total", 0) + ta.get("total", 0)
    result = {"WLC": {"new": wlc_new, "followup": wlc_fu, "total": wlc_total}}
    for key in ["YD", "MW"]:
        if key in raw_vertical:
            result[key] = raw_vertical[key]
        elif key.lower() in raw_vertical:
            result[key] = raw_vertical[key.lower()]
    return result

VERT_KEYS = ("WLC", "YD", "MW")
GENDER_LABELS = ["Male", "Female", "Others / Not to Say"]
MODE_LABELS   = ["Online", "In-Person", "Phone"]
REFERRAL_LABELS = ["Self", "Director / Kushal Calls",
                   "Dean / HoD / Faculty / Insti Hosp",
                   "Friend / Family", "Mitr / Saathi"]
REFERRAL_SHORT  = ["Self", "Director", "Dean/HoD", "Friend/Family", "Mitr/Saathi"]
CONCERN_LABELS = [
    "Anxiety/Depresn/Panic/OCD", "Acute Stress/Trauma", "Career/Acad",
    "Inter-personal", "Self-Devlp", "Clinical", "Addiction",
    "Medical/Health Issues", "Suicidal Ideation/Self-harm",
]
STAKEHOLDER_LABELS = [
    "UG", "PG", "Ph.D.", "Dual Degree", "IIT Faculty/Staff",
    "Employee Family", "Post Doc/Proj Asso", "Not Able to Identify",
]
