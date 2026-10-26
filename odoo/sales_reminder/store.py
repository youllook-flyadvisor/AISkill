"""寄送紀錄與執行紀錄（SQLite，存在 data/reminder.db）＋防重複執行鎖。"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sent (
    order_id INTEGER, order_name TEXT, valid_until TEXT, stage TEXT, sent_at TEXT, run_id INTEGER,
    PRIMARY KEY (order_id, valid_until, stage)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT, finished_at TEXT, mode TEXT,
    scanned INTEGER DEFAULT 0, due INTEGER DEFAULT 0, sent INTEGER DEFAULT 0, status TEXT, error TEXT
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.dir = data_dir
        self.db = sqlite3.connect(data_dir / "reminder.db")
        self.db.executescript(SCHEMA)

    # 去重：同一報價、同一到期日、同一階段只寄一次
    def already_sent(self, order_id: int, valid_until: str, stage: str) -> bool:
        return self.db.execute("SELECT 1 FROM sent WHERE order_id=? AND valid_until=? AND stage=?",
                               (order_id, valid_until, stage)).fetchone() is not None

    def mark_sent(self, run_id: int, items: list[tuple[int, str, str, str]]) -> None:
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO sent VALUES (?,?,?,?,?,?)",
                                [(oid, name, vu, stage, _now(), run_id) for oid, name, vu, stage in items])

    def start_run(self, mode: str) -> int:
        with self.db:
            return self.db.execute("INSERT INTO runs (started_at, mode, status) VALUES (?,?,'running')",
                                   (_now(), mode)).lastrowid

    def finish_run(self, run_id: int, status: str, scanned: int = 0, due: int = 0, sent: int = 0, error: str = "") -> None:
        with self.db:
            self.db.execute("UPDATE runs SET finished_at=?, status=?, scanned=?, due=?, sent=?, error=? WHERE id=?",
                            (_now(), status, scanned, due, sent, error, run_id))

    def recent_runs(self, n: int = 10) -> list[tuple]:
        return self.db.execute("SELECT id, started_at, mode, scanned, due, sent, status, error FROM runs "
                               "ORDER BY id DESC LIMIT ?", (n,)).fetchall()

    @contextmanager
    def lock(self, stale_seconds: int = 7200):
        """同時只允許一個執行；鎖檔超過 2 小時視為上次異常中斷，自動清掉。"""
        path = self.dir / "run.lock"
        if path.exists() and time.time() - path.stat().st_mtime > stale_seconds:
            path.unlink(missing_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError("已有另一個提醒程序在執行，本次略過") from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)
