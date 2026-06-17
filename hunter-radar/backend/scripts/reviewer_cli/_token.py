"""V1.5.6 接力期 m14t1 — reviewer_cli token 生成与校验。

V1.5.3 接力期 m11t4 拆分 TOKEN_HEX_LEN 为 _DEFAULT / _MIN / _PROD_RECOMMENDED,
V1.5.6 接力期 m14t1 沿用。本模块(_token)负责:
- TOKEN_HEX_LEN_DEFAULT / _MIN / _PROD_RECOMMENDED 3 个常量
- _resolve_token_hex_len(env 解析 + 下限保护)
- _secret_key(SECRET_KEY 沙箱 fallback)
- _gen_token(HMAC-SHA256 派生)
- _hash_token(SHA-256 摘要,只存 hash 不存明文)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

TOKEN_HEX_LEN_DEFAULT = 32
TOKEN_HEX_LEN_MIN = 16
TOKEN_HEX_LEN_PROD_RECOMMENDED = 64


def _resolve_token_hex_len() -> int:
    """V1.5.3 接力期 m11t4:解析 token 长度,env 覆盖 + 下限保护。

    优先级:
    1. env REVIEWER_TOKEN_HEX_LEN 显式设置 → 读取
    2. 未设 / 格式错 → fallback TOKEN_HEX_LEN_DEFAULT(32)
    3. 小于 TOKEN_HEX_LEN_MIN(16) → 升级到 TOKEN_HEX_LEN_MIN

    生产推荐 ≥64(TOKEN_HEX_LEN_PROD_RECOMMENDED),本函数不强制,
    只保证下限安全,推荐值由 SOP / deployment runbook 提示。
    """
    raw = os.environ.get("REVIEWER_TOKEN_HEX_LEN")
    if not raw:
        return TOKEN_HEX_LEN_DEFAULT
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return TOKEN_HEX_LEN_DEFAULT
    if n < TOKEN_HEX_LEN_MIN:
        return TOKEN_HEX_LEN_MIN
    return n


def _secret_key() -> bytes:
    """SECRET_KEY 沙箱 fallback(M5 锁定 dev-only)。"""
    return os.environ.get("SECRET_KEY", "dev-only-change-me-in-prod-32-bytes-min").encode("utf-8")


def _gen_token(name: str, role: str) -> str:
    """HMAC-SHA256(SECRET_KEY, name:role:nonce) hex 截 TOKEN_HEX_LEN 字符。

    V1.5.3 接力期 m11t4:token 长度从 env 解析(默认 32,生产 ≥64)。
    """
    nonce = secrets.token_hex(8)
    msg = f"{name}:{role}:{nonce}".encode("utf-8")
    sig = hmac.new(_secret_key(), msg, hashlib.sha256).hexdigest()
    return f"{nonce}{sig}"[:_resolve_token_hex_len() * 2]  # hex字符数 = 字节数 * 2


def _hash_token(token: str) -> str:
    """token hash(入库用,只存 hash 不存明文)。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
