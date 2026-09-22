"""StoreApp 主窗口：左侧分组、右侧记录表格，完成增删改查。"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .. import backup
from ..db import UNGROUPED, Database
from .dialogs import (
    RecordDialog,
    ask_backup_password,
    ask_group_name,
    choose_import_mode,
)

ALL_LABEL = "全部记录"
UNG_LABEL = "未分组"

#: 密钥列打码时显示的最长圆点数
_MASK_MAX = 16

#: 复制到剪贴板后自动清空的秒数
COPY_CLEAR_SECONDS = 30
COPY_CLEAR_MS = COPY_CLEAR_SECONDS * 1000


class MainWindow:
    def __init__(self, root: tk.Tk, db: Database) -> None:
        self.root = root
        self.db = db
        #: 当前选中的分组：None=全部，UNGROUPED=未分组，>0=真实分组 ID
        self.selected_group_id: Optional[int] = None
        self.show_secrets = False
        #: 搜索关键词（非空时跨全部分组搜索）
        self.keyword = ""
        #: 剪贴板监护：已复制的值与其自动清空定时器
        self._clipboard_value: Optional[str] = None
        self._clipboard_after = None
        #: 列表框索引 -> 分组 ID（前两项固定为 全部/未分组）
        self._group_ids: list[Optional[int]] = []

        self._build_ui()
        self._bind_events()
        self.refresh_groups()
        self.refresh_records()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.title("StoreApp · 密钥与密码本地存储")
        self.root.geometry("1060x620")
        self.root.minsize(900, 500)

        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        # 顶部工具栏（记录操作 + 搜索 + 备份）
        bar = ttk.Frame(self.root, padding=(10, 7))
        bar.pack(fill="x")
        self.btn_new = ttk.Button(bar, text="新增记录", command=self.on_new_record)
        self.btn_edit = ttk.Button(bar, text="编辑", command=self.on_edit_record)
        self.btn_delete = ttk.Button(bar, text="删除", command=self.on_delete_record)
        self.btn_copy = ttk.Button(bar, text="复制密钥", command=self.on_copy_secret)
        self.btn_new.pack(side="left")
        self.btn_edit.pack(side="left", padx=(6, 0))
        self.btn_delete.pack(side="left", padx=(6, 0))
        self.btn_copy.pack(side="left", padx=(6, 0))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Label(bar, text="搜索:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=24)
        self.search_entry.pack(side="left", padx=(6, 0))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        self.var_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bar, text="显示密钥", variable=self.var_show,
            command=self.on_toggle_secrets,
        ).pack(side="left")

        self.btn_import = ttk.Button(bar, text="导入备份", command=self.on_import_backup)
        self.btn_export = ttk.Button(bar, text="导出备份", command=self.on_export_backup)
        self.btn_import.pack(side="right")
        self.btn_export.pack(side="right", padx=(0, 6))

        # 底部状态栏
        self.status = ttk.Label(
            self.root, anchor="w", padding=(10, 4), foreground="#555555"
        )
        self.status.pack(fill="x", side="bottom")

        # 主体
        body = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        body.pack(fill="both", expand=True)

        # --- 左侧：分组 ---
        left = ttk.Frame(body, width=224)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="分组").pack(anchor="w", pady=(2, 4))

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        self.group_list = tk.Listbox(
            list_frame, exportselection=False, activestyle="none",
            relief="solid", borderwidth=1, highlightthickness=0,
            font=("Microsoft YaHei UI", 10), selectbackground="#cde4f7",
            selectforeground="#000000",
        )
        self.group_list.pack(side="left", fill="both", expand=True)
        group_scroll = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.group_list.yview
        )
        group_scroll.pack(side="right", fill="y")
        self.group_list.config(yscrollcommand=group_scroll.set)

        group_btns = ttk.Frame(left)
        group_btns.pack(fill="x", pady=(8, 0))
        self.btn_group_add = ttk.Button(
            group_btns, text="新增分组", width=8, command=self.on_new_group
        )
        self.btn_group_rename = ttk.Button(
            group_btns, text="重命名", width=7, command=self.on_rename_group,
            state="disabled",
        )
        self.btn_group_del = ttk.Button(
            group_btns, text="删除分组", width=8, command=self.on_delete_group,
            state="disabled",
        )
        self.btn_group_add.pack(side="left")
        self.btn_group_rename.pack(side="left", padx=(4, 0))
        self.btn_group_del.pack(side="left", padx=(4, 0))

        # --- 右侧：记录表格 ---
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        table_frame = ttk.Frame(right)
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "username", "secret", "tags", "group", "url", "updated")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "name": ("名称", 170, "w"),
            "username": ("账号 / 用户名", 140, "w"),
            "secret": ("密钥 / 密码", 140, "w"),
            "tags": ("标签", 130, "w"),
            "group": ("分组", 100, "center"),
            "url": ("网址", 160, "w"),
            "updated": ("更新时间", 145, "center"),
        }
        for col, (text, width, anchor) in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, minwidth=60, anchor=anchor)

        vsb = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        hsb = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="we")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # 记录右键菜单
        self.menu_records = tk.Menu(self.root, tearoff=0)
        self.menu_records.add_command(label="复制密钥", command=self.on_copy_secret)
        self.menu_records.add_command(label="复制账号", command=self.on_copy_account)
        self.menu_records.add_separator()
        self.menu_records.add_command(label="编辑", command=self.on_edit_record)
        self.menu_records.add_command(label="删除", command=self.on_delete_record)

    def _bind_events(self) -> None:
        self.group_list.bind("<<ListboxSelect>>", self._on_group_select)
        self.tree.bind("<Double-1>", lambda _e: self.on_edit_record())
        self.tree.bind("<Return>", lambda _e: self.on_edit_record())
        self.tree.bind("<Delete>", lambda _e: self.on_delete_record())
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Control-c>", lambda _e: self.on_copy_secret())
        self.search_entry.bind("<KeyRelease>", self.on_search_changed)
        self.search_entry.bind("<Escape>", self._clear_search)
        self.root.bind("<Control-n>", lambda _e: self.on_new_record())
        self.root.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------- 刷新

    def refresh_groups(self) -> None:
        groups = self.db.groups()
        total = self.db.record_count()
        ungrouped = self.db.ungrouped_count()

        self.group_list.delete(0, "end")
        self._group_ids = [None, UNGROUPED]
        self.group_list.insert("end", f"{ALL_LABEL} ({total})")
        self.group_list.insert("end", f"{UNG_LABEL} ({ungrouped})")
        for g in groups:
            self._group_ids.append(g.id)
            self.group_list.insert("end", f"{g.name} ({g.record_count})")

        # 尽量保持原选中项；分组被删等情况则回落到"全部记录"
        try:
            idx = self._group_ids.index(self.selected_group_id)
        except ValueError:
            idx = 0
            self.selected_group_id = None
        self.group_list.selection_clear(0, "end")
        self.group_list.selection_set(idx)
        self._update_group_buttons(idx)
        self.refresh_records()

    def refresh_records(self) -> None:
        if self.keyword:
            records = self.db.records(None, keyword=self.keyword)
        else:
            records = self.db.records(self.selected_group_id)
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        for r in records:
            self.tree.insert(
                "", "end", iid=str(r.id),
                values=(
                    r.name,
                    r.username,
                    self._display_secret(r.secret),
                    r.tags,
                    r.group_name or UNG_LABEL,
                    r.url,
                    r.updated_at,
                ),
            )
        total = self.db.record_count()
        if self.keyword:
            status = (
                f"搜索「{self.keyword}」找到 {len(records)} 条"
                f"（范围：全部分组，Esc 清除搜索）   ·   共 {total} 条"
            )
        else:
            if self.selected_group_id is None:
                where = ALL_LABEL
            elif self.selected_group_id == UNGROUPED:
                where = UNG_LABEL
            else:
                where = self._current_group_name()
            status = f"「{where}」显示 {len(records)} 条 / 共 {total} 条"
        self.status.config(text=f"{status}   ·   数据文件: {self.db.path}")

    def _current_group_name(self) -> str:
        for g in self.db.groups():
            if g.id == self.selected_group_id:
                return g.name
        return ALL_LABEL

    def _display_secret(self, secret: str) -> str:
        if self.show_secrets:
            return secret
        if not secret:
            return ""
        return "•" * min(len(secret), _MASK_MAX)

    def _update_group_buttons(self, idx: int) -> None:
        """仅真实分组（索引 >= 2）允许重命名/删除。"""
        custom = idx >= 2
        state = ["!disabled"] if custom else ["disabled"]
        self.btn_group_rename.state(state)
        self.btn_group_del.state(state)

    # ------------------------------------------------------------- 记录

    def on_new_record(self) -> None:
        default_gid = (
            self.selected_group_id
            if isinstance(self.selected_group_id, int)
            and self.selected_group_id > 0
            else None
        )
        dlg = RecordDialog(
            self.root, groups=self.db.groups(), default_group_id=default_gid
        )
        result = dlg.show()
        if result is None:
            return
        try:
            self.db.add_record(**result)
        except ValueError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return
        self.refresh_groups()

    def on_edit_record(self) -> None:
        record_id = self._selected_record_id()
        if record_id is None:
            messagebox.showinfo("提示", "请先在列表中选择一条记录", parent=self.root)
            return
        try:
            record = self.db.get_record(record_id)
        except ValueError as exc:
            messagebox.showwarning("提示", str(exc), parent=self.root)
            self.refresh_groups()
            return
        dlg = RecordDialog(self.root, groups=self.db.groups(), record=record)
        result = dlg.show()
        if result is None:
            return
        try:
            self.db.update_record(record_id, **result)
        except ValueError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return
        self.refresh_groups()

    def on_delete_record(self) -> None:
        record_id = self._selected_record_id()
        if record_id is None:
            messagebox.showinfo("提示", "请先在列表中选择一条记录", parent=self.root)
            return
        try:
            record = self.db.get_record(record_id)
        except ValueError as exc:
            messagebox.showwarning("提示", str(exc), parent=self.root)
            self.refresh_groups()
            return
        if not messagebox.askyesno(
            "删除记录", f"确定删除「{record.name}」？该操作不可撤销。", parent=self.root
        ):
            return
        self.db.delete_record(record_id)
        self.refresh_groups()

    def on_toggle_secrets(self) -> None:
        self.show_secrets = self.var_show.get()
        self.refresh_records()

    # ------------------------------------------------------------- 搜索

    def on_search_changed(self, _event=None) -> None:
        self.keyword = self.search_var.get().strip()
        self.refresh_records()

    def _clear_search(self, _event=None) -> None:
        self.search_var.set("")
        self.on_search_changed()

    # ------------------------------------------------------------- 复制

    def on_copy_secret(self) -> None:
        self._copy_field("secret", "密钥")

    def on_copy_account(self) -> None:
        self._copy_field("username", "账号")

    def _copy_field(self, field: str, label: str) -> None:
        record_id = self._selected_record_id()
        if record_id is None:
            messagebox.showinfo("提示", "请先在列表中选择一条记录", parent=self.root)
            return
        try:
            record = self.db.get_record(record_id)
        except ValueError as exc:
            messagebox.showwarning("提示", str(exc), parent=self.root)
            self.refresh_groups()
            return
        value = getattr(record, field, "") or ""
        if not value:
            messagebox.showinfo(
                "提示", f"「{record.name}」没有{label}", parent=self.root
            )
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()  # 立即写入系统剪贴板，确保其他窗口可用
        self._clipboard_value = value
        if self._clipboard_after is not None:
            self.root.after_cancel(self._clipboard_after)
        self._clipboard_after = self.root.after(COPY_CLEAR_MS, self._clear_clipboard)
        self.status.config(
            text=f"已复制「{record.name}」的{label}，{COPY_CLEAR_SECONDS} 秒后自动清空剪贴板"
        )

    def _clear_clipboard(self) -> None:
        """定时清空剪贴板；若用户已复制了别的内容则不动它。"""
        self._clipboard_after = None
        value, self._clipboard_value = self._clipboard_value, None
        if value is None:
            return
        try:
            current = self.root.clipboard_get()
        except tk.TclError:
            return  # 剪贴板已不是文本（如图片），不碰用户的内容
        if current == value:
            self.root.clipboard_clear()
            self.root.update()
            self.status.config(text="剪贴板已自动清空")

    # ------------------------------------------------------------- 备份

    def on_export_backup(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出加密备份",
            defaultextension=backup.FILE_EXTENSION,
            initialfile=(
                f"StoreApp-backup-{datetime.now():%Y%m%d-%H%M%S}"
                f"{backup.FILE_EXTENSION}"
            ),
            filetypes=backup.FILE_TYPES,
        )
        if not path:
            return
        password = ask_backup_password(
            self.root,
            "设置备份密码",
            "该密码用于加密备份文件，不会被保存在任何地方；\n"
            "遗忘后将无法恢复此备份。",
            confirm=True,
        )
        if not password:
            return
        payload = self.db.export_data()
        try:
            backup.export_file(path, password, payload)
        except Exception as exc:
            messagebox.showerror(
                "导出失败", f"写入备份文件失败：{exc}", parent=self.root
            )
            return
        messagebox.showinfo(
            "导出成功",
            f"已导出 {len(payload['groups'])} 个分组、"
            f"{len(payload['records'])} 条记录到：\n{path}",
            parent=self.root,
        )

    def on_import_backup(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="选择备份文件",
            filetypes=backup.FILE_TYPES,
        )
        if not path:
            return
        password = ask_backup_password(
            self.root,
            "输入备份密码",
            "输入导出该备份时设置的密码。",
            confirm=False,
        )
        if not password:
            return
        try:
            payload = backup.load_file(path, password)
        except backup.BackupError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)
            return
        summary = (
            f"备份包含 {len(payload.get('groups', []))} 个分组、"
            f"{len(payload['records'])} 条记录\n"
            f"导出时间：{payload.get('exported_at', '未知')}\n\n"
            "请选择导入方式："
        )
        mode = choose_import_mode(self.root, summary)
        if not mode:
            return
        try:
            stats = self.db.apply_import(payload, mode)
        except ValueError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)
            return
        self.refresh_groups()
        messagebox.showinfo(
            "导入完成",
            f"新增 {stats['records_added']} 条记录，"
            f"跳过重复 {stats['records_skipped']} 条，"
            f"新建分组 {stats['groups_created']} 个",
            parent=self.root,
        )

    def _selected_record_id(self) -> Optional[int]:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _on_tree_right_click(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        self.tree.focus(row)
        try:
            self.menu_records.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_records.grab_release()

    # ------------------------------------------------------------- 分组

    def _on_group_select(self, _event=None) -> None:
        selection = self.group_list.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self._group_ids):
            return
        self.selected_group_id = self._group_ids[idx]
        self._update_group_buttons(idx)
        self.refresh_records()

    def _selected_group_index(self) -> Optional[int]:
        selection = self.group_list.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < 2:  # 全部记录 / 未分组 不可改名删除
            return None
        return idx

    def on_new_group(self) -> None:
        name = ask_group_name(self.root, "新增分组")
        if not name:
            return
        try:
            self.db.add_group(name)
        except ValueError as exc:
            messagebox.showwarning("新增失败", str(exc), parent=self.root)
            return
        self.refresh_groups()

    def on_rename_group(self) -> None:
        idx = self._selected_group_index()
        if idx is None or idx >= len(self._group_ids):
            return
        group_id = self._group_ids[idx]
        current = self._current_group_name()
        name = ask_group_name(self.root, "重命名分组", initial=current)
        if not name or name == current:
            return
        try:
            self.db.rename_group(group_id, name)
        except ValueError as exc:
            messagebox.showwarning("重命名失败", str(exc), parent=self.root)
            return
        self.refresh_groups()

    def on_delete_group(self) -> None:
        idx = self._selected_group_index()
        if idx is None or idx >= len(self._group_ids):
            return
        group_id = self._group_ids[idx]
        name = self._current_group_name()
        count = next(
            (g.record_count for g in self.db.groups() if g.id == group_id), 0
        )
        hint = (
            f"分组「{name}」中有 {count} 条记录，删除后它们将变为「{UNG_LABEL}」。"
            if count
            else f"确定删除分组「{name}」？"
        )
        if not messagebox.askyesno("删除分组", hint, parent=self.root):
            return
        try:
            self.db.delete_group(group_id)
        except ValueError as exc:
            messagebox.showwarning("删除失败", str(exc), parent=self.root)
            return
        if self.selected_group_id == group_id:
            self.selected_group_id = None
        self.refresh_groups()

    # ------------------------------------------------------------- 其他

    def _on_close(self) -> None:
        # 关闭前清掉我们复制到剪贴板的密钥，避免残留
        if self._clipboard_after is not None:
            self.root.after_cancel(self._clipboard_after)
            self._clipboard_after = None
        if self._clipboard_value is not None:
            try:
                if self.root.clipboard_get() == self._clipboard_value:
                    self.root.clipboard_clear()
                    self.root.update()
            except tk.TclError:
                pass
            self._clipboard_value = None
        self.db.close()
        self.root.destroy()


def run() -> None:
    """启动 StoreApp。"""
    db = Database()
    root = tk.Tk()
    MainWindow(root, db)
    root.mainloop()
