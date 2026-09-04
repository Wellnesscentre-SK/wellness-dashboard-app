"""
AI Assistant service â€” tool-calling chatbot backed by OpenRouter.

Tools available:
  - get_kpi_summary(period_id)
  - compare_teams(period_id)
  - get_top_concerns(period_id, n)
  - get_gender_breakdown(period_id)
  - get_session_mode_breakdown(period_id)
  - get_monthly_trend(months)
  - find_anomalies()
  - list_periods()
  - generate_report(period_id, format)  â€” requires approval

The assistant returns structured messages that the frontend renders as
chat bubbles, data tables, charts, and actionable buttons.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import urllib.request
import urllib.error
from datetime import date, timedelta
from typing import Any

from django.db.models import Sum, Q, F

from wellness.models import CaseRow, Period, SecondaryMetrics

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# OpenRouter client (inline to avoid sys.path issues)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "minimax/minimax-m3:free"
# Free-tier models churn quickly (de-listed, rate-limited, or turned paid).
# minimax/m3 returns clean, fast insight text; fall through this chain on
# 402/429/404/408; "openrouter/free" is a stable catch-all.
MODEL_FALLBACKS = [
    DEFAULT_MODEL,
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]


def _get_api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key.strip()
    key_file = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "ppt_generator", "openrouter_key.txt"
    )
    key_file = os.path.normpath(key_file)
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    return ""


def _chat_raw(messages: list, model: str = None, temperature: float = 0.3,
              max_tokens: int = 4096, tools: list | None = None) -> dict:
    """Send chat completion, return full response dict including tool_calls."""
    api_key = _get_api_key()
    if not api_key:
        return {"error": "No OpenRouter API key configured."}

    payload: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://wellness-centre.local",
            "X-Title": "Wellness Centre AI Assistant",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        return {"error": f"HTTP Error {e.code}: {e.reason}", "_status": e.code, "_body": body}
    except Exception as e:
        return {"error": str(e)}


def chat(messages: list, model: str = None, temperature: float = 0.3,
         max_tokens: int = 4096, tools: list | None = None) -> dict:
    """chat() with automatic fallback across free-tier models on rate-limit/paywall errors."""
    chain = [model] if model else list(MODEL_FALLBACKS)
    last: dict = {}
    for m in chain:
        result = _chat_raw(messages, model=m, temperature=temperature,
                           max_tokens=max_tokens, tools=tools)
        if "error" not in result:
            return result
        status = result.get("_status")
        last = result
        if status not in (402, 429, 404, 408):
            break
    return last


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TOOL DEFINITIONS (OpenRouter function-calling format)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_periods",
            "description": "List all available reporting periods with their IDs, types, and date ranges.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kpi_summary",
            "description": "Get KPI summary (total cases, new, follow-up, sessions, active cases) for a specific period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                },
                "required": ["period_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_teams",
            "description": "Compare WC, Team A, YourDost, and Myndwell verticals for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                },
                "required": ["period_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_concerns",
            "description": "Get the top N concerns/issues addressed in sessions for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                    "n": {"type": "integer", "description": "Number of top concerns to return (default 5)"},
                },
                "required": ["period_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gender_breakdown",
            "description": "Get gender breakdown (male, female, other) of cases for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                },
                "required": ["period_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_session_mode_breakdown",
            "description": "Get session mode breakdown (online, in-person, phone) for a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                },
                "required": ["period_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_trend",
            "description": "Get monthly case trends for the last N months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "months": {"type": "integer", "description": "Number of months of history (default 6)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_anomalies",
            "description": "Detect anomalies or unusual patterns across all periods (spikes, drops, outliers).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate and download a PPTX or Excel report for a period. REQUIRES USER APPROVAL before executing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_id": {"type": "integer", "description": "The period ID"},
                    "format": {"type": "string", "enum": ["ppt", "xlsx"], "description": "Report format"},
                },
                "required": ["period_id", "format"],
            },
        },
    },
]


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TOOL IMPLEMENTATIONS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _serialize_period(p: Period) -> dict:
    return {
        "id": p.id,
        "report_type": p.report_type,
        "period_start": str(p.period_start),
        "period_end": str(p.period_end),
        "status": p.status,
        "source": p.source,
    }


def tool_list_periods() -> dict:
    periods = Period.objects.filter(superseded_by__isnull=True).order_by("-period_start")
    return {"periods": [_serialize_period(p) for p in periods]}


def tool_get_kpi_summary(period_id: int) -> dict:
    rows = CaseRow.objects.filter(period_id=period_id)
    agg = rows.aggregate(
        total=Sum("total_cases"),
        male=Sum("gender_male"),
        female=Sum("gender_female"),
        other=Sum("gender_other"),
    )
    new_rows = rows.filter(case_type="new")
    fu_rows = rows.filter(case_type="followup")
    new_agg = new_rows.aggregate(total=Sum("total_cases"))
    fu_agg = fu_rows.aggregate(total=Sum("total_cases"))

    metrics = SecondaryMetrics.objects.filter(period_id=period_id)
    metrics_agg = metrics.aggregate(
        sessions=Sum("total_sessions"),
        active=Sum("active_cases"),
        early=Sum("early_prevention_warning"),
        no_show=Sum("no_show_turn_up"),
        over4=Sum("clients_over_4_sessions"),
    )

    p = Period.objects.filter(id=period_id).first()
    return {
        "period": _serialize_period(p) if p else None,
        "total_cases": agg["total"] or 0,
        "new_cases": new_agg["total"] or 0,
        "followup_cases": fu_agg["total"] or 0,
        "gender": {"male": agg["male"] or 0, "female": agg["female"] or 0, "other": agg["other"] or 0},
        "sessions": metrics_agg["sessions"] or 0,
        "active_cases": metrics_agg["active"] or 0,
        "early_prevention": metrics_agg["early"] or 0,
        "no_show": metrics_agg["no_show"] or 0,
        "over_4_sessions": metrics_agg["over4"] or 0,
    }


def tool_compare_teams(period_id: int) -> dict:
    verticals = ["WC", "TA", "YD", "MW"]
    result = {}
    for v in verticals:
        rows = CaseRow.objects.filter(period_id=period_id, vertical=v)
        new_r = rows.filter(case_type="new").aggregate(t=Sum("total_cases"))
        fu_r = rows.filter(case_type="followup").aggregate(t=Sum("total_cases"))
        metrics = SecondaryMetrics.objects.filter(period_id=period_id, vertical=v).first()
        result[v] = {
            "new": new_r["t"] or 0,
            "followup": fu_r["t"] or 0,
            "total": (new_r["t"] or 0) + (fu_r["t"] or 0),
            "sessions": metrics.total_sessions if metrics else 0,
            "active_cases": metrics.active_cases if metrics else 0,
        }
    return {"verticals": result}


def tool_get_top_concerns(period_id: int, n: int = 5) -> dict:
    fields = {
        "Anxiety/Depression/Panic/OCD": "concern_anxiety",
        "Acute Stress/Trauma": "concern_stress",
        "Career/Academic": "concern_career",
        "Inter-personal": "concern_interpersonal",
        "Self-Development": "concern_self_dev",
        "Clinical": "concern_clinical",
        "Addiction": "concern_addiction",
        "Medical/Health Issues": "concern_medical",
        "Suicidal Ideation/Self-harm": "concern_suicidal",
    }
    totals = {}
    for label, field in fields.items():
        agg = CaseRow.objects.filter(period_id=period_id).aggregate(v=Sum(field))
        totals[label] = agg["v"] or 0
    sorted_concerns = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:n]
    return {"concerns": [{"label": k, "count": v} for k, v in sorted_concerns]}


def tool_get_gender_breakdown(period_id: int) -> dict:
    agg = CaseRow.objects.filter(period_id=period_id).aggregate(
        male=Sum("gender_male"), female=Sum("gender_female"), other=Sum("gender_other")
    )
    total = (agg["male"] or 0) + (agg["female"] or 0) + (agg["other"] or 0)
    return {
        "total": total,
        "male": agg["male"] or 0,
        "female": agg["female"] or 0,
        "other": agg["other"] or 0,
        "male_pct": round((agg["male"] or 0) / total * 100, 1) if total else 0,
        "female_pct": round((agg["female"] or 0) / total * 100, 1) if total else 0,
        "other_pct": round((agg["other"] or 0) / total * 100, 1) if total else 0,
    }


def tool_get_session_mode_breakdown(period_id: int) -> dict:
    agg = CaseRow.objects.filter(period_id=period_id).aggregate(
        online=Sum("mode_online"), in_person=Sum("mode_in_person"), phone=Sum("mode_phone")
    )
    total = (agg["online"] or 0) + (agg["in_person"] or 0) + (agg["phone"] or 0)
    return {
        "total": total,
        "online": agg["online"] or 0,
        "in_person": agg["in_person"] or 0,
        "phone": agg["phone"] or 0,
        "online_pct": round((agg["online"] or 0) / total * 100, 1) if total else 0,
        "in_person_pct": round((agg["in_person"] or 0) / total * 100, 1) if total else 0,
        "phone_pct": round((agg["phone"] or 0) / total * 100, 1) if total else 0,
    }


def tool_get_monthly_trend(months: int = 6) -> dict:
    monthly = Period.objects.filter(
        report_type="monthly", superseded_by__isnull=True
    ).order_by("-period_start")[:months]
    trend = []
    for p in reversed(list(monthly)):
        total = CaseRow.objects.filter(period=p).aggregate(t=Sum("total_cases"))["t"] or 0
        new = CaseRow.objects.filter(period=p, case_type="new").aggregate(t=Sum("total_cases"))["t"] or 0
        fu = CaseRow.objects.filter(period=p, case_type="followup").aggregate(t=Sum("total_cases"))["t"] or 0
        trend.append({
            "period_id": p.id,
            "label": f"{p.period_start} to {p.period_end}",
            "total": total,
            "new": new,
            "followup": fu,
        })
    return {"trend": trend, "count": len(trend)}


def tool_find_anomalies() -> dict:
    monthly = Period.objects.filter(
        report_type="monthly", superseded_by__isnull=True
    ).order_by("period_start")
    data = []
    for p in monthly:
        total = CaseRow.objects.filter(period=p).aggregate(t=Sum("total_cases"))["t"] or 0
        data.append({"period_id": p.id, "label": f"{p.period_start}", "total": total})

    if len(data) < 3:
        return {"anomalies": [], "message": "Need at least 3 periods for anomaly detection."}

    totals = [d["total"] for d in data]
    mean = sum(totals) / len(totals)
    variance = sum((t - mean) ** 2 for t in totals) / len(totals)
    std = variance ** 0.5

    anomalies = []
    for d in data:
        if std > 0:
            z = (d["total"] - mean) / std
            if abs(z) > 1.5:
                direction = "spike" if z > 0 else "drop"
                anomalies.append({
                    "period_id": d["period_id"],
                    "label": d["label"],
                    "total": d["total"],
                    "expected": round(mean),
                    "deviation": round(z, 2),
                    "type": direction,
                })

    return {
        "anomalies": anomalies,
        "stats": {"mean": round(mean), "std": round(std, 1), "periods_analyzed": len(data)},
    }


def tool_generate_report(period_id: int, fmt: str) -> dict:
    """Generate report â€” returns approval-required action."""
    return {
        "action": "generate_report",
        "period_id": period_id,
        "format": fmt,
        "status": "pending_approval",
        "message": f"Ready to generate {fmt.upper()} report for period {period_id}. Click Approve to proceed.",
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TOOL DISPATCHER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

TOOL_MAP = {
    "list_periods": lambda args: tool_list_periods(),
    "get_kpi_summary": lambda args: tool_get_kpi_summary(args["period_id"]),
    "compare_teams": lambda args: tool_compare_teams(args["period_id"]),
    "get_top_concerns": lambda args: tool_get_top_concerns(args["period_id"], args.get("n", 5)),
    "get_gender_breakdown": lambda args: tool_get_gender_breakdown(args["period_id"]),
    "get_session_mode_breakdown": lambda args: tool_get_session_mode_breakdown(args["period_id"]),
    "get_monthly_trend": lambda args: tool_get_monthly_trend(args.get("months", 6)),
    "find_anomalies": lambda args: tool_find_anomalies(),
    "generate_report": lambda args: tool_generate_report(args["period_id"], args["format"]),
}


def execute_tool(name: str, arguments: dict) -> dict:
    fn = TOOL_MAP.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(arguments)
    except Exception as e:
        return {"error": f"Tool {name} failed: {e}", "traceback": traceback.format_exc()}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SYSTEM PROMPT
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

SYSTEM_PROMPT = """You are the Wellness Centre AI Assistant. You help administrators analyze mental health counselling data from an Indian university wellness centre.

You have access to the following tools:
- list_periods: Show all available reporting periods
- get_kpi_summary: Get key metrics for a period
- compare_teams: Compare WC, Team A, YourDost, Myndwell verticals
- get_top_concerns: Top issues students face
- get_gender_breakdown: Gender distribution
- get_session_mode_breakdown: Online vs in-person vs phone
- get_monthly_trend: Case volume trends
- find_anomalies: Detect unusual patterns
- generate_report: Create PPTX/Excel reports (requires user approval)

IMPORTANT RULES:
1. Always call tools to get actual data before making claims. Never fabricate numbers.
2. When analyzing data, provide actionable insights, not just numbers.
3. Be concise but thorough. Use bullet points for readability.
4. When generating reports, always explain what the report will contain and ask for approval.
5. Use professional, empathetic tone â€” this is mental health data.
6. If a tool returns an error, explain it and suggest alternatives.
7. When comparing periods, highlight meaningful changes (not just small fluctuations).
8. Always call list_periods first if you don't know which period ID to use.
"""


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN CHAT HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def chat_completion(messages: list) -> dict:
    """Process a chat request with tool-calling loop.

    Returns a dict with:
      - reply: str (final text response)
      - tool_results: list of {name, arguments, result} for UI display
      - pending_action: dict if a report generation is awaiting approval
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "reply": "AI Assistant is not configured. Please set the OPENROUTER_API_KEY environment variable or create ppt_generator/openrouter_key.txt with your API key.",
            "tool_results": [],
            "pending_action": None,
        }

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    tool_results = []
    pending_action = None
    max_iterations = 8

    for _ in range(max_iterations):
        resp = chat(full_messages, tools=TOOLS, max_tokens=8192)
        if "error" in resp:
            return {"reply": f"Error: {resp['error']}", "tool_results": tool_results, "pending_action": None}

        choice = resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            if not content.strip():
                # Reasoning model exhausted its budget without an answer;
                # summarize the gathered data instead of returning nothing.
                break
            return {"reply": content, "tool_results": tool_results, "pending_action": pending_action}

        # Add assistant message with tool calls to conversation
        full_messages.append(message)

        # Execute each tool call
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = execute_tool(name, args)
            tool_results.append({"name": name, "arguments": args, "result": result})

            # Check for pending approval actions
            if name == "generate_report" and result.get("status") == "pending_approval":
                pending_action = result
                # Feed the tool result back so AI can acknowledge it
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })
            else:
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

    # If we exhausted iterations, get a final text response
    resp = chat(full_messages, max_tokens=8192)
    if "error" not in resp:
        content = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
        if content.strip():
            return {"reply": content, "tool_results": tool_results, "pending_action": pending_action}

    if tool_results:
        names = ", ".join(dict.fromkeys(r["name"] for r in tool_results))
        return {"reply": f"I've gathered the data via {names} — please see the tool results above.",
                "tool_results": tool_results, "pending_action": pending_action}
    return {"reply": "I couldn't generate a response. Please try again.", "tool_results": [], "pending_action": None}


def approve_action(action: dict) -> dict:
    """Execute an approved pending action (e.g. generate report)."""
    if action.get("action") == "generate_report":
        return {"status": "approved", "period_id": action["period_id"], "format": action["format"]}
    return {"status": "unknown_action"}
