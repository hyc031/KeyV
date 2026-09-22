"""SQLite 数据访问层：分组与记录的增删改查。

数据文件默认位置：
- 开发运行：  <项目目录>/data/storeapp.db
- exe 运行：  <StoreApp.exe 所在目录>/data/storeapp.db

所有数据库异常在此层转换为带中文说明的 ValueError，UI 层直接提示即可。
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import obfuscate

#: 伪分组 ID，表示"未分组"（真实分组 ID 从 1 开始）
UNGROUPED = -1

#: 保留名称：UI 已用作伪分组，禁止用作真实分组名
_RESERVED_GROUP_NAMES = ("未分组", "全部记录")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    username   TEXT NOT NULL DEFAULT '',
    secret     TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    note       TEXT NOT NULL DEFAULT '',
    group_id   INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_group ON records(group_id);
"""


def app_data_dir() -> Path:
    """返回数据目录：开发时在项目 data/ 下，打包后在 exe 同级 data/ 下。"""
    if getattr(sys, "frozen", False):  # PyInstaller 打包运行
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    path = base / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_db_path() -> Path:
    return app_data_dir() / "storeapp.db"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Group:
    id: int
    name: str
    record_count: int = 0


@dataclass
class Record:
    id: int
    name: str
    username: str = ""
    secret: str = ""
    url: str = ""
    note: str = ""
    group_id: Optional[int] = None
    group_name: str = ""
    created_at: str = ""
    updated_at: str = ""


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else default_db_path()
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ 分组

    @staticmethod
    def _check_group_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("分组名称不能为空")
        if name in _RESERVED_GROUP_NAMES:
            raise ValueError(f"「{name}」是保留名称，请换一个分组名")
        return name

    def groups(self) -> list[Group]:
        rows = self.conn.execute(
            """
            SELECT g.id, g.name, COUNT(r.id) AS cnt
            FROM groups g
            LEFT JOIN records r ON r.group_id = g.id
            GROUP BY g.id
            ORDER BY g.name
            """
        ).fetchall()
        return [Group(r["id"], r["name"], r["cnt"]) for r in rows]

    def add_group(self, name: str) -> int:
        name = self._check_group_name(name)
        try:
            cur = self.conn.execute("INSERT INTO groups(name) VALUES (?)", (name,))
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"分组「{name}」已存在") from exc
        self.conn.commit()
        return int(cur.lastrowid)

    def rename_group(self, group_id: int, name: str) -> None:
        name = self._check_group_name(name)
        try:
            cur = self.conn.execute(
                "UPDATE groups SET name = ? WHERE id = ?", (name, group_id)
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"分组「{name}」已存在") from exc
        if cur.rowcount == 0:
            raise ValueError("分组不存在或已被删除")
        self.conn.commit()

    def delete_group(self, group_id: int) -> None:
        """删除分组；其中的记录自动变为"未分组"（外键 ON DELETE SET NULL）。"""
        cur = self.conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        if cur.rowcount == 0:
            raise ValueError("分组不存在或已被删除")
        self.conn.commit()

    # ------------------------------------------------------------------ 记录

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> Record:
        return Record(
            id=row["id"],
            name=row["name"],
            username=row["username"],
            secret=obfuscate.decode(row["secret"]),
            url=row["url"],
            note=row["note"],
            group_id=row["group_id"],
            group_name=row["group_name"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def records(self, group_id: Optional[int] = None) -> list[Record]:
        """列出记录。

        group_id=None     -> 全部记录
        group_id=UNGROUPED -> 仅未分组
        group_id>0        -> 指定分组
        """
        sql = """
            SELECT r.*, g.name AS group_name
            FROM records r
            LEFT JOIN groups g ON g.id = r.group_id
        """
        params: tuple = ()
        if group_id == UNGROUPED:
            sql += " WHERE r.group_id IS NULL"
        elif group_id is not None:
            sql += " WHERE r.group_id = ?"
            params = (group_id,)
        sql += " ORDER BY r.updated_at DESC, r.id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_record(self, record_id: int) -> Record:
        row = self.conn.execute(
            """
            SELECT r.*, g.name AS group_name
            FROM records r
            LEFT JOIN groups g ON g.id = r.group_id
            WHERE r.id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            raise ValueError("记录不存在或已被删除")
        return self._row_to_record(row)

    def add_record(
        self,
        *,
        name: str,
        group_id: Optional[int] = None,
        username: str = "",
        secret: str = "",
        url: str = "",
        note: str = "",
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("名称不能为空")
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO records(name, username, secret, url, note, group_id,
                                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, username, obfuscate.encode(secret), url, note, group_id, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_record(
        self,
        record_id: int,
        *,
        name: str,
        group_id: Optional[int] = None,
        username: str = "",
        secret: str = "",
        url: str = "",
        note: str = "",
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("名称不能为空")
        cur = self.conn.execute(
            """
            UPDATE records
            SET name = ?, username = ?, secret = ?, url = ?, note = ?,
                group_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, username, obfuscate.encode(secret), url, note, group_id, _now(), record_id),
        )
        if cur.rowcount == 0:
            raise ValueError("记录不存在或已被删除")
        self.conn.commit()

    def delete_record(self, record_id: int) -> None:
        cur = self.conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        if cur.rowcount == 0:
            raise ValueError("记录不存在或已被删除")
        self.conn.commit()

    # ------------------------------------------------------------------ 统计

    def record_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])

    def ungrouped_count(self) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM records WHERE group_id IS NULL"
            ).fetchone()[0]
        )
