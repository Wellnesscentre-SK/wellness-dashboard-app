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


API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"
# Free-tier models are individually rate-limited; fall through on 402/429/404.
MODEL_FALLBACKS = [
    DEFAULT_MODEL,
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
]


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

    chain = [model] if model else list(MODEL_FALLBACKS)
    for m in chain:
        result = _chat_once(api_key, m, messages, temperature, max_tokens)
        if result:
            return result
    return ""


def _chat_once(api_key: str, model: str, messages: list, temperature: float,
               max_tokens: int) -> str:
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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
