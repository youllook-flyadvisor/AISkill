"""主流程：讀 Odoo → 套規則 → 去重 → 寄前再確認 → 寄摘要信 → 記錄。

用法（在 skill 資料夾內執行）：
    python -m sales_reminder              正式執行（EMAIL_ENABLED=true 才會真的寄信，否則等同 dry run）
    python -m sales_reminder --dry-run    只預覽，不寄信、不寫寄送紀錄
    python -m sales_reminder --dry-run --date 2026-10-09   模擬某一天
    python -m sales_reminder --status     看最近執行紀錄
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler

from . import mailer
from .config import ConfigError, Settings, load_settings
from .odoo import TW, Odoo, OdooError
from .rules import Decision, evaluate
from .store import Store

log = logging.getLogger("sales_reminder")


@dataclass
class Result:
    status: str          # ok / nothing / dry_run / error / locked
    scanned: int = 0
    due: list[Decision] = None
    error: str = ""
    preview: str = ""


def _key(d: Decision) -> tuple[int, str, str]:
    return d.quote.id, d.quote.valid_until.isoformat(), d.stage


def run(s: Settings, today: date | None = None, dry_run: bool = False,
        odoo: Odoo | None = None, store: Store | None = None, sender=mailer.send) -> Result:
    today = today or datetime.now(TW).date()
    odoo = odoo or Odoo(s.odoo_url, s.odoo_db, s.odoo_api_key)
    store = store or Store(s.data_dir)
    dry_run = dry_run or not s.email_enabled
    mode = "dry_run" if dry_run else "live"

    try:
        with store.lock():
            run_id = store.start_run(mode)
            try:
                return _run(s, today, dry_run, odoo, store, sender, run_id)
            except Exception as e:
                log.error("執行失敗：%s", e)
                store.finish_run(run_id, "error", error=str(e)[:500])
                return Result("error", error=str(e))
    except RuntimeError as e:  # 拿不到鎖
        log.warning("%s", e)
        return Result("locked", error=str(e))


def _run(s, today, dry_run, odoo, store, sender, run_id) -> Result:
    quotes = odoo.fetch_quotes(s.rules.track_states)
    decisions = [evaluate(q, today, s.rules) for q in quotes]
    for d in decisions:
        if d.stage is None:
            log.info("略過 %s：%s", d.quote.name, d.reason)  # 只記單號與原因，不記客戶資料
    if s.state_mode == "stateless":  # 階段跟昨天不同＝今天剛進入這個階段
        due = [d for d in decisions if d.stage and evaluate(d.quote, today - timedelta(days=1), s.rules).stage != d.stage]
    else:
        due = [d for d in decisions if d.stage and not store.already_sent(*_key(d))]

    # 寄前再向 Odoo 確認一次：狀態或到期日變了的，以最新資料重算
    if due:
        fresh = {q.id: evaluate(q, today, s.rules) for q in odoo.fetch_quotes(s.rules.track_states, ids=[d.quote.id for d in due])}
        due = [fresh[d.quote.id] for d in due
               if d.quote.id in fresh and fresh[d.quote.id].stage == d.stage
               and _key(fresh[d.quote.id]) == _key(d)]

    log.info("掃描 %d 筆，需提醒 %d 筆：%s", len(quotes), len(due), ", ".join(f"{d.quote.name}/{d.stage}" for d in due))
    if not due:
        store.finish_run(run_id, "nothing", scanned=len(quotes))
        return Result("nothing", scanned=len(quotes), due=[])

    subject, text, html_body = mailer.build(due, today, odoo.quote_link)
    if dry_run:
        (s.data_dir / f"preview-{today:%Y%m%d}.html").write_text(html_body, "utf-8")
        store.finish_run(run_id, "dry_run", scanned=len(quotes), due=len(due))
        return Result("dry_run", scanned=len(quotes), due=due, preview=f"{subject}\n\n{text}")

    sender(s, subject, text, html_body)  # 失敗會丟例外 → 不寫寄送紀錄，下次會重寄
    store.mark_sent(run_id, [(d.quote.id, d.quote.name, d.quote.valid_until.isoformat(), d.stage) for d in due])
    store.finish_run(run_id, "ok", scanned=len(quotes), due=len(due), sent=len(due))
    return Result("ok", scanned=len(quotes), due=due)


def _setup_logging(s: Settings) -> None:
    s.data_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = RotatingFileHandler(s.data_dir / "reminder.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    sh = logging.StreamHandler()
    for h in (fh, sh):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def cli(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="sales_reminder", description="Odoo 報價到期提醒")
    p.add_argument("--dry-run", action="store_true", help="只預覽，不寄信、不寫寄送紀錄")
    p.add_argument("--date", help="模擬某一天（YYYY-MM-DD），只能搭配 --dry-run")
    p.add_argument("--status", action="store_true", help="顯示最近 10 次執行紀錄")
    a = p.parse_args(argv)
    try:
        s = load_settings()
    except ConfigError as e:
        print(f"設定錯誤：{e}", file=sys.stderr)
        return 2
    _setup_logging(s)
    if a.status:
        for row in Store(s.data_dir).recent_runs():
            print(row)
        return 0
    if a.date and not a.dry_run:
        print("--date 只能搭配 --dry-run 使用", file=sys.stderr)
        return 2
    today = date.fromisoformat(a.date) if a.date else None
    r = run(s, today=today, dry_run=a.dry_run)
    if r.preview:
        print("\n" + r.preview)
    print(f"\n結果：{r.status}｜掃描 {r.scanned} 筆｜提醒 {len(r.due or [])} 筆" + (f"｜錯誤：{r.error}" if r.error else ""))
    if r.status == "dry_run" and not a.dry_run:
        print("（EMAIL_ENABLED 未開啟，所以只預覽沒寄信）")
    return 1 if r.status == "error" else 0
