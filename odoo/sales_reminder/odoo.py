"""Odoo 連線（Odoo 19 JSON-2 API，只讀）。"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .rules import Quote

TW = timezone(timedelta(hours=8))
FIELDS = ["name", "state", "partner_id", "user_id", "date_order", "validity_date", "amount_total", "currency_id"]


class OdooError(Exception):
    pass


class OdooAuthError(OdooError):
    """金鑰錯誤或權限不足：重試沒用，直接回報。"""


class Odoo:
    def __init__(self, url: str, db: str, api_key: str, timeout: int = 60, retries: int = 3, backoff: float = 2.0):
        self.url, self.db, self._key = url.rstrip("/"), db, api_key
        self.timeout, self.retries, self.backoff = timeout, retries, backoff

    def call(self, model: str, method: str, **kw):
        req = Request(f"{self.url}/json/2/{model}/{method}", data=json.dumps(kw).encode(),
                      headers={"Authorization": f"bearer {self._key}", "X-Odoo-Database": self.db,
                               "Content-Type": "application/json; charset=utf-8"})
        last = None
        for attempt in range(1, self.retries + 1):
            try:
                with urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read() or b"null")
            except HTTPError as e:
                body = e.read()[:300].decode("utf-8", "replace")
                if e.code in (401, 403):
                    raise OdooAuthError(f"Odoo 拒絕存取（HTTP {e.code}），請檢查 API Key 與權限") from None
                if e.code < 500 and e.code != 429:
                    raise OdooError(f"Odoo 回應錯誤 HTTP {e.code}: {body}") from None
                last = f"HTTP {e.code}"
            except (URLError, TimeoutError, OSError) as e:
                last = f"連線失敗：{getattr(e, 'reason', e)}"
            if attempt < self.retries:
                time.sleep(self.backoff * attempt)
        raise OdooError(f"Odoo 連線重試 {self.retries} 次仍失敗（{last}）")

    def search_read_all(self, model: str, domain: list, fields: list, order: str = "id", page: int = 200) -> list[dict]:
        rows, offset = [], 0
        while True:
            batch = self.call(model, "search_read", domain=domain, fields=fields, order=order, limit=page, offset=offset)
            rows += batch
            if len(batch) < page:
                return rows
            offset += page

    def fetch_quotes(self, states: list[str], ids: list[int] | None = None) -> list[Quote]:
        domain = [["state", "in", states]] if ids is None else [["id", "in", ids]]
        return [to_quote(r) for r in self.search_read_all("sale.order", domain, FIELDS)]

    def quote_link(self, quote_id: int) -> str:
        return f"{self.url}/odoo/sale.order/{quote_id}"


def _name(m2o) -> str:
    return m2o[1] if m2o else ""


def to_quote(r: dict) -> Quote:
    """Odoo 資料轉 Quote；date_order 是 UTC 字串，換成台灣日期。"""
    qd = None
    if r.get("date_order"):
        qd = datetime.strptime(r["date_order"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(TW).date()
    vd = date.fromisoformat(r["validity_date"]) if r.get("validity_date") else None
    return Quote(id=r["id"], name=r["name"], state=r["state"], customer=_name(r.get("partner_id")),
                 salesperson=_name(r.get("user_id")), quote_date=qd, valid_until=vd,
                 amount=r.get("amount_total") or 0.0, currency=_name(r.get("currency_id")))
