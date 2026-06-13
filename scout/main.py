"""SaleScout daily run: fetch -> filter -> dedup -> score -> landed cost -> store."""
import json
import pathlib
import sys

from . import shopify, filters, scorer, landed
from .db import DB

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name: str) -> dict:
    return json.loads((ROOT / "config" / name).read_text())


def item_key(c: dict) -> str:
    return f"{c['retailer_id']}:{c['product_id']}:{c['variant_id']}"


def main():
    db = DB()
    db_prefs = db.get_preferences()
    prefs = db_prefs or load("preferences.json")
    registry = db.get_retailers() or load("retailers.json")["retailers"]
    print(f"config source: {'database' if db_prefs else 'repo files'}")
    db.set_flag("stop_requested", False)  # clear any stale stop request
    db.set_sweep_status("running", "starting")
    muted = db.muted_retailers()
    seen = db.existing_items()
    print(f"DB: {len(seen)} known items, {len(muted)} muted retailers")

    new_count = 0
    scored = 0
    stopped = False
    max_scores = int(prefs.get("max_scores_per_run", 0))  # 0 = unlimited
    for retailer in registry:
        if stopped or db.get_flag("stop_requested"):
            stopped = True
            break
        if not retailer.get("enabled") or retailer["id"] in muted:
            continue
        if retailer["type"] != "shopify":
            continue  # custom scrapers: future work
        print(f"-> {retailer['name']}")
        db.set_sweep_status("running", retailer["name"])
        try:
            candidates = shopify.sale_candidates(retailer)
        except Exception as e:
            print(f"  ! retailer failed entirely: {e}")
            continue
        allow = [a.strip().lower() for a in (retailer.get("vendor_allow") or "").split(",") if a.strip()]
        if allow:
            candidates = [c for c in candidates
                          if c.get("vendor", "").strip().lower() in allow]
        print(f"   {len(candidates)} on-sale variants"
              + (f" (after brand allowlist: {len(allow)} brands)" if allow else ""))

        kept = []
        for c in candidates:
            ok, cat, reason = filters.passes_rules(c, prefs)
            if ok:
                c["category"] = cat
                kept.append(c)
        print(f"   {len(kept)} pass rules")

        for c in kept:
            key = item_key(c)
            prior = seen.get(key)
            if prior:
                status = prior["status"]
                drop_needed = float(prior["price"]) * (1 - prefs["resurface_drop_pct"])
                if status == "too_expensive" and c["price"] <= drop_needed:
                    pass  # resurface at the new lower price
                else:
                    continue  # already handled

            if max_scores and scored >= max_scores:
                continue  # cap hit: leave unscored for the next run
            if not shopify.variant_available(c, retailer):
                continue  # feed said in stock, product page says sold out
            if scored and scored % 20 == 0 and db.get_flag("stop_requested"):
                stopped = True
                break
            scored += 1
            result = scorer.score_item(c, prefs["style_brief"])
            if result is None:
                continue  # scoring failed; leave for a future run
            score, reason = result
            if score < prefs["score_threshold"]:
                # remember rejection so we never pay to score it again
                db.upsert_item({**_row(c, retailer, prefs),
                                "status": "auto_rejected",
                                "score": score, "score_reason": reason})
                seen[item_key(c)] = {"status": "auto_rejected", "price": c["price"]}
                continue

            row = _row(c, retailer, prefs)
            row.update({"status": "new", "score": score, "score_reason": reason})
            db.upsert_item(row)
            seen[key] = {"status": "new", "price": c["price"]}
            new_count += 1
            print(f"   + [{score}] {c['title']} ({c['variant_title']}) "
                  f"{c['discount_pct']:.0%} off")

    if stopped:
        db.set_flag("stop_requested", False)
        db.set_sweep_status("stopped",
            f"stopped by you; {new_count} new, {scored} scored")
        print("STOPPED by website request; remainder deferred to next run.")
    if max_scores and scored >= max_scores:
        print(f"NOTE: hit max_scores_per_run={max_scores}; remainder deferred to next run.")
    if not stopped:
        deferred = " (backlog remaining)" if max_scores and scored >= max_scores else ""
        db.set_sweep_status("idle", f"{new_count} new, {scored} scored{deferred}")
    print(f"Done. {new_count} new items surfaced ({scored} items scored this run).")


def _row(c: dict, retailer: dict, prefs: dict) -> dict:
    costs = landed.landed(c, retailer, prefs)
    return {
        "item_key": item_key(c),
        "retailer_id": c["retailer_id"],
        "retailer_name": c["retailer_name"],
        "region": c["region"],
        "category": c["category"],
        "title": c["title"],
        "vendor": c["vendor"],
        "variant_title": c["variant_title"],
        "currency": c["currency"],
        "price": c["price"],
        "compare_at": c["compare_at"],
        "discount_pct": c["discount_pct"],
        "url": c["url"],
        "image": c["image"],
        **costs,
    }


if __name__ == "__main__":
    sys.exit(main())
