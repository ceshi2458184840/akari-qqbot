"""账号 / 配置持久化（SQLite）。"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from typing import Any


class Store:
    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS bots (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,          -- onebot | qqofficial
                    label TEXT,
                    config TEXT NOT NULL,        -- JSON
                    enabled INTEGER DEFAULT 0,
                    created_at REAL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS plugins (
                    name TEXT PRIMARY KEY,
                    version TEXT,
                    repo TEXT,
                    path TEXT,
                    enabled INTEGER DEFAULT 1,
                    installed_at REAL
                )"""
            )

    # ---- bots ----
    def list_bots(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM bots ORDER BY created_at").fetchall()
        return [dict(r) | {"config": json.loads(r["config"])} for r in rows]

    def get_bot(self, bot_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
        return dict(r) | {"config": json.loads(r["config"])} if r else None

    def add_bot(self, mode: str, label: str, config: dict[str, Any]) -> dict[str, Any]:
        bot_id = uuid.uuid4().hex[:12]
        with self._conn() as c:
            c.execute(
                "INSERT INTO bots (id,mode,label,config,enabled,created_at) VALUES (?,?,?,?,0,?)",
                (bot_id, mode, label, json.dumps(config, ensure_ascii=False), time.time()),
            )
        return self.get_bot(bot_id)  # type: ignore[return-value]

    def set_enabled(self, bot_id: str, enabled: bool) -> None:
        with self._conn() as c:
            c.execute("UPDATE bots SET enabled=? WHERE id=?", (1 if enabled else 0, bot_id))

    def delete_bot(self, bot_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM bots WHERE id=?", (bot_id,))

    # ---- plugins ----
    def list_plugins(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM plugins ORDER BY installed_at DESC").fetchall()
        return [dict(r) for r in rows]

    def upsert_plugin(self, name: str, version: str, repo: str, path: str) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO plugins (name,version,repo,path,enabled,installed_at)
                   VALUES (?,?,?,?,1,?)
                   ON CONFLICT(name) DO UPDATE SET version=excluded.version,
                   repo=excluded.repo, path=excluded.path, installed_at=excluded.installed_at""",
                (name, version, repo, path, time.time()),
            )
