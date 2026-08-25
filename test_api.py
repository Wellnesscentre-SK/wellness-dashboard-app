import json, urllib.request, urllib.error

key = open(r"C:\Users\Wellness\Desktop\admin dashboard\ppt_generator\openrouter_key.txt").read().strip()

models = [
    "google/gemini-2.0-flash-001",
    "google/gemini-2.0-flash",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-preview",
    "google/gemini-flash-1.5",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-r1",
    "openai/gpt-4o-mini",
    "anthropic/claude-3-haiku",
]

for model in models:
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "Say hi in 5 words"}], "max_tokens": 30}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://test.local",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            content = data["choices"][0]["message"]["content"]
            print(f"  OK: {model} -> {content[:50]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"  HTTP {e.code}: {model} -> {body}")
    except Exception as e:
        print(f"  ERR: {model} -> {e}")
