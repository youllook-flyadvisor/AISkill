"""提醒規則：純計算、不連網，所有「什麼時候該提醒」的判斷都在這支檔案。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from .config import Rules

HALF, DUE_SOON, EXPIRED = "half", "due_soon", "expired"
STAGE_LABEL = {EXPIRED: "已逾期", DUE_SOON: "即將到期", HALF: "效期過半"}
STAGE_ORDER = [EXPIRED, DUE_SOON, HALF]  # 信件分組順序：最急迫在前


@dataclass
class Quote:
    id: int
    name: str
    state: str
    customer: str
    salesperson: str
    quote_date: date | None    # 報價日（Odoo date_order，換成台灣日期）
    valid_until: date | None   # 有效期限（Odoo validity_date），唯一的到期依據
    amount: float
    currency: str


@dataclass
class Decision:
    quote: Quote
    stage: str | None = None       # None＝今天不提醒
    days_left: int | None = None   # 負數＝已逾期幾天
    reason: str = ""               # 不提醒的原因（寫進紀錄）


def evaluate(q: Quote, today: date, r: Rules) -> Decision:
    d = Decision(q)
    if q.state not in r.track_states:
        d.reason = f"狀態 {q.state} 不在追蹤範圍"
        return d
    if q.valid_until is None:
        d.reason = "缺少有效期限"
        return d

    days_left = d.days_left = (q.valid_until - today).days
    if days_left < 0:
        if -days_left > r.overdue_max_days:
            d.reason = f"逾期超過 {r.overdue_max_days} 天，不再列入"
        else:
            d.stage = EXPIRED
        return d

    if q.quote_date and (today - q.quote_date).days < r.min_age_days:
        d.reason = "報價剛建立"
        return d

    if days_left <= r.due_soon_days:
        d.stage = DUE_SOON
        return d

    if q.quote_date is None:
        d.reason = "缺少報價日，無法算效期過半"
        return d
    total = (q.valid_until - q.quote_date).days
    half_date = q.quote_date + timedelta(days=math.ceil(total / 2))
    due_soon_date = q.valid_until - timedelta(days=r.due_soon_days)
    if today < half_date:
        d.reason = "尚未過半"
    elif (due_soon_date - half_date).days < r.min_gap_days:
        d.reason = "與即將到期提醒太近，併入第二次"
    else:
        d.stage = HALF
    return d
