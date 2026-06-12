"""Probe the retailer registry: which sites expose a working Shopify feed?

Run locally or via the manual GitHub Actions trigger:
    python -m scout.probe
"""
import json
import pathlib
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; SaleScout/1.0; personal sale tracker)"}


def probe(retailer: dict) -> str:
    url = f"{retailer['base_url'].rstrip('/')}/products.json"
    try:
        r = requests.get(url, params={"limit": 1}, headers=UA, timeout=20)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        products = r.json().get("products")
        if products is None:
            return "200 but not a Shopify feed"
        return f"OK ({'has products' if products else 'empty page 1'})"
    except Exception as e:
        return f"FAIL: {type(e).__name__}"


def main():
    registry = json.loads((ROOT / "config" / "retailers.json").read_text())["retailers"]
    print(f"{'retailer':<24}{'type':<10}result")
    print("-" * 60)
    for r in registry:
        result = probe(r) if r["type"] == "shopify" else "(custom, skipped)"
        print(f"{r['name']:<24}{r['type']:<10}{result}")


if __name__ == "__main__":
    main()
