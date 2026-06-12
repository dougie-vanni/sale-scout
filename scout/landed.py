"""Convert prices to AUD landed cost: FX + per-retailer shipping estimate + GST."""
import requests

_rates_cache: dict = {}


def fx_to_aud(amount: float, currency: str) -> float:
    if currency == "AUD":
        return amount
    if currency not in _rates_cache:
        try:
            r = requests.get("https://api.frankfurter.app/latest",
                             params={"from": currency, "to": "AUD"}, timeout=20)
            r.raise_for_status()
            _rates_cache[currency] = r.json()["rates"]["AUD"]
        except Exception as e:
            print(f"  ! FX fetch failed for {currency}: {e}; using rough fallback")
            fallback = {"USD": 1.55, "GBP": 1.95, "CAD": 1.12, "JPY": 0.0105, "EUR": 1.65}
            _rates_cache[currency] = fallback.get(currency, 1.0)
    return amount * _rates_cache[currency]


def shipping_aud(retailer: dict) -> float:
    if "shipping_aud" in retailer:
        return float(retailer["shipping_aud"])
    return fx_to_aud(float(retailer.get("shipping_usd", 35)), "USD")


def landed(c: dict, retailer: dict, prefs: dict) -> dict:
    price_aud = fx_to_aud(c["price"], c["currency"])
    compare_aud = fx_to_aud(c["compare_at"], c["currency"])
    ship = shipping_aud(retailer)
    gst = 0.0
    if retailer["region"] != "AU" and (price_aud + ship) > prefs["gst_threshold_aud"]:
        gst = (price_aud + ship) * prefs["gst_rate"]
    landed_sale = round(price_aud + ship + gst, 2)
    landed_full = round(compare_aud + ship + gst, 2)
    return {
        "price_aud": round(price_aud, 2),
        "shipping_aud": round(ship, 2),
        "gst_aud": round(gst, 2),
        "landed_aud": landed_sale,
        "landed_full_aud": landed_full,
        "landed_discount_pct": round(1 - landed_sale / landed_full, 3) if landed_full else 0,
    }
