"""Fetch sale candidates from Shopify storefront /products.json feeds."""
import time
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; SaleScout/1.0; personal sale tracker)"}
PAGE_LIMIT = 250
MAX_PAGES = 20


def fetch_products(base_url: str) -> list[dict]:
    """Page through a Shopify store's public products feed."""
    products = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{base_url.rstrip('/')}/products.json"
        try:
            r = requests.get(url, params={"limit": PAGE_LIMIT, "page": page},
                             headers=UA, timeout=30)
            r.raise_for_status()
            batch = r.json().get("products", [])
        except Exception as e:
            print(f"  ! fetch failed p{page} {base_url}: {e}")
            break
        if not batch:
            break
        products.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
        time.sleep(1)  # be polite
    return products


def sale_candidates(retailer: dict) -> list[dict]:
    """Normalize on-sale, in-stock variants into candidate dicts."""
    out = []
    for p in fetch_products(retailer["base_url"]):
        image = (p.get("images") or [{}])[0].get("src", "")
        url = f"{retailer['base_url'].rstrip('/')}/products/{p.get('handle','')}"
        tags = " ".join(p.get("tags", [])) if isinstance(p.get("tags"), list) else str(p.get("tags", ""))
        for v in p.get("variants", []):
            try:
                price = float(v.get("price") or 0)
                compare = float(v.get("compare_at_price") or 0)
            except (TypeError, ValueError):
                continue
            if not (compare > price > 0):
                continue  # not on sale
            if v.get("available") is False:
                continue
            out.append({
                "retailer_id": retailer["id"],
                "retailer_name": retailer["name"],
                "region": retailer["region"],
                "currency": retailer["currency"],
                "product_id": str(p.get("id")),
                "variant_id": str(v.get("id")),
                "handle": p.get("handle", ""),
                "title": p.get("title", ""),
                "vendor": p.get("vendor", ""),
                "product_type": p.get("product_type", ""),
                "tags": tags,
                "variant_title": v.get("title", ""),
                "price": price,
                "compare_at": compare,
                "discount_pct": round(1 - price / compare, 3),
                "url": url,
                "image": image,
            })
    return out


_avail_cache: dict = {}


def variant_available(c: dict, retailer: dict) -> bool:
    """Verify stock via /products/<handle>.js — products.json often omits
    the 'available' field, silently passing sold-out variants."""
    ck = (retailer["id"], c.get("handle", ""))
    if ck not in _avail_cache:
        url = f"{retailer['base_url'].rstrip('/')}/products/{c.get('handle','')}.js"
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            _avail_cache[ck] = {str(v.get("id")): bool(v.get("available", True))
                                for v in r.json().get("variants", [])}
            time.sleep(0.25)  # be polite
        except Exception:
            _avail_cache[ck] = None  # endpoint unavailable: don't drop items
    m = _avail_cache[ck]
    if m is None:
        return True
    return m.get(c["variant_id"], False)
