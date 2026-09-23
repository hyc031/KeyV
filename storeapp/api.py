"""暴露给网页前端的 API（pywebview js_api）。

约定：
- 查询类方法返回 {"ok": True, "data": ...}
- 写操作返回 {"ok": True, "data": <新的完整快照>}，前端拿到即可整体刷新
- 出错返回 {"ok": False, "error": "<中文说明>}，不向前端抛异常
- 文件选择用系统原生对话框；密码输入、确认框等由前端自绘弹窗完成
"""

from __future__ import annotations

import threading
from typing import Optional

import webview

from . import __version__, backup, clipboard
from .db import Database, tag_list

#: 复制后自动清空剪贴板的秒数
COPY_CLEAR_SECONDS = 30


def _fail(message: str) -> dict:
    return {"ok": False, "error": str(message)}


class Api:
    def __init__(self, db=None):
        #: 允许跨线程访问：pywebview 的 API 调用发生在独立线程
        self.db = db if db is not None else Database()
        self._lock = threading.Lock()
        self._copy_timer: Optional[threading.Timer] = None
        self._copied_value: Optional[str] = None
        self._window = None

    def bind_window(self, window) -> None:
        self._window = window

    # ------------------------------------------------------------ 快照

    @staticmethod
    def _record_dict(r) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "username": r.username,
            "secret": r.secret,
            "tags": tag_list(r.tags),
            "group_id": r.group_id,
            "url": r.url,
            "note": r.note,
            "updated_at": r.updated_at,
        }

    def _snapshot(self) -> dict:
        return {
            "groups": [
                {"id": g.id, "name": g.name} for g in self.db.groups()
            ],
            "records": [
                self._record_dict(r) for r in self.db.records()
            ],
            "db_path": str(self.db.path),
            "version": __version__,
        }

    # ------------------------------------------------------------ 启动

    def bootstrap(self) -> dict:
        with self._lock:
            return {"ok": True, "data": self._snapshot()}

    # ------------------------------------------------------------ 记录

    def create_record(self, fields: dict) -> dict:
        with self._lock:
            try:
                self.db.add_record(**_normalize_fields(fields))
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    def update_record(self, record_id: int, fields: dict) -> dict:
        with self._lock:
            try:
                self.db.update_record(int(record_id), **_normalize_fields(fields))
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    def delete_record(self, record_id: int) -> dict:
        with self._lock:
            try:
                self.db.delete_record(int(record_id))
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    # ------------------------------------------------------------ 分组

    def create_group(self, name: str) -> dict:
        with self._lock:
            try:
                self.db.add_group(name or "")
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    def rename_group(self, group_id: int, name: str) -> dict:
        with self._lock:
            try:
                self.db.rename_group(int(group_id), name or "")
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    def delete_group(self, group_id: int) -> dict:
        with self._lock:
            try:
                self.db.delete_group(int(group_id))
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            return {"ok": True, "data": self._snapshot()}

    # ------------------------------------------------------------ 复制

    def copy(self, record_id: int, field: str = "secret") -> dict:
        with self._lock:
            try:
                record = self.db.get_record(int(record_id))
            except (ValueError, TypeError) as exc:
                return _fail(exc)
            value = record.secret if field != "username" else record.username
            if not value:
                return _fail("该记录没有可复制的内容")
            if not clipboard.set_text(value):
                return _fail("写入剪贴板失败，请重试")
            # 重新计时：取消旧的自动清空任务
            if self._copy_timer is not None:
                self._copy_timer.cancel()
            self._copied_value = value
            timer = threading.Timer(
                COPY_CLEAR_SECONDS, self._clear_clipboard_task
            )
            timer.daemon = True
            timer.start()
            self._copy_timer = timer
            return {"ok": True, "seconds": COPY_CLEAR_SECONDS}

    def _clear_clipboard_task(self) -> None:
        value, self._copied_value = self._copied_value, None
        self._copy_timer = None
        if value:
            clipboard.clear_if(value)

    # ------------------------------------------------------------ 备份

    def save_path_dialog(self, suggested: str) -> dict:
        try:
            result = webview.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=suggested,
                file_types=(
                    ("StoreApp 加密备份", "*.sab"),
                    ("所有文件", "*.*"),
                ),
                allow_multiple=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _fail(exc)
        if not result:
            return {"ok": False, "cancelled": True}
        path = result if isinstance(result, str) else result[0]
        return {"ok": True, "path": str(path)}

    def open_path_dialog(self) -> dict:
        try:
            result = webview.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=(
                    ("StoreApp 加密备份", "*.sab"),
                    ("所有文件", "*.*"),
                ),
                allow_multiple=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _fail(exc)
        if not result:
            return {"ok": False, "cancelled": True}
        path = result if isinstance(result, str) else result[0]
        return {"ok": True, "path": str(path)}

    def export_backup(self, path: str, password: str) -> dict:
        with self._lock:
            payload = self.db.export_data()
        try:
            backup.export_file(path, password, payload)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"写入备份文件失败：{exc}")
        return {
            "ok": True,
            "groups": len(payload["groups"]),
            "records": len(payload["records"]),
            "path": str(path),
        }

    def import_preview(self, path: str, password: str) -> dict:
        try:
            payload = backup.load_file(path, password)
        except backup.BackupError as exc:
            return _fail(exc)
        return {
            "ok": True,
            "path": str(path),
            "groups": len(payload.get("groups", [])),
            "records": len(payload["records"]),
            "exported_at": payload.get("exported_at", "未知"),
        }

    def import_backup(self, path: str, password: str, mode: str) -> dict:
        try:
            payload = backup.load_file(path, password)
        except backup.BackupError as exc:
            return _fail(exc)
        with self._lock:
            try:
                stats = self.db.apply_import(payload, mode)
            except ValueError as exc:
                return _fail(exc)
            return {"ok": True, "stats": stats, "data": self._snapshot()}

    # ------------------------------------------------------------ 其他

    def get_db_path(self) -> dict:
        return {"ok": True, "path": str(self.db.path)}

    def shutdown(self) -> None:
        """窗口关闭时调用：清计时器、清我们复制的剪贴板、关库。"""
        with self._lock:
            if self._copy_timer is not None:
                self._copy_timer.cancel()
                self._copy_timer = None
            if self._copied_value:
                clipboard.clear_if(self._copied_value)
                self._copied_value = None
            try:
                self.db.close()
            except Exception:  # noqa: BLE001
                pass


def _normalize_fields(fields: dict) -> dict:
    """把前端传来的记录字段整理成 db 层的关键字参数。"""
    if not isinstance(fields, dict):
        raise ValueError("记录内容格式不正确")
    tags = fields.get("tags", "")
    if isinstance(tags, (list, tuple)):
        tags = ",".join(str(t) for t in tags)
    group_id = fields.get("group_id")
    return {
        "name": str(fields.get("name") or ""),
        "group_id": int(group_id) if group_id else None,
        "username": str(fields.get("username") or ""),
        "secret": str(fields.get("secret") or ""),
        "url": str(fields.get("url") or ""),
        "note": str(fields.get("note") or ""),
        "tags": str(tags or ""),
    }
