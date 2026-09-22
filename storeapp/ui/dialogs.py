"""模态对话框：新增/编辑记录、新增/重命名分组。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ..db import Group

#: UI 中"未分组"伪分组的显示文字
UNG_LABEL = "未分组"


class RecordDialog(tk.Toplevel):
    """记录编辑对话框。调用 show() 阻塞等待，返回字段字典或 None（取消）。"""

    def __init__(
        self,
        parent: tk.Misc,
        groups: list[Group],
        record=None,
        default_group_id: Optional[int] = None,
    ) -> None:
        super().__init__(parent)
        self.title("新增记录" if record is None else "编辑记录")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.result: Optional[dict] = None
        self.groups = list(groups)

        self._build_ui()
        self._prefill(record, default_group_id)

        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self._on_cancel())

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        def label(text: str, row: int, sticky: str = "ne") -> None:
            ttk.Label(body, text=text).grid(
                row=row, column=0, sticky=sticky, padx=(0, 10), pady=4
            )

        label("名称 *", 0, "e")
        self.entry_name = ttk.Entry(body, width=44)
        self.entry_name.grid(row=0, column=1, sticky="we", pady=4)

        label("分组", 1, "e")
        self.combo_group = ttk.Combobox(
            body, state="readonly", width=42, values=self._group_labels()
        )
        self.combo_group.grid(row=1, column=1, sticky="we", pady=4)

        label("账号/用户名", 2, "e")
        self.entry_username = ttk.Entry(body, width=44)
        self.entry_username.grid(row=2, column=1, sticky="we", pady=4)

        label("密钥/密码", 3, "e")
        secret_frame = ttk.Frame(body)
        secret_frame.grid(row=3, column=1, sticky="we", pady=4)
        self.entry_secret = ttk.Entry(secret_frame, width=44, show="*")
        self.entry_secret.pack(side="left", fill="x", expand=True)
        self.var_show_secret = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            secret_frame, text="显示", variable=self.var_show_secret,
            command=self._toggle_secret,
        ).pack(side="left", padx=(6, 0))

        label("网址", 4, "e")
        self.entry_url = ttk.Entry(body, width=44)
        self.entry_url.grid(row=4, column=1, sticky="we", pady=4)

        label("备注", 5, "ne")
        self.text_note = tk.Text(body, width=44, height=4, wrap="word")
        self.text_note.grid(row=5, column=1, sticky="we", pady=4)

        btns = ttk.Frame(self, padding=(12, 0, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", command=self._on_save).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(btns, text="取消", command=self._on_cancel).pack(side="right")

    def _group_labels(self) -> list[str]:
        return [UNG_LABEL] + [g.name for g in self.groups]

    def _prefill(self, record, default_group_id: Optional[int]) -> None:
        if record is not None:
            self.entry_name.insert(0, record.name)
            self.entry_username.insert(0, record.username)
            self.entry_secret.insert(0, record.secret)
            self.entry_url.insert(0, record.url)
            self.text_note.insert("1.0", record.note)
            group_id = record.group_id
        else:
            group_id = default_group_id
        # 定位分组下拉框：0 = 未分组，其后为真实分组
        idx = 0
        for i, g in enumerate(self.groups, start=1):
            if g.id == group_id:
                idx = i
                break
        self.combo_group.current(idx)

    # -------------------------------------------------------------- 行为

    def _toggle_secret(self) -> None:
        self.entry_secret.config(show="" if self.var_show_secret.get() else "*")

    def _on_save(self) -> None:
        name = self.entry_name.get().strip()
        if not name:
            messagebox.showwarning("校验失败", "名称不能为空", parent=self)
            self.entry_name.focus_set()
            return
        idx = self.combo_group.current()
        group_id = None if idx <= 0 else self.groups[idx - 1].id
        self.result = {
            "name": name,
            "group_id": group_id,
            "username": self.entry_username.get().strip(),
            "secret": self.entry_secret.get(),
            "url": self.entry_url.get().strip(),
            "note": self.text_note.get("1.0", "end").rstrip("\n"),
        }
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()

    def show(self) -> Optional[dict]:
        """阻塞显示对话框，返回保存的字段字典；取消返回 None。"""
        self.grab_set()
        self.entry_name.focus_set()
        self.wait_window(self)
        return self.result


def ask_group_name(
    parent: tk.Misc, title: str, initial: str = ""
) -> Optional[str]:
    """弹出分组名称输入框，返回去空格后的名称；取消返回 None。"""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(False, False)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="分组名称").pack(anchor="w")
    var = tk.StringVar(value=initial)
    entry = ttk.Entry(frame, textvariable=var, width=34)
    entry.pack(pady=(4, 12))

    holder: dict = {"result": None}

    def ok(_event=None) -> None:
        name = var.get().strip()
        if not name:
            messagebox.showwarning("校验失败", "分组名称不能为空", parent=win)
            entry.focus_set()
            return
        holder["result"] = name
        win.destroy()

    def cancel() -> None:
        win.destroy()

    btns = ttk.Frame(frame)
    btns.pack(fill="x")
    ttk.Button(btns, text="确定", command=ok).pack(side="right", padx=(8, 0))
    ttk.Button(btns, text="取消", command=cancel).pack(side="right")

    win.bind("<Return>", ok)
    win.bind("<Escape>", lambda _e: cancel())
    win.protocol("WM_DELETE_WINDOW", cancel)

    entry.select_range(0, "end")
    entry.focus_set()
    win.grab_set()
    win.wait_window(win)
    return holder["result"]
