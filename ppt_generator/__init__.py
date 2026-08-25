"""
Wellness Centre PPT Report Generator

Produces dean-quality PowerPoint reports matching the reference format
from "Report to asc dean_29_JULY_2026 - WO.pptx".

Modules:
  weekly   - Week-to-week comparison (10 slides)
  monthly  - Month-to-month comparison
  yearly   - Year-over-year comparison

Usage:
    from ppt_generator.weekly import build
    ppt_bytes = build(period_a_data, period_b_data)
"""
