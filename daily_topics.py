#!/usr/bin/env python3
"""Daily curiosity feed — 5 random topics with links, sent via Pushover."""

import json
import os
import urllib.request
import urllib.parse

import anthropic

# ── Keys read from environment (set as GitHub Secrets) ───────────────────────
PUSHOVER_USER_KEY  = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_APP_TOKEN = os.environ["PUSHOVER_APP_TOKEN"]
# ANTHROPIC_API_KEY is picked up automatically by the anthropic library

# ── Topics to avoid ──────────────────────────────────────────────────────────
EXCLUDE = "Avoid: current news, politics, elections, sports competitions."


PROMPT = f"""You are a curiosity engine. Today, generate exactly 5 fascinating topics
that feel completely removed from everyday office/tech/business life.
Think: obscure history, deep-sea biology, ancient crafts, materials science,
unusual linguistics, forgotten inventions, extreme geography, etc.

{EXCLUDE}

For each topic return:
- A short punchy title (≤ 8 words)
- One sentence explaining why it's interesting
- A real YouTube URL **or** a real article URL (no paywalls)

Return ONLY valid JSON in this exact shape, nothing else:
[
  {{"title": "...", "why": "...", "url": "https://..."}},
  ...
]
""".strip()


def fetch_topics() -> list[dict]:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": PROMPT}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def pushover_notify(message: str) -> None:
    data = urllib.parse.urlencode({
        "token":   PUSHOVER_APP_TOKEN,
        "user":    PUSHOVER_USER_KEY,
        "title":   "Today's 5 Curiosities",
        "message": message,
    }).encode()
    req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        if result.get("status") != 1:
            print(f"Pushover error: {result}")


def main() -> None:
    print("Fetching today's 5 curiosities…\n")
    topics = fetch_topics()

    for i, t in enumerate(topics, 1):
        print(f"{i}. {t['title']}\n   {t['why']}\n   {t['url']}\n")

    iphone_msg = "\n".join(
        f"{i}. {t['title']}\n{t['url']}" for i, t in enumerate(topics, 1)
    )
    pushover_notify(iphone_msg)
    print("Sent to iPhone.")


if __name__ == "__main__":
    main()
