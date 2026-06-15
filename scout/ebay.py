"""eBay Browse API integration for SaleScout.

Each eBay retailer config entry has:
  type: "ebay"
  marketplace: "EBAY_AU"          # eBay marketplace ID
  ebay_keywords: "polo ralph lauren brooks brothers pendleton"
  ebay_sizes: "L,Large,XL,X-Large"   # optional, comma-separated

Requires GitHub secrets EBAY_APP_ID and EBAY_CERT_ID (Production keys from
developer.ebay.com — App ID and Cert ID respectively).
"""
import base64
import os
import time
import requests

OAUTH_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE      = "https://api.ebay.com/oauth/api_scope"
PAGE_LIMIT = 200   # eBay Browse API max per request

_token_cache: dict = {"token": None, "expires": 0.0}


def _get_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires"] - 60:
        return _token_cache["token"]
    app_id  = os.environ["EBAY_APP_ID"]
    cert_id = os.environ["EBAY_CERT_ID"]
    creds   = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
    r = requests.post(OAUTH_URL, timeout=30, headers={
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data=f"grant_type=client_credentials&scope={SCOPE}")
    r.raise_for_status()
    data = r.json()
    _token_cache["token"]   = data["access_token"]
    _token_cache["expires"] = time.time() + int(data.get("expires_in", 7200))
    return _token_cache["token"]


def _extract_aspects(item: dict) -> dict:
    """Flatten localizedAspects list to a lowercase key → value dict."""
    return {
        a["localizedName"].lower(): a["localizedValue"]
        for a in item.get("localizedAspects", [])
    }


def search_candidates(retailer: dict) -> list[dict]:
    """Search eBay for used menswear matching this retailer's keyword profile."""
    try:
        token = _get_token()
    except Exception as e:
        print(f"  ! eBay auth failed: {e}")
        return []

    marketplace = retailer.get("marketplace", "EBAY_AU")
    keywords    = retailer.get("ebay_keywords", "")
    sizes_raw   = retailer.get("ebay_sizes", "")

    # Build size filter string for the search query (not aspect_filter — that
    # requires a specific category_id; keyword + condition is sufficient to start)
    size_suffix = ""
    if sizes_raw:
        # Append the most common size token to the keyword to narrow results
        first_size = sizes_raw.split(",")[0].strip()
        size_suffix = f" {first_size}"

    params: dict = {
        "q":      keywords + size_suffix,
        "filter": "conditions:{USED|VERY_GOOD|GOOD|ACCEPTABLE}",
        "limit":  str(PAGE_LIMIT),
        "sort":   "newlyListed",
    }

    headers = {
        "Authorization":           f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace,
        "Content-Type":            "application/json",
    }

    out = []
    offset = 0
    while True:
        params["offset"] = str(offset)
        try:
            r = requests.get(BROWSE_URL, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            body  = r.json()
            items = body.get("itemSummaries", [])
        except Exception as e:
            print(f"  ! eBay search failed (offset {offset}): {e}")
            break

        for item in items:
            try:
                price = float(item.get("price", {}).get("value", 0))
                if not price:
                    continue
                aspects  = _extract_aspects(item)
                size     = (aspects.get("clothing size")
                            or aspects.get("size")
                            or aspects.get("shirt size")
                            or aspects.get("trouser size")
                            or "")
                brand    = (aspects.get("brand") or "")
                image    = item.get("image", {}).get("imageUrl", "")
                out.append({
                    "retailer_id":   retailer["id"],
                    "retailer_name": retailer["name"],
                    "region":        retailer.get("region", "AU"),
                    "currency":      retailer.get("currency", "AUD"),
                    "product_id":    item["itemId"],
                    "variant_id":    item["itemId"],
                    "handle":        item["itemId"],
                    "title":         item.get("title", ""),
                    "vendor":        brand,
                    "product_type":  "",
                    "tags":          "",
                    "variant_title": size,
                    "price":         price,
                    "compare_at":    price,
                    "discount_pct":  0.0,
                    "url":           item.get("itemWebUrl", ""),
                    "image":         image,
                    "vintage":       True,
                })
            except Exception:
                continue

        total = int(body.get("total", 0))
        offset += PAGE_LIMIT
        if offset >= min(total, 1000):   # cap at 1000 items per search
            break
        time.sleep(0.5)

    return out
