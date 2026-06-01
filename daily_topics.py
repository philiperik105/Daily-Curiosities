#!/usr/bin/env python3
"""Daily curiosity feed — generates an HTML page + sends Pushover notification."""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime

import anthropic

# ── Keys read from environment (set as GitHub Secrets) ───────────────────────
PUSHOVER_USER_KEY  = os.environ["PUSHOVER_USER_KEY"]
PUSHOVER_APP_TOKEN = os.environ["PUSHOVER_APP_TOKEN"]
PAGES_URL          = os.environ.get("PAGES_URL", "")

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
- A single relevant emoji

Return ONLY valid JSON in this exact shape, nothing else:
[
  {{"title": "...", "why": "...", "emoji": "🌊"}},
  ...
]
""".strip()


def search_urls(title: str) -> tuple[str, str]:
    q = urllib.parse.quote(title)
    yt  = f"https://www.youtube.com/search?query={q}"
    art = f"https://www.google.com/search?q={q}"
    return yt, art


def fetch_topics() -> list[dict]:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": PROMPT}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


GRADIENTS = [
    "linear-gradient(135deg, #1a1a2e, #16213e)",
    "linear-gradient(135deg, #0d1b2a, #1b4332)",
    "linear-gradient(135deg, #2d1b4e, #1a0533)",
    "linear-gradient(135deg, #1c1c1c, #3a1c1c)",
    "linear-gradient(135deg, #0a2342, #1a3a5c)",
]


def build_html(topics: list[dict], date_str: str) -> str:
    cards = ""
    for i, t in enumerate(topics, 1):
        emoji    = t.get("emoji", "🔍")
        gradient = GRADIENTS[(i - 1) % len(GRADIENTS)]
        yt_url, art_url = search_urls(t["title"])

        cards += f"""
        <div class="card">
            <div class="thumb" style="background: {gradient};">
                <span class="emoji">{emoji}</span>
            </div>
            <div class="info">
                <div class="num">{i}</div>
                <h2>{t['title']}</h2>
                <p>{t['why']}</p>
                <div class="btns">
                    <a href="{yt_url}" target="_blank" class="btn yt">▶ YouTube</a>
                    <a href="{art_url}" target="_blank" class="btn art">📄 Article</a>
                </div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Today's Curiosities — {date_str}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f0f0f;
    color: #f0f0f0;
    padding: 20px;
    max-width: 680px;
    margin: 0 auto;
  }}
  header {{
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #333;
  }}
  header h1 {{ font-size: 1.4rem; font-weight: 700; }}
  header p  {{ font-size: 0.85rem; color: #888; margin-top: 4px; }}
  .card {{
    display: flex;
    gap: 14px;
    background: #1a1a1a;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 14px;
  }}
  .thumb {{
    flex-shrink: 0;
    width: 100px;
    min-height: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .emoji {{ font-size: 2.8rem; }}
  .info {{
    padding: 12px 14px 12px 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .num {{ font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
  h2   {{ font-size: 0.95rem; font-weight: 600; line-height: 1.3; }}
  p    {{ font-size: 0.8rem; color: #aaa; line-height: 1.4; }}
  .btns {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }}
  .btn {{
    font-size: 0.75rem;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 20px;
    text-decoration: none;
    white-space: nowrap;
  }}
  .yt  {{ background: #ff0000; color: #fff; }}
  .art {{ background: #2a2a2a; color: #ccc; border: 1px solid #444; }}
</style>
</head>
<body>
<header>
  <h1>Today's Curiosities</h1>
  <p>{date_str} — pick YouTube or Article</p>
</header>
{cards}
</body>
</html>"""


def pushover_notify(message: str, url: str) -> None:
    data = urllib.parse.urlencode({
        "token":     PUSHOVER_APP_TOKEN,
        "user":      PUSHOVER_USER_KEY,
        "title":     "Today's 5 Curiosities",
        "message":   message,
        "url":       url,
        "url_title": "Open all 5 →",
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
        print(f"{i}. {t['title']}\n   {t['why']}\n")

    date_str = datetime.utcnow().strftime("%B %d, %Y")
    html = build_html(topics, date_str)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html written.")

    teaser = " · ".join(t["title"] for t in topics[:3]) + "…"
    pushover_notify(teaser, PAGES_URL)
    print("Sent to iPhone.")


if __name__ == "__main__":
    main()
