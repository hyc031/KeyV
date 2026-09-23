"""SQLite 数据访问层：分组与记录的增删改查。

数据文件默认位置：
- 开发运行：  <项目目录>/data/storeapp.db
- exe 运行：  <StoreApp.exe 所在目录>/data/storeapp.db

所有数据库异常在此层转换为带中文说明的 ValueError，UI 层直接提示即可。
"""

from __future__ import annotations

import re
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
    tags       TEXT NOT NULL DEFAULT '',
    group_id   INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_group ON records(group_id);
"""

#: 标签分隔符：中英文逗号/分号/顿号
_TAG_SPLIT = re.compile(r"[,，;；、]+")

#: SQLite LIKE 通配符转义
_LIKE_SPECIAL = re.compile(r"([\\%_])")


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


def normalize_tags(text: str) -> str:
    """把用户输入的标签规整为去重、逗号连接的存储格式。"""
    seen: set = set()
    result: list = []
    for part in _TAG_SPLIT.split(text or ""):
        tag = part.strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return ",".join(result)


def tag_list(tags: str) -> list:
    """把存储格式的标签还原为列表。"""
    return [t for t in (tags or "").split(",") if t]


def _like_pattern(keyword: str) -> str:
    """构造大小写不敏感的子串匹配模式，并转义 % _ \\ 字面量。"""
    escaped = _LIKE_SPECIAL.sub(r"\\\1", keyword.strip())
    return f"%{escaped}%"


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
    tags: str = ""
    group_id: Optional[int] = None
    group_name: str = ""
    created_at: str = ""
    updated_at: str = ""


class Database:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False：pywebview 的 API 调用发生在其他线程，
        # 统一由 Api 层的锁保证串行访问
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        """老版本数据库的结构升级（如 1.0 没有 tags 列）。"""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(records)")}
        if "tags" not in columns:
            self.conn.execute(
                "ALTER TABLE records ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
            )

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
            tags=row["tags"] or "",
            group_id=row["group_id"],
            group_name=row["group_name"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def records(
        self, group_id: Optional[int] = None, keyword: str = ""
    ) -> list[Record]:
        """列出记录。

        group_id=None      -> 全部记录
        group_id=UNGROUPED -> 仅未分组
        group_id>0         -> 指定分组
        keyword 非空       -> 在名称/账号/网址/备注/标签/分组名中做子串搜索
                               （搜索范围为全部分组，忽略 group_id）
        """
        sql = """
            SELECT r.*, g.name AS group_name
            FROM records r
            LEFT JOIN groups g ON g.id = r.group_id
        """
        where: list[str] = []
        params: list = []

        if keyword.strip():
            pattern = _like_pattern(keyword)
            where.append(
                "(r.name LIKE ? ESCAPE '\\' OR r.username LIKE ? ESCAPE '\\'"
                " OR r.url LIKE ? ESCAPE '\\' OR r.note LIKE ? ESCAPE '\\'"
                " OR r.tags LIKE ? ESCAPE '\\' OR g.name LIKE ? ESCAPE '\\')"
            )
            params.extend([pattern] * 6)
        elif group_id == UNGROUPED:
            where.append("r.group_id IS NULL")
        elif group_id is not None:
            where.append("r.group_id = ?")
            params.append(group_id)

        if where:
            sql += " WHERE " + " AND ".join(where)
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
        tags: str = "",
    ) -> int:
        name = name.strip()
        if not name:
            raise ValueError("名称不能为空")
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO records(name, username, secret, url, note, tags, group_id,
                                created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name, username, obfuscate.encode(secret), url, note,
                normalize_tags(tags), group_id, now, now,
            ),
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
        tags: str = "",
    ) -> None:
        name = name.strip()
        if not name:
            raise ValueError("名称不能为空")
        cur = self.conn.execute(
            """
            UPDATE records
            SET name = ?, username = ?, secret = ?, url = ?, note = ?, tags = ?,
                group_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name, username, obfuscate.encode(secret), url, note,
                normalize_tags(tags), group_id, _now(), record_id,
            ),
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

    # ------------------------------------------------------------- 备份

    def export_data(self) -> dict:
        """导出全部分组与记录（secret 此处为明文，由 backup 模块加密落盘）。"""
        records = []
        for r in self.records():
            records.append(
                {
                    "name": r.name,
                    "username": r.username,
                    "secret": r.secret,
                    "url": r.url,
                    "note": r.note,
                    "tags": r.tags,
                    "group": r.group_name,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
            )
        return {
            "app": "StoreApp",
            "format": 1,
            "exported_at": _now(),
            "groups": [g.name for g in self.groups()],
            "records": records,
        }

    def apply_import(self, payload: dict, mode: str) -> dict:
        """导入备份内容。

        mode="merge"   -> 保留现有数据；按 (名称, 账号, 更新时间) 去重后补充
        mode="replace" -> 清空现有分组与记录，完全替换为备份内容
        返回统计字典：groups_created / records_added / records_skipped。
        """
        if mode not in ("merge", "replace"):
            raise ValueError("未知的导入方式")
        raw_groups = payload.get("groups", [])
        raw_records = payload.get("records", [])
        if not isinstance(raw_groups, list) or not isinstance(raw_records, list):
            raise ValueError("备份文件内容格式不正确")

        if mode == "replace":
            self.conn.execute("DELETE FROM records")
            self.conn.execute("DELETE FROM groups")

        stats = {"groups_created": 0, "records_added": 0, "records_skipped": 0}
        name_to_id = {g.name: g.id for g in self.groups()}

        def ensure_group(name) -> Optional[int]:
            name = (name or "").strip()
            if not name or name in _RESERVED_GROUP_NAMES:
                return None
            if name in name_to_id:
                return name_to_id[name]
            cur = self.conn.execute("INSERT INTO groups(name) VALUES (?)", (name,))
            gid = int(cur.lastrowid)
            name_to_id[name] = gid
            stats["groups_created"] += 1
            return gid

        for group in raw_groups:
            if isinstance(group, str):
                ensure_group(group)

        seen: set = set()
        if mode == "merge":
            seen = {(r.name, r.username, r.updated_at) for r in self.records()}

        for rec in raw_records:
            if not isinstance(rec, dict):
                stats["records_skipped"] += 1
                continue
            name = str(rec.get("name") or "").strip()
            username = str(rec.get("username") or "")
            created = str(rec.get("created_at") or "") or _now()
            updated = str(rec.get("updated_at") or "") or created
            key = (name, username, updated)
            if not name or key in seen:
                stats["records_skipped"] += 1
                continue
            seen.add(key)
            group_id = ensure_group(rec.get("group"))
            self.conn.execute(
                """
                INSERT INTO records(name, username, secret, url, note, tags,
                                    group_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    username,
                    obfuscate.encode(str(rec.get("secret") or "")),
                    str(rec.get("url") or ""),
                    str(rec.get("note") or ""),
                    normalize_tags(str(rec.get("tags") or "")),
                    group_id,
                    created,
                    updated,
                ),
            )
            stats["records_added"] += 1

        self.conn.commit()
        return stats
