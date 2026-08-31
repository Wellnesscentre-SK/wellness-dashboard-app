"""
OpenRouter AI Client — connects to OpenRouter API for AI-powered analysis.

Endpoint: POST https://openrouter.ai/api/v1/chat/completions
Auth: Bearer token (OPENROUTER_API_KEY env var or config file)

Set your API key:
  - Environment variable: set OPENROUTER_API_KEY=sk-or-...
  - Or create ppt_generator/openrouter_key.txt with your key
"""

import json
import os
import urllib.request
import urllib.error
from time import monotonic


API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "minimax/minimax-m3:free"
# Free-tier models churn quickly (de-listed, rate-limited, or turned paid).
# minimax/m3 returns clean, fast, well-formatted insight text without a
# reasoning chain; the OpenRouter free router ("openrouter/free") is a stable
# catch-all that auto-selects an available model if the specific ones are busy.
MODEL_FALLBACKS = [
    DEFAULT_MODEL,
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]
# Cap the whole AI-insight call so a slow / rate-limited provider can never
# stall the PPT build into a request timeout / "Network Error". Each attempt
# is given only the remaining budget (see chat()), so the total is strictly
# bounded by this value; on exceeding it the caller falls back to rule-based
# insights. Kept small so the PPT always builds in a few seconds.
MAX_TOTAL_SECONDS = 5


def _get_api_key():
    """Get API key from env or file."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key.strip()
    key_file = os.path.join(os.path.dirname(__file__), "openrouter_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    return ""


def chat(messages: list, model: str = None, temperature: float = 0.3,
         max_tokens: int = 2048) -> str:
    """Send a chat completion request to OpenRouter.

    Args:
        messages: list of {"role": "system"/"user"/"assistant", "content": str}
        model: model ID (e.g. "google/gemini-2.0-flash-001")
        temperature: 0.0-1.0
        max_tokens: max response length

    Returns:
        assistant message content string, or "" on error
    """
    api_key = _get_api_key()
    if not api_key:
        return ""

    # Hard budget so a slow / rate-limited provider can never stall the
    # whole PPT build (which would otherwise time out into a "Network Error").
    deadline = monotonic() + MAX_TOTAL_SECONDS
    chain = [model] if model else list(MODEL_FALLBACKS)
    for m in chain:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        # Each attempt may block up to its own timeout, so cap it to the
        # remaining budget to guarantee the total never exceeds MAX_TOTAL_SECONDS.
        result = _chat_once(api_key, m, messages, temperature, max_tokens,
                            timeout=min(20, remaining))
        if result:
            return result
    return ""


def _chat_once(api_key: str, model: str, messages: list, temperature: float,
               max_tokens: int, timeout: int = 20) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://wellness-centre.local",
            "X-Title": "Wellness Centre PPT Generator",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            if not content:
                print(f"[OpenRouter] model {model} returned empty content")
                return ""
            return content.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"[OpenRouter Error] HTTP {e.code}: {body}")
        if e.code in (402, 429, 404, 408):
            return ""  # try next model in the fallback chain
        return ""
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, OSError) as e:
        print(f"[OpenRouter Error] {e}")
        return ""


def is_available() -> bool:
    """Check if OpenRouter API key is configured."""
    return bool(_get_api_key())
