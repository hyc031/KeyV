"""secret 字段的轻量混淆（非加密）。

按当前版本需求，数据为"本地明文 + 混淆"存储：
- 目的：防止他人随手打开数据文件直接看到密钥/密码；
- 边界：混淆钥写死在源码里，能被逆向还原，**不构成真正的加密**。
后续如需真正的安全保护，应升级为主密码 + AES-GCM（见 README 后续规划）。
"""

from __future__ import annotations

import base64

_KEY = b"StoreApp::local::vault"


def _xor(data: bytes) -> bytes:
    key = _KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encode(text: str) -> str:
    """把明文混淆为可安全写入数据库的字符串。空值原样返回空串。"""
    if not text:
        return ""
    return base64.b64encode(_xor(text.encode("utf-8"))).decode("ascii")


def decode(token: str) -> str:
    """还原混淆串。若内容不是合法混淆数据（例如早期明文），按原样返回。"""
    if not token:
        return ""
    try:
        return _xor(base64.b64decode(token.encode("ascii"), validate=True)).decode("utf-8")
    except Exception:
        return token
