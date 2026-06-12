"""Score candidate items against the style brief using Claude Haiku.

Falls back to a neutral pass-through score if no API key is configured,
so the pipeline still works (just noisier) in free mode.
"""
import json
import os
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


def score_item(c: dict, brief: str) -> tuple[int, str]:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return 6, "no api key: rule-pass only"
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
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", [])
                       if b.get("type") == "text")
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        return int(data["score"]), str(data.get("reason", ""))[:120]
    except Exception as e:
        print(f"  ! scorer error ({c['title'][:40]}): {e}")
        return 6, "scorer error: rule-pass only"
