"""Auto-refine the style brief from the owner's verdicts.

Called at the end of each sweep. Looks at saved/too_expensive items as
positive signals and human-rejected items as negative signals, then asks
Claude Haiku to rewrite the brief to better reflect actual taste.

Requires at least MIN_POSITIVES saved items before updating — avoids
thrashing the brief when there's not enough signal.
"""
import json
import os
import time
import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5"
MIN_POSITIVES = 10   # don't update without at least this many saves
MAX_POSITIVES = 40   # cap to keep prompt size reasonable
MAX_NEGATIVES = 20


def maybe_update_brief(db, prefs: dict) -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return

    # Positive signal: want it, waiting on price, bought it
    positives = db._get("items", {
        "select": "title,vendor,category,score_reason",
        "status": "in.(approved,too_expensive,purchased)",
        "order": "created_at.desc",
        "limit": str(MAX_POSITIVES),
    })
    if len(positives) < MIN_POSITIVES:
        print(f"  (brief update skipped — only {len(positives)} saved items, need {MIN_POSITIVES})")
        return

    # Negative signal: items the owner passed on that the AI liked (score >= threshold)
    threshold = prefs.get("score_threshold", 6)
    negatives = db._get("items", {
        "select": "title,vendor,category,score_reason",
        "status": "eq.rejected",
        "score": f"gte.{threshold}",
        "order": "created_at.desc",
        "limit": str(MAX_NEGATIVES),
    })

    def fmt(items):
        return "\n".join(
            f"- {i['title']} [{i.get('category','')}] ({i.get('vendor','')}) — {i.get('score_reason','')}"
            for i in items
        ) or "(none yet)"

    current_brief = prefs.get("style_brief", "")
    prompt = (
        f"You are refining a style brief for a personal menswear AI scout.\n\n"
        f"Current brief:\n{current_brief}\n\n"
        f"Items the owner SAVED or marked 'waiting on price' (positive — these match his taste):\n"
        f"{fmt(positives)}\n\n"
        f"Items the owner PASSED on despite a high AI score (negative — these don't fit):\n"
        f"{fmt(negatives)}\n\n"
        "Rewrite the style brief in 3–5 sentences to better capture what this owner actually buys. "
        "Be specific about cuts, colours, fabrics, and brands that appear in the positives. "
        "Note what to avoid based on the negatives. "
        "Keep 'MENSWEAR ONLY.' as the opening if present. "
        "Respond with ONLY the updated brief text, nothing else."
    )

    try:
        r = requests.post(API_URL, timeout=60, headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json={
            "model": MODEL,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        })
        r.raise_for_status()
        new_brief = "".join(
            b.get("text", "") for b in r.json().get("content", [])
            if b.get("type") == "text"
        ).strip()
    except Exception as e:
        print(f"  ! brief update failed: {e}")
        return

    if not new_brief or len(new_brief) < 40:
        print("  ! brief update returned empty response, skipping")
        return

    if new_brief == current_brief:
        print("  (brief unchanged)")
        return

    # Write updated brief back into preferences
    updated_prefs = dict(prefs)
    updated_prefs["style_brief"] = new_brief
    try:
        db._write("patch", "preferences", {"key": "eq.main"}, {"value": updated_prefs})
        print(f"  ✓ Style brief updated from {len(positives)} saves / {len(negatives)} passes")
        print(f"    New brief: {new_brief[:120]}...")
    except Exception as e:
        print(f"  ! could not save updated brief: {e}")
