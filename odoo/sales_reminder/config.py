"""所有設定集中在這裡。要調規則或信箱，改 .env 即可，不用改程式。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    pass


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """把 .env 讀進環境變數；已存在的環境變數優先，不覆寫。"""
    if not path.exists():
        return
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    return int(_get(name, str(default)))


def _bool(name: str, default: bool = False) -> bool:
    return _get(name, str(default)).lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in _get(name, default).split(",") if x.strip()]


@dataclass
class Rules:
    """提醒規則參數（業務規則本身在 rules.py）。"""
    track_states: list[str] = field(default_factory=lambda: ["sent"])  # sent=已發送報價；要連草稿一起追蹤就加 draft
    due_soon_days: int = 7      # 到期前幾天發第二次提醒（7–14）
    min_gap_days: int = 3       # 第一、二次提醒日期相距少於這天數，就省略第一次
    min_age_days: int = 1       # 報價建立未滿幾天不提醒
    overdue_max_days: int = 30  # 逾期超過幾天就不再列入（避免陳年舊單一直出現）

    def __post_init__(self) -> None:
        if not 7 <= self.due_soon_days <= 14:
            raise ConfigError("DUE_SOON_DAYS 必須介於 7 到 14")


@dataclass
class Settings:
    odoo_url: str
    odoo_db: str
    odoo_api_key: str
    rules: Rules
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"  # starttls / ssl / none
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""
    mail_to: list[str] = field(default_factory=list)
    internal_domains: list[str] = field(default_factory=list)
    data_dir: Path = ROOT / "data"
    # db＝用 data/reminder.db 記錄已寄，漏跑的日子下次會補寄（本機／固定主機用）
    # stateless＝不靠紀錄，每個階段只在開始的那一天寄（雲端排程每次都是新環境時用）
    state_mode: str = "db"


def load_settings() -> Settings:
    load_dotenv()
    missing = [n for n in ("ODOO_URL", "ODOO_DB", "ODOO_API_KEY") if not _get(n)]
    if missing:
        raise ConfigError("缺少必要設定：" + ", ".join(missing) + "（請在 .env 填寫，步驟見 docs\\設定說明書.pdf）")
    rules = Rules(
        track_states=_list("TRACK_STATES", "sent"),
        due_soon_days=_int("DUE_SOON_DAYS", 7),
        min_gap_days=_int("MIN_GAP_DAYS", 3),
        min_age_days=_int("MIN_AGE_DAYS", 1),
        overdue_max_days=_int("OVERDUE_MAX_DAYS", 30),
    )
    s = Settings(
        odoo_url=_get("ODOO_URL").rstrip("/"),
        odoo_db=_get("ODOO_DB"),
        odoo_api_key=_get("ODOO_API_KEY"),
        rules=rules,
        email_enabled=_bool("EMAIL_ENABLED"),
        smtp_host=_get("SMTP_HOST"),
        smtp_port=_int("SMTP_PORT", 587),
        smtp_security=_get("SMTP_SECURITY", "starttls").lower(),
        smtp_user=_get("SMTP_USER"),
        smtp_password=_get("SMTP_PASSWORD"),
        mail_from=_get("MAIL_FROM"),
        mail_to=_list("MAIL_TO"),
        internal_domains=[d.lower() for d in _list("INTERNAL_DOMAINS")],
        data_dir=Path(_get("DATA_DIR") or ROOT / "data"),
        state_mode=_get("STATE_MODE", "db").lower(),
    )
    if "gmail" in s.smtp_host.lower():  # Google 顯示的應用程式密碼帶空白，貼上時常一起貼進來
        s.smtp_password = s.smtp_password.replace(" ", "")
    if s.state_mode not in ("db", "stateless"):
        raise ConfigError("STATE_MODE 只能是 db 或 stateless")
    if s.email_enabled:
        need = [n for n, v in (("SMTP_HOST", s.smtp_host), ("MAIL_FROM", s.mail_from), ("MAIL_TO", s.mail_to)) if not v]
        if need:
            raise ConfigError("EMAIL_ENABLED=true 但缺少：" + ", ".join(need))
    return s
