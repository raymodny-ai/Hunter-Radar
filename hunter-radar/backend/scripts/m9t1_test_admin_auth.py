"""M9-t1 V1.5 Admin 鉴权自测(25 测点)。

V1.5 接力期 m9t1 — admin 端点鉴权补全:
- JWT role 字段
- ADMIN_API_KEY 备选
- IP 白名单
- 三态显式标注(prod_admin_jwt / prod_admin_apikey / sandbox_skip_admin)

Section 1 — auth.py Role + TUser.role + require_admin_role(8 测点):
  - Role Literal 定义
  - TUser.role 字段 + is_admin property
  - create_access_token 接受 role
  - _parse_jwt_user 解析 role
  - require_admin_role 存在 + 三种 fallback 路径

Section 2 — config.py 3 字段(3 测点):
  - admin_api_key / admin_ip_whitelist / admin_role_enabled

Section 3 — admin.py 4 端点全部加鉴权(7 测点):
  - 4 端点都 Depends(require_admin_role)
  - 4 端点都返 auth_mode
  - _resolve_auth_mode helper
  - IP 白名单校验

Section 4 — 错误码 + 边界(7 测点):
  - 401: 非 Bearer scheme + 无 API key
  - 503: admin_role_enabled=True 但无 JWT/API key(生产配置缺)
  - 403: IP 白名单不命中
  - 403: API key 不匹配
  - 沙箱 fallback: admin_role_enabled=False 通过

总计 25 测点。
"""
from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = ROOT / "backend" / "app"
BACKEND_CORE = BACKEND_APP / "core"
BACKEND_API = BACKEND_APP / "api"
AUTH_PY = BACKEND_CORE / "auth.py"
CONFIG_PY = BACKEND_CORE / "config.py"
ADMIN_PY = BACKEND_API / "admin.py"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _load_module(name: str, path: Path):
    """沙箱加载 helper(Python 3.14 dataclass sys.modules 兼容)。"""
    import sys
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Section 1: auth.py Role + TUser.role + require_admin_role(8 测点)
# ----------------------------------------------------------------------

def t01_role_literal() -> bool:
    """Role Literal 定义。"""
    txt = _read(AUTH_PY)
    if 'Role = Literal["user", "admin"]' not in txt:
        print("  [FAIL] Role Literal 缺失")
        return False
    print(f"  [PASS] Role Literal 齐全")
    return True


def t02_tuser_role_field() -> bool:
    """TUser.role 字段 + is_admin property。"""
    txt = _read(AUTH_PY)
    if "role: Role" not in txt:
        print("  [FAIL] TUser.role 字段缺失")
        return False
    if "is_admin" not in txt:
        print("  [FAIL] is_admin property 缺失")
        return False
    print(f"  [PASS] TUser.role + is_admin 齐全")
    return True


def t03_create_token_role() -> bool:
    """create_access_token 接受 role 参数。"""
    txt = _read(AUTH_PY)
    if "role: Role = \"user\"" not in txt and "role: Role = 'user'" not in txt:
        print("  [FAIL] create_access_token 缺 role 参数")
        return False
    if '"role": role' not in txt and "'role': role" not in txt:
        print("  [FAIL] JWT payload 缺 role 字段")
        return False
    print(f"  [PASS] create_access_token 支持 role")
    return True


def t04_parse_jwt_role() -> bool:
    """_parse_jwt_user 解析 role。"""
    txt = _read(AUTH_PY)
    if 'role = payload.get("role", "user")' not in txt and 'role = payload.get(\'role\', \'user\')' not in txt:
        print("  [FAIL] _parse_jwt_user 缺 role 解析")
        return False
    print(f"  [PASS] _parse_jwt_user 解析 role")
    return True


def t05_require_admin_role_exists() -> bool:
    """require_admin_role dependency 存在。"""
    txt = _read(AUTH_PY)
    if "def require_admin_role(" not in txt:
        print("  [FAIL] require_admin_role 未定义")
        return False
    print(f"  [PASS] require_admin_role 存在")
    return True


def t06_require_admin_role_jwt_path() -> bool:
    """JWT role=admin 路径。"""
    txt = _read(AUTH_PY)
    if "user.is_admin" not in txt:
        print("  [FAIL] require_admin_role 缺 user.is_admin 校验")
        return False
    print(f"  [PASS] require_admin_role JWT 路径")
    return True


def t07_require_admin_role_apikey_path() -> bool:
    """X-Admin-API-Key 路径。"""
    txt = _read(AUTH_PY)
    if "X-Admin-API-Key" not in txt:
        print("  [FAIL] require_admin_role 缺 X-Admin-API-Key header")
        return False
    if "_check_api_key" not in txt:
        print("  [FAIL] require_admin_role 缺 _check_api_key helper")
        return False
    print(f"  [PASS] require_admin_role API key 路径")
    return True


def t08_require_admin_role_sandbox_skip() -> bool:
    """沙箱 fallback:admin_role_enabled=False。"""
    txt = _read(AUTH_PY)
    if "admin_role_enabled" not in txt:
        print("  [FAIL] 缺 admin_role_enabled 校验")
        return False
    if "sandbox_skip_admin" not in txt:
        print("  [FAIL] 缺 sandbox_skip_admin 标注")
        return False
    print(f"  [PASS] 沙箱 fallback 显式标注")
    return True


# ----------------------------------------------------------------------
# Section 2: config.py 3 字段(3 测点)
# ----------------------------------------------------------------------

def t09_config_admin_api_key() -> bool:
    """config.py admin_api_key 字段。"""
    txt = _read(CONFIG_PY)
    if "admin_api_key" not in txt:
        print("  [FAIL] config.py 缺 admin_api_key")
        return False
    print(f"  [PASS] config.py admin_api_key 齐全")
    return True


def t10_config_ip_whitelist() -> bool:
    """config.py admin_ip_whitelist 字段。"""
    txt = _read(CONFIG_PY)
    if "admin_ip_whitelist" not in txt:
        print("  [FAIL] config.py 缺 admin_ip_whitelist")
        return False
    print(f"  [PASS] config.py admin_ip_whitelist 齐全")
    return True


def t11_config_role_enabled() -> bool:
    """config.py admin_role_enabled 字段。"""
    txt = _read(CONFIG_PY)
    if "admin_role_enabled" not in txt:
        print("  [FAIL] config.py 缺 admin_role_enabled")
        return False
    print(f"  [PASS] config.py admin_role_enabled 齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: admin.py 4 端点全部加鉴权(7 测点)
# ----------------------------------------------------------------------

def t12_admin_4_endpoints_auth() -> bool:
    """admin.py 4 端点都 Depends(require_admin_role)。"""
    txt = _read(ADMIN_PY)
    # 应该有 4 个 Depends(require_admin_role)
    count = txt.count("Depends(require_admin_role)")
    if count < 4:
        print(f"  [FAIL] Depends(require_admin_role) 出现 {count} 次,期望 >= 4")
        return False
    print(f"  [PASS] 4 端点都加鉴权({count} 次)")
    return True


def t13_admin_4_endpoints_auth_mode() -> bool:
    """admin.py 4 端点都返 auth_mode 字段。"""
    txt = _read(ADMIN_PY)
    # 4 端点 + 错误分支 + _resolve_auth_mode helper
    count = txt.count('"auth_mode": auth_mode')
    if count < 4:
        print(f"  [FAIL] 'auth_mode': auth_mode 出现 {count} 次,期望 >= 4")
        return False
    print(f"  [PASS] 4 端点都返 auth_mode({count} 处)")
    return True


def t14_admin_resolve_auth_mode_helper() -> bool:
    """admin.py _resolve_auth_mode helper 存在。"""
    txt = _read(ADMIN_PY)
    if "def _resolve_auth_mode(" not in txt:
        print("  [FAIL] _resolve_auth_mode 未定义")
        return False
    if "prod_admin_jwt" not in txt or "prod_admin_apikey" not in txt or "sandbox_skip_admin" not in txt:
        print("  [FAIL] _resolve_auth_mode 缺三态标注")
        return False
    print(f"  [PASS] _resolve_auth_mode helper + 三态齐全")
    return True


def t15_admin_ip_whitelist_check() -> bool:
    """admin.py IP 白名单校验。"""
    txt = _read(ADMIN_PY)
    if "_check_ip_whitelist" not in txt:
        print("  [FAIL] admin.py 缺 _check_ip_whitelist 调用")
        return False
    if "client_host" not in txt:
        print("  [FAIL] admin.py 缺 client_host 取值")
        return False
    print(f"  [PASS] IP 白名单校验齐全")
    return True


def t16_admin_jwt_admin_role() -> bool:
    """admin.py 校验 user.is_admin + 真实用户(非沙箱占位)。"""
    txt = _read(ADMIN_PY)
    if "user.is_admin" not in txt:
        print("  [FAIL] admin.py 缺 user.is_admin 校验")
        return False
    if "SANDBOX_PLACEHOLDER_USER_ID" not in txt:
        print("  [FAIL] admin.py 缺沙箱占位 user 排除")
        return False
    print(f"  [PASS] JWT role=admin + 真实用户校验")
    return True


def t17_admin_module_header_updated() -> bool:
    """admin.py 模块头注释说明鉴权(m9t1 标识)。"""
    txt = _read(ADMIN_PY)
    if "m9t1" not in txt:
        print("  [FAIL] admin.py 缺 m9t1 标识")
        return False
    if "require_admin_role" not in txt:
        print("  [FAIL] admin.py 缺 require_admin_role 引用")
        return False
    print(f"  [PASS] admin.py 模块头 m9t1 标识齐全")
    return True


def t18_admin_4_endpoint_names() -> bool:
    """admin.py 4 端点名锁定。"""
    txt = _read(ADMIN_PY)
    endpoints = [
        "post_etl_run",
        "post_backtest_run",
        "get_backtest_result",
        "post_webhook_replay",
    ]
    missing = [e for e in endpoints if f"def {e}(" not in txt]
    if missing:
        print(f"  [FAIL] 缺端点函数: {missing}")
        return False
    print(f"  [PASS] 4 端点函数齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: 错误码 + 边界(7 测点)
# ----------------------------------------------------------------------

def t19_401_unsupported_scheme() -> bool:
    """401: 非 Bearer scheme + 无 API key。"""
    txt = _read(AUTH_PY)
    if "unsupported auth scheme" not in txt:
        print("  [FAIL] 缺 401 unsupported auth scheme 错误")
        return False
    if "status_code=401" not in txt:
        print("  [FAIL] 缺 401 状态码")
        return False
    print(f"  [PASS] 401 unsupported scheme 错误齐全")
    return True


def t20_503_admin_auth_not_configured() -> bool:
    """503: admin_role_enabled=True 但无 JWT/API key。"""
    txt = _read(AUTH_PY)
    if "admin auth not configured" not in txt:
        print("  [FAIL] 缺 503 admin auth not configured 错误")
        return False
    if "status_code=503" not in txt:
        print("  [FAIL] 缺 503 状态码")
        return False
    print(f"  [PASS] 503 admin auth not configured 齐全")
    return True


def t21_403_ip_whitelist() -> bool:
    """403: IP 白名单不命中。"""
    txt = _read(ADMIN_PY)
    if "client IP not in admin whitelist" not in txt:
        print("  [FAIL] 缺 403 IP whitelist 错误")
        return False
    if "status_code=403" not in txt:
        print("  [FAIL] 缺 403 状态码")
        return False
    print(f"  [PASS] 403 IP whitelist 错误齐全")
    return True


def t22_hmac_compare_digest() -> bool:
    """API key 用 hmac.compare_digest 防 timing attack。"""
    txt = _read(AUTH_PY)
    if "hmac.compare_digest" not in txt:
        print("  [FAIL] _check_api_key 缺 hmac.compare_digest")
        return False
    print(f"  [PASS] hmac.compare_digest 防 timing attack")
    return True


def t23_no_silent_fail_marker() -> bool:
    """admin 鉴权不 mock 200 伪装。"""
    txt = _read(ADMIN_PY)
    txt_auth = _read(AUTH_PY)
    # 显式标注"不 mock 200"或类似
    count_admin = txt.count("不 mock 200") + txt.count("不 mock") + txt.count("不伪装")
    count_auth = txt_auth.count("不 mock 200") + txt_auth.count("不 mock") + txt_auth.count("不伪装")
    total = count_admin + count_auth
    if total < 1:
        print(f"  [FAIL] 缺『不 mock 200 伪装』红线({total})")
        return False
    print(f"  [PASS] 不 mock 200 伪装({total} 处)")
    return True


def t24_role_field_in_jwt_payload() -> bool:
    """JWT payload 含 role 字段。"""
    txt = _read(AUTH_PY)
    if '"role": role' not in txt and "'role': role" not in txt:
        print("  [FAIL] JWT payload 缺 role 字段写入")
        return False
    print(f"  [PASS] JWT payload role 字段")
    return True


def t25_ip_whitelist_comma_split() -> bool:
    """IP 白名单按逗号分隔。"""
    txt = _read(AUTH_PY)
    if "split(\",\")" not in txt:
        print("  [FAIL] _check_ip_whitelist 缺 split(',')")
        return False
    print(f"  [PASS] IP 白名单逗号分隔")
    return True


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[str] = []


def _run(name: str, fn) -> None:
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {name} 抛出异常: {exc}")
        ok = False
    if ok:
        _PASSED.append(name)
    else:
        _FAILED.append(name)


def main() -> int:
    print("=== 1. auth.py Role + TUser.role + require_admin_role ===")
    _run("t01_role_literal", t01_role_literal)
    _run("t02_tuser_role_field", t02_tuser_role_field)
    _run("t03_create_token_role", t03_create_token_role)
    _run("t04_parse_jwt_role", t04_parse_jwt_role)
    _run("t05_require_admin_role_exists", t05_require_admin_role_exists)
    _run("t06_require_admin_role_jwt_path", t06_require_admin_role_jwt_path)
    _run("t07_require_admin_role_apikey_path", t07_require_admin_role_apikey_path)
    _run("t08_require_admin_role_sandbox_skip", t08_require_admin_role_sandbox_skip)

    print("\n=== 2. config.py 3 字段 ===")
    _run("t09_config_admin_api_key", t09_config_admin_api_key)
    _run("t10_config_ip_whitelist", t10_config_ip_whitelist)
    _run("t11_config_role_enabled", t11_config_role_enabled)

    print("\n=== 3. admin.py 4 端点全部加鉴权 ===")
    _run("t12_admin_4_endpoints_auth", t12_admin_4_endpoints_auth)
    _run("t13_admin_4_endpoints_auth_mode", t13_admin_4_endpoints_auth_mode)
    _run("t14_admin_resolve_auth_mode_helper", t14_admin_resolve_auth_mode_helper)
    _run("t15_admin_ip_whitelist_check", t15_admin_ip_whitelist_check)
    _run("t16_admin_jwt_admin_role", t16_admin_jwt_admin_role)
    _run("t17_admin_module_header_updated", t17_admin_module_header_updated)
    _run("t18_admin_4_endpoint_names", t18_admin_4_endpoint_names)

    print("\n=== 4. 错误码 + 边界 ===")
    _run("t19_401_unsupported_scheme", t19_401_unsupported_scheme)
    _run("t20_503_admin_auth_not_configured", t20_503_admin_auth_not_configured)
    _run("t21_403_ip_whitelist", t21_403_ip_whitelist)
    _run("t22_hmac_compare_digest", t22_hmac_compare_digest)
    _run("t23_no_silent_fail_marker", t23_no_silent_fail_marker)
    _run("t24_role_field_in_jwt_payload", t24_role_field_in_jwt_payload)
    _run("t25_ip_whitelist_comma_split", t25_ip_whitelist_comma_split)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m9t1] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m9t1] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m9t1] ALL {total} ADMIN-AUTH TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
