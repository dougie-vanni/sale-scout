"""Dumb-but-fast rule filters that run before any AI scoring."""
import re


def _haystack(c: dict) -> str:
    return " ".join([c["title"], c["product_type"], c["tags"], c["variant_title"]]).lower()


def categorize(c: dict, prefs: dict) -> str | None:
    hay = _haystack(c)
    # order matters: shoes' "oxford shoe" must not lose to shirts' "oxford" etc.
    # check belts/shoes/outerwear before shirts to disambiguate
    order = ["belts", "shoes", "outerwear", "trousers", "sweaters", "shirts"]
    for cat in order:
        for kw in prefs["categories"][cat]["keywords"]:
            if kw in hay:
                return cat
    return None


def _norm_tokens(s: str) -> set[str]:
    return set(re.split(r"[\s/,\-]+", s.upper().strip()))


def size_matches(c: dict, cat: str, prefs: dict) -> bool:
    wanted = {w.upper() for w in prefs["sizes"].get(cat, [])}
    tokens = _norm_tokens(c["variant_title"])
    # whole variant string match too (e.g. "16.5/35")
    return bool(wanted & tokens) or c["variant_title"].upper().strip() in wanted


def hard_excluded(c: dict, cat: str, prefs: dict) -> str | None:
    hay = _haystack(c)
    hx = prefs["hard_excludes"]
    for kw in hx.get("gender_keywords", []):
        if re.search(rf"\b{re.escape(kw)}\b", hay):
            return f"gender:{kw}"
    for kw in hx["fit_keywords"]:
        if kw in hay:
            return f"fit:{kw}"
    for kw in hx["pattern_keywords"]:
        if kw in hay:
            return f"pattern:{kw}"
    for kw in hx["color_keywords_by_category"].get(cat, []):
        if re.search(rf"\b{re.escape(kw)}\b", hay):
            return f"color:{kw}"
    return None


def passes_rules(c: dict, prefs: dict) -> tuple[bool, str, str]:
    """Returns (keep, category, reason)."""
    cat = categorize(c, prefs)
    if not cat:
        return False, "", "no category"
    tier = prefs["categories"][cat]["tier"]
    threshold = prefs["discount_thresholds"][tier]
    if c["discount_pct"] < threshold:
        return False, cat, f"discount {c['discount_pct']:.0%} < {threshold:.0%}"
    if not size_matches(c, cat, prefs):
        return False, cat, "size unavailable"
    ex = hard_excluded(c, cat, prefs)
    if ex:
        return False, cat, f"excluded {ex}"
    return True, cat, "ok"
