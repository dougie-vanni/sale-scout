"""Score candidate items against the style brief using Claude Haiku.

Falls back to a neutral pass-through score if no API key is configured,
so the pipeline still works (just noisier) in free mode.
"""
import json
import os
import time
import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5"


def _prompt(c: dict, brief: str) -> list:
    content = []
    if c.get("image"):
        content.append({"type": "image", "source": {"type": "url", "url": c["image"]}})
    content.append({"type": "text", "text": (
        f"Style brief:\n{brief}\n\n"
        f"Item: {c['title']}\nBrand: {c['vendor']}\nType: {c['product_type']}\n"
        f"Tags: {c['tags'][:300]}\n\n"
        "Score 0-10 how well this item fits the style brief (10 = perfect fit). "
        "Judge the image if provided: fit/silhouette, pattern loudness, colour. "
        'Respond with ONLY JSON: {"score": <int>, "reason": "<max 12 words>"}'
    )})
    return [{"role": "user", "content": content}]


def score_item(c: dict, brief: str) -> tuple[int, str] | None:
    """Returns (score, reason), or None if scoring failed (caller should
    skip the item so it gets scored on a later run, NOT surface it)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return 6, "no api key: rule-pass only"
    last_err = "unknown"
    for attempt in range(4):
        try:
            r = requests.post(API_URL, timeout=60, headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }, json={
                "model": MODEL,
                "max_tokens": 100,
                "messages": _prompt(c, brief),
            })
            if r.status_code in (429, 500, 502, 503, 529):
                wait = float(r.headers.get("retry-after", 2 ** (attempt + 1)))
                last_err = f"HTTP {r.status_code}"
                time.sleep(min(wait, 60))
                continue
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", [])
                           if b.get("type") == "text")
            text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return int(data["score"]), str(data.get("reason", ""))[:120]
        except Exception as e:
            last_err = str(e)
            time.sleep(2 ** (attempt + 1))
    print(f"  ! scorer failed after retries ({c['title'][:40]}): {last_err}")
    return None
