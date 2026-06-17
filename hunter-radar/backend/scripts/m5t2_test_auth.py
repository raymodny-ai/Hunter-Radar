"""§6.2 m5t2 BD-075 JWT 自测(沙箱友好)。

不依赖 PG / Redis / 外部 API;仅在 sys.modules 注入 stub config 后 import auth。

测点(11):
01  JWT round-trip(编解码 sub / tier / exp)
02  JWT tier=pro 传递
03  JWT 篡改 → ValueError(签名错)
04  JWT 过期 → ValueError(expire_seconds=-1)
05  X-User-Id 兼容(无 Authorization 走 fallback)
06  沙箱占位(无任何 header → SANDBOX_PLACEHOLDER_USER_ID + is_authenticated=False)
07  Authorization: Bearer <JWT> 正常解析
08  Authorization: Basic xxx → 401(unsupported scheme)
09  Authorization: Bearer invalid → 401(invalid token)
10  require_pro:free → 402,pro → pass
11  is_sandbox_token:占位 token → True,真实 token → False
"""
from __future__ import annotations

import os
import sys
import time
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

# === 1. 装 stub app.core.config(沙箱无 pydantic_settings 时短路) ============
_STUB_SETTINGS = SimpleNamespace(
    secret_key=os.environ.get("HR_AUTH_DEV_SECRET") or "dev-only-change-me-in-prod-32-bytes-min",
    jwt_algorithm="HS256",
    jwt_expire_minutes=60 * 24 * 7,  # 7 天
)
_stub_cfg = types.ModuleType("app.core.config")
_stub_cfg.settings = _STUB_SETTINGS
sys.modules["app.core.config"] = _stub_cfg

# 锁住 HR_AUTH_DEV_SECRET,避免 auth.py 末尾覆盖
os.environ["HR_AUTH_DEV_SECRET"] = _STUB_SETTINGS.secret_key

# === 2. 注入 sys.path,把 backend/ 放进去(确保 `from app.core.auth` 找得到) ===
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# === 3. import auth(此时 config 已是 stub) ===================================
from fastapi import HTTPException  # noqa: E402

from app.core.auth import (  # noqa: E402
    SANDBOX_PLACEHOLDER_USER_ID,
    TUser,
    create_access_token,
    decode_token,
    get_current_user,
    is_sandbox_token,
    require_pro,
)

# === 4. 测试 harness =========================================================

_RESULTS: list[tuple[str, str, str | None]] = []


def _run(name: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        _RESULTS.append((name, "FAIL", f"assert: {e}"))
    except Exception as e:  # noqa: BLE001
        _RESULTS.append((name, "ERROR", f"{type(e).__name__}: {e}"))
    else:
        _RESULTS.append((name, "PASS", None))


# === 5. 11 个测点 ===========================================================


def t01_jwt_round_trip() -> None:
    uid = uuid4()
    token = create_access_token(uid, tier="free")
    payload = decode_token(token)
    assert payload["sub"] == str(uid), f"sub mismatch: {payload['sub']!r}"
    assert payload["tier"] == "free"
    assert "exp" in payload and int(payload["exp"]) > int(time.time())


def t02_jwt_pro_tier() -> None:
    uid = uuid4()
    token = create_access_token(uid, tier="pro")
    payload = decode_token(token)
    assert payload["tier"] == "pro", f"tier mismatch: {payload['tier']!r}"


def t03_jwt_tampered_rejected() -> None:
    token = create_access_token(uuid4(), tier="free")
    h, p, s = token.split(".")
    tampered = f"{h}.{p}.{'A' * len(s)}"
    try:
        decode_token(tampered)
    except ValueError as e:
        return
    raise AssertionError("expected ValueError on tampered token")


def t04_jwt_expired_rejected() -> None:
    token = create_access_token(uuid4(), tier="free", expire_seconds=-1)
    try:
        decode_token(token)
    except ValueError:
        return
    raise AssertionError("expected ValueError on expired token")


def t05_x_user_id_compat() -> None:
    uid = uuid4()
    user = get_current_user(authorization=None, x_user_id=str(uid))
    assert isinstance(user, TUser)
    assert user.user_id == uid
    assert user.tier == "free"
    assert user.is_authenticated is True


def t06_sandbox_placeholder() -> None:
    user = get_current_user(authorization=None, x_user_id=None)
    assert isinstance(user, TUser)
    assert user.user_id == SANDBOX_PLACEHOLDER_USER_ID
    assert user.is_authenticated is False
    assert user.is_pro is False


def t07_bearer_jwt() -> None:
    uid = uuid4()
    token = create_access_token(uid, tier="pro")
    user = get_current_user(authorization=f"Bearer {token}", x_user_id=None)
    assert user.user_id == uid
    assert user.tier == "pro"
    assert user.is_pro is True
    assert user.is_authenticated is True


def t08_unsupported_scheme_401() -> None:
    try:
        get_current_user(authorization="Basic xyz", x_user_id=None)
    except HTTPException as e:
        assert e.status_code == 401, f"expected 401, got {e.status_code}"
        return
    raise AssertionError("expected HTTPException 401 on Basic scheme")


def t09_invalid_jwt_401() -> None:
    try:
        get_current_user(authorization="Bearer not.a.jwt", x_user_id=None)
    except HTTPException as e:
        assert e.status_code == 401, f"expected 401, got {e.status_code}"
        return
    raise AssertionError("expected HTTPException 401 on malformed JWT")


def t10_require_pro() -> None:
    free_user = TUser(
        user_id=uuid4(),
        tier="free",
        exp=datetime.now(tz=timezone.utc),
    )
    try:
        require_pro(user=free_user)
    except HTTPException as e:
        assert e.status_code == 402, f"expected 402, got {e.status_code}"
        assert e.detail.get("upgrade_url") == "/pricing"
    else:
        raise AssertionError("expected HTTPException 402 for free user")

    pro_user = TUser(
        user_id=uuid4(),
        tier="pro",
        exp=datetime.now(tz=timezone.utc),
    )
    out = require_pro(user=pro_user)
    assert out is pro_user
    assert out.is_pro is True


def t11_is_sandbox_token() -> None:
    placeholder_tok = create_access_token(SANDBOX_PLACEHOLDER_USER_ID, tier="free")
    assert is_sandbox_token(placeholder_tok) is True
    real_tok = create_access_token(uuid4(), tier="free")
    assert is_sandbox_token(real_tok) is False


# === 6. 跑测点 + 汇总 ========================================================


def main() -> int:
    tests = [
        ("01_jwt_round_trip", t01_jwt_round_trip),
        ("02_jwt_pro_tier", t02_jwt_pro_tier),
        ("03_jwt_tampered_rejected", t03_jwt_tampered_rejected),
        ("04_jwt_expired_rejected", t04_jwt_expired_rejected),
        ("05_x_user_id_compat", t05_x_user_id_compat),
        ("06_sandbox_placeholder", t06_sandbox_placeholder),
        ("07_bearer_jwt", t07_bearer_jwt),
        ("08_unsupported_scheme_401", t08_unsupported_scheme_401),
        ("09_invalid_jwt_401", t09_invalid_jwt_401),
        ("10_require_pro", t10_require_pro),
        ("11_is_sandbox_token", t11_is_sandbox_token),
    ]
    for name, fn in tests:
        _run(name, fn)
    print()
    for name, status, err in _RESULTS:
        line = f"  [{status}] {name}"
        if err:
            line += f"  -- {err}"
        print(line)
    fail = [r for r in _RESULTS if r[1] != "PASS"]
    print()
    if fail:
        print(f"[m5t2] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t2] ALL {len(_RESULTS)} AUTH TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
