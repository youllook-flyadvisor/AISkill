"""每日摘要信：組信（繁中、依急迫度分組）＋ SMTP 寄送。"""
from __future__ import annotations

import html
import smtplib
import ssl
import time
from datetime import date
from email.message import EmailMessage
from typing import Callable

from .config import Settings
from .rules import STAGE_LABEL, STAGE_ORDER, Decision


def _days_text(n: int) -> str:
    return f"已逾期 {-n} 天" if n < 0 else ("今天到期" if n == 0 else f"剩 {n} 天")


def group(decisions: list[Decision]) -> dict[str, list[Decision]]:
    out = {s: [] for s in STAGE_ORDER}
    for d in decisions:
        out[d.stage].append(d)
    for items in out.values():
        items.sort(key=lambda d: d.days_left)
    return out


def build(decisions: list[Decision], today: date, link: Callable[[int], str]) -> tuple[str, str, str]:
    """回傳 (主旨, 純文字, HTML)。"""
    groups = group(decisions)
    counts = "、".join(f"{STAGE_LABEL[s]} {len(groups[s])} 筆" for s in STAGE_ORDER if groups[s])
    subject = f"[報價追蹤] {today:%m/%d} 共 {len(decisions)} 筆需追蹤（{counts}）"

    text = [f"今日需追蹤的報價：{len(decisions)} 筆（{counts}）", ""]
    parts = [f"<p>今日需追蹤的報價：<b>{len(decisions)}</b> 筆（{html.escape(counts)}）</p>"]
    for s in STAGE_ORDER:
        if not groups[s]:
            continue
        text.append(f"■ {STAGE_LABEL[s]}（{len(groups[s])}）")
        rows = []
        for d in groups[s]:
            q = d.quote
            amt = f"{q.currency} {q.amount:,.0f}"
            text.append(f"  {q.name}｜{q.customer}｜{amt}｜{_days_text(d.days_left)}（{q.valid_until}）｜{q.salesperson}")
            text.append(f"    {link(q.id)}")
            rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in (
                f'<a href="{html.escape(link(q.id))}">{html.escape(q.name)}</a>', html.escape(q.customer),
                html.escape(amt), html.escape(_days_text(d.days_left)), q.valid_until, html.escape(q.salesperson))) + "</tr>")
        text.append("")
        parts.append(f"<h3>{STAGE_LABEL[s]}（{len(groups[s])}）</h3>"
                     '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
                     "<tr><th>報價單</th><th>客戶</th><th>金額</th><th>剩餘天數</th><th>有效期限</th><th>業務</th></tr>"
                     + "".join(rows) + "</table>")
    footer = "此信由報價追蹤提醒系統自動產生，僅寄給內部同仁。"
    text.append(footer)
    parts.append(f'<p style="color:#888;font-size:12px">{footer}</p>')
    return subject, "\n".join(text), "<html><body>" + "".join(parts) + "</body></html>"


def check_recipients(s: Settings) -> None:
    """只准寄給內部網域，避免設定錯誤寄到客戶。"""
    if not s.internal_domains:
        return
    bad = [a for a in s.mail_to if a.rsplit("@", 1)[-1].lower() not in s.internal_domains]
    if bad:
        raise ValueError(f"收件人不在內部網域 {s.internal_domains}：{bad}")


def send(s: Settings, subject: str, text: str, html_body: str, retries: int = 3, backoff: float = 5.0) -> None:
    check_recipients(s)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, s.mail_from, ", ".join(s.mail_to)
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    last = None
    for attempt in range(1, retries + 1):
        try:
            if s.smtp_security == "ssl":
                server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ssl.create_default_context(), timeout=30)
            else:
                server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
                if s.smtp_security == "starttls":
                    server.starttls(context=ssl.create_default_context())
            with server:
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password)
                server.send_message(msg)
            return
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError("SMTP 帳密錯誤") from None
        except (smtplib.SMTPException, OSError) as e:
            last = e
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"Email 寄送重試 {retries} 次仍失敗：{last}")
