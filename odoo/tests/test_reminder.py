"""驗收測試：python -m pytest tests（不連 Odoo、不寄信）。"""
from datetime import date, timedelta

import pytest

from sales_reminder import mailer
from sales_reminder.config import ConfigError, Rules, Settings
from sales_reminder.main import run
from sales_reminder.odoo import OdooError, to_quote
from sales_reminder.rules import DUE_SOON, EXPIRED, HALF, Quote, evaluate
from sales_reminder.store import Store

R = Rules()


def q(id=139, name="S00139", state="sent", start=date(2026, 9, 9), end=date(2026, 10, 16)):
    return Quote(id, name, state, "測試客戶", "業務A", start, end, 14459.0, "TWD")


class FakeOdoo:
    url = "https://example.odoo.com"

    def __init__(self, quotes, fail=False):
        self.quotes, self.fail = {x.id: x for x in quotes}, fail

    def fetch_quotes(self, states, ids=None):
        if self.fail:
            raise OdooError("Odoo 連線重試 3 次仍失敗（連線失敗：timed out）")
        return [x for x in self.quotes.values() if (x.id in ids if ids else x.state in states)]

    def quote_link(self, i):
        return f"{self.url}/odoo/sale.order/{i}"


class FakeSender:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, s, subject, text, html):
        if self.fail:
            raise RuntimeError("Email 寄送重試 3 次仍失敗")
        self.calls.append(subject)


@pytest.fixture
def env(tmp_path):
    s = Settings("https://example.odoo.com", "db", "k", R, email_enabled=True, data_dir=tmp_path)
    return s, Store(tmp_path)


# ---- 規則 ----
def test_just_created_no_reminder():
    assert evaluate(q(), date(2026, 9, 9), R).stage is None


def test_half_way_first_reminder():
    # 9/9～10/16 共 37 天，第 19 天（9/28）過半
    assert evaluate(q(), date(2026, 9, 27), R).stage is None
    assert evaluate(q(), date(2026, 9, 28), R).stage == HALF


def test_seven_days_left_second_reminder():
    d = evaluate(q(), date(2026, 10, 9), R)
    assert (d.stage, d.days_left) == (DUE_SOON, 7)


def test_expired_marked():
    d = evaluate(q(), date(2026, 10, 17), R)
    assert (d.stage, d.days_left) == (EXPIRED, -1)


def test_old_expired_dropped_with_reason():
    d = evaluate(q(), date(2026, 12, 1), R)
    assert d.stage is None and "逾期超過" in d.reason


@pytest.mark.parametrize("state", ["sale", "cancel"])
def test_won_or_cancelled_no_reminder(state):
    assert evaluate(q(state=state), date(2026, 10, 9), R).stage is None


def test_missing_validity_skipped_with_reason():
    d = evaluate(q(end=None), date(2026, 10, 9), R)
    assert d.stage is None and d.reason == "缺少有效期限"


def test_close_reminders_merged():
    # 10/1～10/15：過半日 10/9，第二次提醒日 10/8 → 太近，只發第二次
    short = q(start=date(2026, 10, 1), end=date(2026, 10, 15))
    assert evaluate(short, date(2026, 10, 7), R).stage is None
    assert evaluate(short, date(2026, 10, 8), R).stage == DUE_SOON


def test_due_soon_days_configurable_and_bounded():
    assert evaluate(q(), date(2026, 10, 2), Rules(due_soon_days=14)).stage == DUE_SOON
    with pytest.raises(ConfigError):
        Rules(due_soon_days=5)


def test_odoo_date_converted_to_taiwan():
    r = {"id": 1, "name": "S1", "state": "sent", "partner_id": [1, "客"], "user_id": False,
         "date_order": "2026-09-08 17:00:00", "validity_date": "2026-10-16", "amount_total": 1, "currency_id": [1, "TWD"]}
    assert to_quote(r).quote_date == date(2026, 9, 9)  # UTC 17:00 = 台灣隔天 01:00


# ---- 流程 ----
def test_same_day_rerun_no_duplicate(env):
    s, store = env
    sender = FakeSender()
    odoo = FakeOdoo([q()])
    assert run(s, date(2026, 10, 9), odoo=odoo, store=store, sender=sender).status == "ok"
    assert run(s, date(2026, 10, 9), odoo=odoo, store=store, sender=sender).status == "nothing"
    assert len(sender.calls) == 1


def test_validity_change_recalculates(env):
    s, store = env
    sender = FakeSender()
    run(s, date(2026, 10, 9), odoo=FakeOdoo([q()]), store=store, sender=sender)
    # 業務把到期日延到 10/30 → 新的到期版本，10/23 再提醒一次
    r = run(s, date(2026, 10, 23), odoo=FakeOdoo([q(end=date(2026, 10, 30))]), store=store, sender=sender)
    assert r.status == "ok" and r.due[0].stage == DUE_SOON and len(sender.calls) == 2


def test_state_changed_before_send_dropped(env):
    s, store = env

    class Flip(FakeOdoo):  # 第一次讀到 sent，寄前再確認時已成交
        n = 0

        def fetch_quotes(self, states, ids=None):
            self.n += 1
            return [q()] if self.n == 1 else [q(state="sale")]

    sender = FakeSender()
    assert run(s, date(2026, 10, 9), odoo=Flip([]), store=store, sender=sender).status == "nothing"
    assert sender.calls == []


def test_missing_date_does_not_break_run(env):
    s, store = env
    r = run(s, date(2026, 10, 9), odoo=FakeOdoo([q(id=1, name="S1", end=None), q()]), store=store, sender=FakeSender())
    assert r.status == "ok" and [d.quote.name for d in r.due] == ["S00139"]


def test_api_down_logged(env):
    s, store = env
    r = run(s, date(2026, 10, 9), odoo=FakeOdoo([], fail=True), store=store, sender=FakeSender())
    assert r.status == "error"
    assert store.recent_runs()[0][6:] == ("error", "Odoo 連線重試 3 次仍失敗（連線失敗：timed out）")


def test_email_failure_not_marked_sent(env):
    s, store = env
    r = run(s, date(2026, 10, 9), odoo=FakeOdoo([q()]), store=store, sender=FakeSender(fail=True))
    assert r.status == "error"
    assert not store.already_sent(139, "2026-10-16", DUE_SOON)
    # 下次執行會補寄
    assert run(s, date(2026, 10, 9), odoo=FakeOdoo([q()]), store=store, sender=FakeSender()).status == "ok"


def test_dry_run_no_send_no_record(env):
    s, store = env
    sender = FakeSender()
    r = run(s, date(2026, 10, 9), dry_run=True, odoo=FakeOdoo([q()]), store=store, sender=sender)
    assert r.status == "dry_run" and "S00139" in r.preview
    assert sender.calls == [] and not store.already_sent(139, "2026-10-16", DUE_SOON)


def test_email_disabled_means_dry_run(env):
    s, store = env
    s.email_enabled = False
    sender = FakeSender()
    assert run(s, date(2026, 10, 9), odoo=FakeOdoo([q()]), store=store, sender=sender).status == "dry_run"
    assert sender.calls == []


def test_parallel_run_blocked(env):
    s, store = env
    with store.lock():
        assert run(s, date(2026, 10, 9), odoo=FakeOdoo([q()]), store=store, sender=FakeSender()).status == "locked"


def test_s00139_reminded_before_expiry(env):
    """訪談案例：9/9 報價、10/16 到期 → 9/28 第一次、10/9 第二次、10/17 列為逾期，每階段只寄一次。"""
    s, store = env
    sender = FakeSender()
    odoo = FakeOdoo([q()])
    stages = {}
    for day in range(9, 31):
        r = run(s, date(2026, 9, day), odoo=odoo, store=store, sender=sender)
        stages.update({d.stage: date(2026, 9, day) for d in r.due or []})
    for day in range(1, 21):
        r = run(s, date(2026, 10, day), odoo=odoo, store=store, sender=sender)
        stages.update({d.stage: date(2026, 10, day) for d in r.due or []})
    assert stages == {HALF: date(2026, 9, 28), DUE_SOON: date(2026, 10, 9), EXPIRED: date(2026, 10, 17)}
    assert len(sender.calls) == 3


def test_stateless_mode_each_day_fresh_environment(tmp_path):
    """雲端排程：每天都是全新環境（沒有寄送紀錄），仍然每階段只寄一次。"""
    s = Settings("u", "d", "k", R, email_enabled=True, state_mode="stateless")
    sender = FakeSender()
    sent_on = []
    start = date(2026, 9, 9)
    for i in range(45):
        day = start + timedelta(days=i)
        r = run(s, day, odoo=FakeOdoo([q()]), store=Store(tmp_path / str(i)), sender=sender)
        sent_on += [(d.stage, day) for d in r.due or []]
    assert sent_on == [(HALF, date(2026, 9, 28)), (DUE_SOON, date(2026, 10, 9)), (EXPIRED, date(2026, 10, 17))]


# ---- 信件 ----
def test_email_grouped_urgent_first():
    ds = [evaluate(q(id=1, name="A"), date(2026, 9, 28), R),
          evaluate(q(id=2, name="B"), date(2026, 10, 17), R),
          evaluate(q(id=3, name="C"), date(2026, 10, 10), R)]
    subject, text, html = mailer.build(ds, date(2026, 10, 17), lambda i: f"https://x/odoo/sale.order/{i}")
    assert "共 3 筆" in subject
    assert text.index("已逾期") < text.index("即將到期") < text.index("效期過半")
    assert "https://x/odoo/sale.order/2" in html and "已逾期 1 天" in text


def test_recipient_outside_internal_domain_blocked():
    s = Settings("u", "d", "k", R, mail_to=["boss@flyadvisor.xyz", "client@gmail.com"], internal_domains=["flyadvisor.xyz"])
    with pytest.raises(ValueError):
        mailer.check_recipients(s)
