#!/usr/bin/env python3
"""Daily curiosity feed — generates an HTML page + sends Pushover notification."""

import base64
import json
import os
import re
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
- A real YouTube URL (preferred) or a real article URL (no paywalls)

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


def youtube_id(url: str) -> str | None:
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_thumbnail_b64(vid: str) -> str | None:
    """Download YouTube thumbnail and return as base64 data URI."""
    for quality in ["maxresdefault", "hqdefault", "mqdefault"]:
        try:
            url = f"https://img.youtube.com/vi/{vid}/{quality}.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                if len(data) > 1000:  # skip tiny placeholder images
                    b64 = base64.b64encode(data).decode()
                    return f"data:image/jpeg;base64,{b64}"
        except Exception:
            continue
    return None


def build_html(topics: list[dict], date_str: str) -> str:
    cards = ""
    for i, t in enumerate(topics, 1):
        vid = youtube_id(t["url"])
        if vid:
            b64 = fetch_thumbnail_b64(vid)
            if b64:
                img_html = f'<img src="{b64}" alt="{t["title"]}">'
            else:
                img_html = f'<div class="placeholder">▶</div>'
        else:
            img_html = f'<div class="placeholder">#{i}</div>'

        cards += f"""
        <a class="card" href="{t['url']}" target="_blank">
            <div class="thumb">{img_html}</div>
            <div class="info">
                <div class="num">{i}</div>
                <h2>{t['title']}</h2>
                <p>{t['why']}</p>
            </div>
        </a>"""

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
    text-decoration: none;
    color: inherit;
    transition: background 0.15s;
  }}
  .card:hover {{ background: #242424; }}
  .thumb {{
    flex-shrink: 0;
    width: 130px;
    height: 90px;
    overflow: hidden;
    background: #333;
  }}
  .thumb img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .placeholder {{
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    color: #555;
    font-weight: 700;
  }}
  .info {{
    padding: 12px 14px 12px 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 5px;
  }}
  .num {{ font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
  h2   {{ font-size: 0.95rem; font-weight: 600; line-height: 1.3; }}
  p    {{ font-size: 0.8rem; color: #aaa; line-height: 1.4; }}
</style>
</head>
<body>
<header>
  <h1>Today's Curiosities</h1>
  <p>{date_str} — tap any card to explore</p>
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
        print(f"{i}. {t['title']}\n   {t['why']}\n   {t['url']}\n")

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
