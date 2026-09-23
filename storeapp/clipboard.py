"""Windows 剪贴板操作（ctypes 实现，不依赖 Tk）。

供 pywebview 界面调用：写入文本、读取文本、按值清空。
剪贴板数据由系统持有，程序退出后仍保留（与 v1.1 的 Tk 行为一致）。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# 64 位句柄必须显式声明返回类型，否则 ctypes 默认截断成 32 位 int 导致句柄失效
_HANDLE = wintypes.HANDLE
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = _HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, _HANDLE]
user32.SetClipboardData.restype = _HANDLE
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = _HANDLE
kernel32.GlobalLock.argtypes = [_HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [_HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [_HANDLE]
kernel32.GlobalFree.restype = _HANDLE

# Windows Clipboard 不是线程安全的，偶发被其他进程占用，做小重试
_OPEN_RETRIES = 8
_OPEN_DELAY = 0.05


def _open() -> bool:
    for _ in range(_OPEN_RETRIES):
        if user32.OpenClipboard(None):
            return True
        time.sleep(_OPEN_DELAY)
    return False


def get_text() -> str | None:
    """读取剪贴板文本；非文本内容或占用失败返回 None。"""
    if not _open():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_text(text: str) -> bool:
    """写入文本到剪贴板。成功返回 True。"""
    cleaned = (text or "").replace("\x00", "")
    if not _open():
        return False
    try:
        user32.EmptyClipboard()
        buffer = ctypes.create_unicode_buffer(cleaned)
        size = ctypes.sizeof(buffer)
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, buffer, size)
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        # 成功后内存所有权移交系统，不能 free
        return True
    finally:
        user32.CloseClipboard()


def clear_if(value: str) -> bool:
    """若剪贴板内容仍等于 value 则清空（避免误清用户后来复制的东西）。"""
    current = get_text()
    if current is None or current != value:
        return False
    if not _open():
        return False
    try:
        user32.EmptyClipboard()
        return True
    finally:
        user32.CloseClipboard()
