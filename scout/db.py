"""Thin Supabase REST client (no SDK dependency)."""
import os
import requests


class DB:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
        key = os.environ["SUPABASE_SERVICE_KEY"]
        self.h = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def _get(self, path: str, params: dict) -> list:
        r = requests.get(f"{self.url}/rest/v1/{path}", headers=self.h,
                         params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def existing_items(self) -> dict[str, dict]:
        """item_key -> {status, price} for dedup/resurface decisions."""
        out, offset = {}, 0
        while True:
            rows = self._get("items", {
                "select": "item_key,status,price",
                "offset": offset, "limit": 1000,
            })
            for row in rows:
                out[row["item_key"]] = row
            if len(rows) < 1000:
                break
            offset += 1000
        return out

    def muted_retailers(self) -> set[str]:
        rows = self._get("muted_retailers", {"select": "retailer_id"})
        return {r["retailer_id"] for r in rows}

    def upsert_item(self, item: dict):
        r = requests.post(
            f"{self.url}/rest/v1/items",
            headers={**self.h, "Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "item_key"},
            json=item, timeout=30)
        r.raise_for_status()
