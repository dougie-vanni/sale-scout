"""Thin Supabase REST client (no SDK dependency)."""
import os
import time
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

    def _write(self, method: str, path: str, params: dict, body: dict,
               prefer: str = "return=minimal", max_attempts: int = 4) -> None:
        """POST/PATCH with exponential-backoff retry on timeout or 5xx."""
        hdrs = {**self.h, "Prefer": prefer}
        fn = requests.post if method == "post" else requests.patch
        last_err = "unknown"
        for attempt in range(max_attempts):
            try:
                r = fn(f"{self.url}/rest/v1/{path}", headers=hdrs,
                       params=params, json=body, timeout=30)
                if r.status_code in (500, 502, 503, 504):
                    last_err = f"HTTP {r.status_code}"
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                return
            except requests.exceptions.Timeout:
                last_err = "timeout"
                if attempt < max_attempts - 1:
                    print(f"  ! DB write timeout, retrying ({attempt + 1}/{max_attempts - 1})")
                    time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                last_err = str(e)
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"DB write failed after {max_attempts} attempts: {last_err}")

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
        self._write("post", "items", {"on_conflict": "item_key"}, item,
                    prefer="resolution=merge-duplicates,return=minimal")

    # ── sweep control flags ──────────────────────────────────────────────────
    def get_flag(self, key: str) -> bool:
        try:
            rows = self._get("control", {"select": "value", "key": f"eq.{key}"})
            return bool(rows and rows[0]["value"])
        except Exception:
            return False

    def set_flag(self, key: str, value: bool) -> None:
        try:
            self._write("patch", "control", {"key": f"eq.{key}"}, {"value": value})
        except Exception as e:
            print(f"  ! could not set flag {key}: {e}")

    # ── website-editable config ──────────────────────────────────────────────
    def get_retailers(self) -> list | None:
        try:
            rows = self._get("retailers", {"select": "*", "order": "id"})
            return [{k: v for k, v in r.items() if v is not None}
                    for r in rows] if rows else None
        except Exception:
            return None

    def get_preferences(self) -> dict | None:
        try:
            rows = self._get("preferences", {"select": "value", "key": "eq.main"})
            return rows[0]["value"] if rows else None
        except Exception:
            return None

    def set_sweep_status(self, state: str, detail: str = "") -> None:
        import datetime
        try:
            self._write("patch", "sweep_status", {"id": "eq.1"},
                        {"state": state, "detail": detail[:200],
                         "updated_at": datetime.datetime.now(
                             datetime.timezone.utc).isoformat()})
        except Exception as e:
            print(f"  ! could not set sweep_status: {e}")
