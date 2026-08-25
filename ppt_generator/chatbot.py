"""
Wellness Centre AI Chatbot — interactive CLI for data analysis.

Powered by OpenRouter API. Ask questions about wellness data,
get AI-powered analysis, and generate PPT reports.

Usage:
    cd ppt_generator
    python chatbot.py

Commands:
    /analyze <week|month|year>  — generate report with AI insights
    /ask <question>             — ask anything about the data
    /charts                     — get AI chart recommendations
    /key <api-key>              — set OpenRouter API key
    /help                       — show help
    /quit                       — exit
"""

import sys
import io
import os
import json
import readline  # enables arrow key support in input()

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from openrouter_client import chat, is_available, _get_api_key

# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA (same as runner.py)
# ═══════════════════════════════════════════════════════════════════════════════

WEEKLY_DATA = {
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

MONTHLY_DATA = {
    "label": "JULY 2026",
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

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

chat_history = [
    {"role": "system", "content": """You are an expert wellness data analyst for IIT Madras Wellness Centre.
You have access to weekly and monthly wellness data. Answer questions about the data,
provide analysis, and suggest insights for PPT reports.

Available data:
""" + json.dumps({"weekly": WEEKLY_DATA, "monthly": MONTHLY_DATA}, indent=2) + """

Be specific with numbers and percentages. Give actionable recommendations."""},
]


def set_api_key(key):
    """Save API key to file."""
    key_file = os.path.join(os.path.dirname(__file__), "openrouter_key.txt")
    with open(key_file, "w") as f:
        f.write(key.strip())
    print(f"  API key saved to {key_file}")


def ask_ai(question):
    """Send question to OpenRouter and print response."""
    if not is_available():
        print("  No API key configured. Use /key <your-api-key> to set one.")
        print("  Get a free key at: https://openrouter.ai/keys")
        return

    chat_history.append({"role": "user", "content": question})
    print("  Thinking...", end="", flush=True)

    response = chat(chat_history, temperature=0.3, max_tokens=2048)

    if response:
        chat_history.append({"role": "assistant", "content": response})
        print(f"\r  AI: {response}")
    else:
        print("\r  [Error] No response from OpenRouter. Check your API key.")


def cmd_analyze(args):
    """Generate a PPT report with AI insights."""
    from config import combine_verticals, VERT_KEYS
    from normal_week import build as build_week
    from normal_monthly import build as build_month
    from weekly import build as build_comp_week

    period_type = args[0].lower() if args else "week"

    if period_type in ("week", "w"):
        data = WEEKLY_DATA
        output = "output/Chatbot_Weekly_Report.pptx"
        print("  Generating weekly report with AI insights...")
        ppt = build_week(data)
    elif period_type in ("month", "m"):
        data = MONTHLY_DATA
        output = "output/Chatbot_Monthly_Report.pptx"
        print("  Generating monthly report with AI insights...")
        ppt = build_month(data)
    elif period_type in ("compare", "c"):
        print("  Generating weekly comparison report...")
        data_a = {**WEEKLY_DATA, "label": "15th to 21st July 2026",
                  "new": 12, "followup": 85, "grand": 97}
        data_b = WEEKLY_DATA
        output = "output/Chatbot_Comparison_Report.pptx"
        ppt = build_comp_week(data_a, data_b)
    else:
        print(f"  Unknown type: {period_type}. Use 'week', 'month', or 'compare'.")
        return

    os.makedirs("output", exist_ok=True)
    with open(output, "wb") as f:
        f.write(ppt)
    print(f"  Saved: {output} ({len(ppt):,} bytes)")


def cmd_charts():
    """Get AI chart recommendations for the data."""
    if not is_available():
        print("  No API key configured. Use /key <your-api-key> to set one.")
        return

    prompt = """Based on this wellness data, recommend the best 5 charts/visualizations
for a dean's report. For each, specify: chart type, what data to show, and why.

Data:
""" + json.dumps(MONTHLY_DATA, indent=2)

    chat_history.append({"role": "user", "content": prompt})
    print("  Getting chart recommendations...", end="", flush=True)

    response = chat(chat_history, temperature=0.3, max_tokens=1024)
    if response:
        chat_history.append({"role": "assistant", "content": response})
        print(f"\r  AI:\n{response}")
    else:
        print("\r  [Error] No response from OpenRouter.")


def cmd_help():
    print("""
  Wellness Centre AI Chatbot
  ==========================

  /analyze <type>    Generate PPT report with AI insights
                     Types: week, month, compare

  /ask <question>    Ask anything about the wellness data

  /charts            Get AI chart recommendations

  /key <api-key>     Set OpenRouter API key
                     Get one free at: https://openrouter.ai/keys

  /history           Show chat history

  /clear             Clear chat history

  /help              Show this help

  /quit              Exit chatbot

  Just type your question to chat with AI about the data!
""")


def main():
    print("=" * 60)
    print("  WELLNESS CENTRE AI CHATBOT")
    print("  Powered by OpenRouter AI")
    print("=" * 60)

    if is_available():
        print("  API key: Configured")
    else:
        print("  API key: NOT configured")
        print("  Set one with: /key <your-api-key>")
        print("  Get free key: https://openrouter.ai/keys")
    print("  Type /help for commands, or just ask a question!\n")

    while True:
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not user_input:
            continue

        # Commands
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []

            if cmd in ("/quit", "/exit", "/q"):
                print("  Goodbye!")
                break
            elif cmd == "/help":
                cmd_help()
            elif cmd == "/key":
                if args:
                    set_api_key(args[0])
                else:
                    print("  Usage: /key <your-api-key>")
            elif cmd == "/analyze":
                cmd_analyze(args)
            elif cmd == "/charts":
                cmd_charts()
            elif cmd == "/history":
                print("  Chat history:")
                for msg in chat_history[1:]:  # skip system
                    role = msg["role"].upper()
                    content = msg["content"][:200]
                    print(f"    [{role}] {content}...")
            elif cmd == "/clear":
                chat_history.clear()
                chat_history.append({
                    "role": "system",
                    "content": chat_history[0]["content"] if chat_history else ""
                })
                print("  History cleared.")
            else:
                print(f"  Unknown command: {cmd}. Type /help for commands.")
            continue

        # Free-form question
        ask_ai(user_input)


if __name__ == "__main__":
    main()
