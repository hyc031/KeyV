"""加密备份文件的读写。

格式（二进制）：
    MAGIC(19B) | salt(16B) | nonce(12B) | AES-256-GCM(ciphertext||tag)

- 密钥派生：PBKDF2-HMAC-SHA256，20 万轮；
- 加密算法：AES-256-GCM，MAGIC 作为附加认证数据（AAD），防止头部被篡改；
- 密码由用户在导出/导入时输入，不保存在任何地方，遗忘即无法恢复该备份。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"STOREAPP.BACKUP.V1"
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16
PBKDF2_ITERATIONS = 200_000

#: 备份文件扩展名与文件类型描述（供文件对话框复用）
FILE_TYPES = [("StoreApp 加密备份", "*.sab"), ("所有文件", "*.*")]
FILE_EXTENSION = ".sab"


class BackupError(Exception):
    """备份读写失败，message 为可直接展示给用户的中文说明。"""


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )


def export_file(path, password: str, payload: dict) -> None:
    """把 payload（dict）加密写入备份文件。"""
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(password, salt)
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, blob, MAGIC)
    Path(path).write_bytes(MAGIC + salt + nonce + ciphertext)


def load_file(path, password: str) -> dict:
    """读取并解密备份文件；密码错误/文件损坏都会抛出 BackupError。"""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise BackupError(f"无法读取备份文件：{exc}") from exc

    head = len(MAGIC)
    if not raw.startswith(MAGIC):
        raise BackupError("这不是 StoreApp 备份文件")
    if len(raw) < head + SALT_LEN + NONCE_LEN + TAG_LEN:
        raise BackupError("备份文件不完整或已损坏")

    salt = raw[head: head + SALT_LEN]
    nonce = raw[head + SALT_LEN: head + SALT_LEN + NONCE_LEN]
    ciphertext = raw[head + SALT_LEN + NONCE_LEN:]
    key = _derive_key(password, salt)

    try:
        blob = AESGCM(key).decrypt(nonce, ciphertext, MAGIC)
    except Exception as exc:  # cryptography 抛 InvalidTag：密码错或内容被改动
        raise BackupError("密码错误，或备份文件已被篡改/损坏") from exc

    try:
        payload = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BackupError("备份内容解析失败") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise BackupError("备份文件内容格式不正确")
    return payload
