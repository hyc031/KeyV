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

        label("标签", 4, "e")
        self.entry_tags = ttk.Entry(body, width=44)
        self.entry_tags.grid(row=4, column=1, sticky="we", pady=4)
        ttk.Label(
            body, text="多个标签用逗号分隔，如：openai,付费", foreground="#888888"
        ).grid(row=5, column=1, sticky="w", pady=(0, 4))

        label("网址", 6, "e")
        self.entry_url = ttk.Entry(body, width=44)
        self.entry_url.grid(row=6, column=1, sticky="we", pady=4)

        label("备注", 7, "ne")
        self.text_note = tk.Text(body, width=44, height=4, wrap="word")
        self.text_note.grid(row=7, column=1, sticky="we", pady=4)

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
            self.entry_tags.insert(0, record.tags)
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
            "tags": self.entry_tags.get(),
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


def ask_backup_password(
    parent: tk.Misc,
    title: str,
    message: str,
    confirm: bool = False,
) -> Optional[str]:
    """输入备份密码。

    confirm=True（导出场景）时要求输入两次并校验一致性；
    返回密码字符串；取消返回 None。密码至少 6 位。
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", lambda: _finish(None))

    holder: dict = {"result": None}

    def _finish(value: Optional[str]) -> None:
        holder["result"] = value
        win.destroy()

    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text=message, wraplength=340, foreground="#555555").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
    )

    def password_row(row: int, label_text: str) -> ttk.Entry:
        ttk.Label(frame, text=label_text).grid(
            row=row, column=0, sticky="e", padx=(0, 10), pady=4
        )
        entry = ttk.Entry(frame, width=32, show="*")
        entry.grid(row=row, column=1, sticky="we", pady=4)
        return entry

    entry_pwd = password_row(1, "密码")
    var_show = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        frame, text="显示", variable=var_show,
        command=lambda: entry_pwd.config(show="" if var_show.get() else "*"),
    ).grid(row=1, column=2, padx=(6, 0), pady=4)

    entry_confirm: Optional[ttk.Entry] = None
    if confirm:
        entry_confirm = password_row(2, "确认密码")

    btns = ttk.Frame(frame)
    btns.grid(row=3, column=0, columnspan=3, sticky="we", pady=(12, 0))
    ttk.Button(btns, text="确定", command=lambda: _on_ok()).pack(
        side="right", padx=(8, 0)
    )
    ttk.Button(btns, text="取消", command=lambda: _finish(None)).pack(side="right")

    def _on_ok() -> None:
        pwd = entry_pwd.get()
        if len(pwd) < 6:
            messagebox.showwarning(
                "密码太短", "备份密码至少需要 6 位", parent=win
            )
            entry_pwd.focus_set()
            return
        if entry_confirm is not None and pwd != entry_confirm.get():
            messagebox.showwarning(
                "两次不一致", "两次输入的密码不一致，请重新确认", parent=win
            )
            entry_confirm.delete(0, "end")
            entry_confirm.focus_set()
            return
        _finish(pwd)

    win.bind("<Return>", lambda _e: _on_ok())
    win.bind("<Escape>", lambda _e: _finish(None))

    entry_pwd.focus_set()
    win.grab_set()
    win.wait_window(win)
    return holder["result"]


def choose_import_mode(parent: tk.Misc, summary: str) -> Optional[str]:
    """选择导入方式：返回 "merge" / "replace" / None（取消）。"""
    win = tk.Toplevel(parent)
    win.title("导入备份")
    win.transient(parent)
    win.resizable(False, False)
    win.protocol("WM_DELETE_WINDOW", lambda: _finish(None))

    holder: dict = {"result": None}

    def _finish(value: Optional[str]) -> None:
        holder["result"] = value
        win.destroy()

    frame = ttk.Frame(win, padding=14)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text=summary, wraplength=380).pack(anchor="w", pady=(0, 12))

    # 合并导入
    ttk.Label(
        frame,
        text="合并导入：保留现有数据，仅补充备份中没有的记录（自动去重）",
        wraplength=380, foreground="#555555",
    ).pack(anchor="w")
    merge_row = ttk.Frame(frame)
    merge_row.pack(fill="x", pady=(4, 12))
    ttk.Button(
        merge_row, text="合并导入", command=lambda: _finish("merge")
    ).pack(side="left")

    # 覆盖全部
    ttk.Label(
        frame,
        text="覆盖全部：删除当前所有分组与记录，完全替换为备份内容（危险）",
        wraplength=380, foreground="#b00020",
    ).pack(anchor="w")
    replace_row = ttk.Frame(frame)
    replace_row.pack(fill="x", pady=(4, 12))
    ttk.Button(
        replace_row, text="覆盖全部", command=lambda: _finish("replace")
    ).pack(side="left")
    ttk.Button(replace_row, text="取消", command=lambda: _finish(None)).pack(
        side="right"
    )

    win.bind("<Escape>", lambda _e: _finish(None))

    win.grab_set()
    win.wait_window(win)
    return holder["result"]
