"""Auto-refine the style brief from the owner's verdicts.

Runs at the end of each sweep but only rewrites the brief every SAVE_INTERVAL
new positive verdicts (approved + too_expensive + purchased). The count at
last update is stored as _brief_last_count in the preferences JSON so it
persists across runs without needing a new DB table.

Uses Sonnet for the rewrite — this is a synthesis task across many examples
that benefits from a stronger model. Cost is negligible (~once a month).
"""
import os
import requests

API_URL = "https://api.anthropic.com/v1/messages"
SCORING_MODEL = "claude-haiku-4-5"       # per-item scoring
BRIEF_MODEL   = "claude-sonnet-4-6"      # brief rewriting (stronger synthesis)
SAVE_INTERVAL = 50    # rewrite brief every N new positive verdicts
MAX_POSITIVES = 60
MAX_NEGATIVES = 30


def maybe_update_brief(db, prefs: dict) -> None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return

    # Count all positive verdicts
    positives = db._get("items", {
        "select": "title,vendor,category,score_reason,status",
        "status": "in.(approved,too_expensive,purchased)",
        "order": "created_at.desc",
        "limit": str(MAX_POSITIVES),
    })
    total_positives = _count_positives(db)
    last_count = int(prefs.get("_brief_last_count", 0))

    if total_positives < SAVE_INTERVAL:
        print(f"  (brief update skipped — {total_positives}/{SAVE_INTERVAL} saves needed)")
        return

    # Only update when we've crossed a new 50-boundary since last run
    if (total_positives // SAVE_INTERVAL) <= (last_count // SAVE_INTERVAL):
        next_update = ((last_count // SAVE_INTERVAL) + 1) * SAVE_INTERVAL
        print(f"  (brief update skipped — {total_positives} saves, next update at {next_update})")
        return

    # Negative signal: human-passed items the AI scored well
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

    # Label positive items by strength of signal
    strong = [i for i in positives if i.get("status") in ("approved", "purchased")]
    medium = [i for i in positives if i.get("status") == "too_expensive"]

    current_brief = prefs.get("style_brief", "")
    prompt = (
        "You are refining a style brief for a personal menswear AI scout. "
        "The scout scores sale items against this brief to surface only items matching the owner's taste.\n\n"
        f"Current brief:\n{current_brief}\n\n"
        f"Items the owner SAVED or BOUGHT (strongest positive signal — {len(strong)} items):\n"
        f"{fmt(strong)}\n\n"
        f"Items marked 'waiting on price' — likes the style, price too high ({len(medium)} items):\n"
        f"{fmt(medium)}\n\n"
        f"Items the owner PASSED on despite a high AI score (negative signal — {len(negatives)} items):\n"
        f"{fmt(negatives)}\n\n"
        "Rewrite the style brief in 3–5 sentences to better capture what this owner actually buys. "
        "Be specific: note preferred cuts, fabrics, colours, collar styles, trouser rises, and brands "
        "that appear in the positives. Note what to avoid from the negatives. "
        "Keep 'MENSWEAR ONLY.' as the opening if present. "
        "Respond with ONLY the updated brief text — no preamble, no explanation."
    )

    print(f"  Rewriting style brief with Sonnet ({total_positives} saves, {len(negatives)} passes)...")
    try:
        r = requests.post(API_URL, timeout=90, headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json={
            "model": BRIEF_MODEL,
            "max_tokens": 400,
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

    # Write updated brief + new count back into preferences
    updated_prefs = dict(prefs)
    updated_prefs["style_brief"] = new_brief
    updated_prefs["_brief_last_count"] = total_positives
    try:
        db._write("patch", "preferences", {"key": "eq.main"}, {"value": updated_prefs})
        print(f"  ✓ Style brief updated (saves: {last_count} → {total_positives})")
        print(f"    {new_brief[:200]}...")
    except Exception as e:
        print(f"  ! could not save updated brief: {e}")


def _count_positives(db) -> int:
    """Total count of positive verdicts in the DB."""
    try:
        # Use HEAD request with count to avoid fetching all rows
        rows = db._get("items", {
            "select": "item_key",
            "status": "in.(approved,too_expensive,purchased)",
            "limit": "2000",
        })
        return len(rows)
    except Exception:
        return 0
