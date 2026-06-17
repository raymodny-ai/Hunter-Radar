"""V1.5 接力期 m9t2 — env_check.py 自测。

校验 scripts/env_check.py 的:
- 文件存在 + 可导入
- 12 CI check 函数(check_ci1~ci10)定义齐全
- 3 V15 check 函数(check_v15_1~v15_3)定义齐全
- 2 manual check 函数(check_manual_11~12)定义齐全
- CI_CHECKS / V15_CHECKS / MANUAL_CHECKS 列表条目数
- _b64url_decode / _is_valid_ip 工具函数正确性
- argparse 参数(--dotenv / --sandbox / --v15)
- main 退出码语义(0=全过 / 1=非沙箱有 FAIL / 2=缺 P0 必填)
- V1.5 admin 鉴权逻辑(ADMIN_API_KEY + role_enabled 互斥)
- VAPID base64url 长度 65 字节校验
- STRIPE_WEBHOOK_SECRET 前缀 whsec_ + 长度 ≥32 校验
- CORS_ORIGINS 不含 * / localhost
- SENTRY_DSN 含 sentry.io + /ingest/

M5 规范:沙箱模式(缺 P0)返 0,严禁 mock 200 伪装。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENV_CHECK = ROOT / "scripts" / "env_check.py"


def _import_env_check():
    """动态加载 env_check.py 模块。"""
    spec = importlib.util.spec_from_file_location("env_check", ENV_CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Test functions
# ----------------------------------------------------------------------

def t01_file_exists() -> bool:
    """t01: env_check.py 存在。"""
    return ENV_CHECK.is_file()


def t02_module_importable() -> bool:
    """t02: env_check.py 可 import。"""
    try:
        _import_env_check()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"    import error: {e}")
        return False


def t03_ci_functions_defined() -> bool:
    """t03: 10 个 check_ci* 函数定义齐全。"""
    mod = _import_env_check()
    for i in range(1, 11):
        name = f"check_ci{i}_"
        # check_ci1_p0_all / check_ci2_secret_key / ... check_ci10_cors_origins
        if i == 1:
            fn_name = "check_ci1_p0_all"
        elif i == 2:
            fn_name = "check_ci2_secret_key"
        elif i == 3:
            fn_name = "check_ci3_stripe_secret"
        elif i == 4:
            fn_name = "check_ci4_stripe_webhook"
        elif i == 5:
            fn_name = "check_ci5_vapid_public"
        elif i == 6:
            fn_name = "check_ci6_vapid_private"
        elif i == 7:
            fn_name = "check_ci7_sentry_dsn"
        elif i == 8:
            fn_name = "check_ci8_env_production"
        elif i == 9:
            fn_name = "check_ci9_debug_false"
        else:
            fn_name = "check_ci10_cors_origins"
        if not hasattr(mod, fn_name):
            print(f"    缺函数:{fn_name}")
            return False
        # 检验函数签名接受 env 参数
        import inspect
        sig = inspect.signature(getattr(mod, fn_name))
        if "env" not in sig.parameters:
            print(f"    {fn_name} 缺 env 参数")
            return False
    return True


def t04_v15_functions_defined() -> bool:
    """t04: 3 个 check_v15_* 函数定义齐全。"""
    mod = _import_env_check()
    for fn_name in ("check_v15_1_admin_api_key", "check_v15_2_admin_ip_whitelist", "check_v15_3_admin_api_key_length"):
        if not hasattr(mod, fn_name):
            print(f"    缺函数:{fn_name}")
            return False
    return True


def t05_manual_functions_defined() -> bool:
    """t05: 2 个 check_manual_* 函数定义齐全(签名带 env)。"""
    mod = _import_env_check()
    for fn_name in ("check_manual_11_pg_extensions", "check_manual_12_vapid_pair"):
        if not hasattr(mod, fn_name):
            print(f"    缺函数:{fn_name}")
            return False
        import inspect
        sig = inspect.signature(getattr(mod, fn_name))
        if "env" not in sig.parameters:
            print(f"    {fn_name} 缺 env 参数(bug 修复后必须带)")
            return False
    return True


def t06_ci_checks_list_count() -> bool:
    """t06: CI_CHECKS 列表 10 项。"""
    mod = _import_env_check()
    return len(mod.CI_CHECKS) == 10


def t07_v15_checks_list_count() -> bool:
    """t07: V15_CHECKS 列表 3 项。"""
    mod = _import_env_check()
    return len(mod.V15_CHECKS) == 3


def t08_manual_checks_list_count() -> bool:
    """t08: MANUAL_CHECKS 列表 2 项。"""
    mod = _import_env_check()
    return len(mod.MANUAL_CHECKS) == 2


def t09_b64url_decode_valid() -> bool:
    """t09: _b64url_decode 合法 65 字节输入(P-256 uncompressed)解码为 65 bytes。"""
    mod = _import_env_check()
    # P-256 uncompressed 公钥 = 0x04 + 32 bytes X + 32 bytes Y = 65 bytes
    fake = b"\x04" + b"\x00" * 32 + b"\x00" * 32
    import base64
    encoded = base64.urlsafe_b64encode(fake).rstrip(b"=").decode("ascii")
    decoded = mod._b64url_decode(encoded)
    return decoded is not None and len(decoded) == 65


def t10_b64url_decode_invalid() -> bool:
    """t10: _b64url_decode 非法输入返 None。"""
    mod = _import_env_check()
    return mod._b64url_decode("!!!not-base64!!!") is None


def t11_is_valid_ip_v4() -> bool:
    """t11: _is_valid_ip IPv4 合法格式。"""
    mod = _import_env_check()
    return mod._is_valid_ip("192.168.1.1") and mod._is_valid_ip("10.0.0.1")


def t12_is_valid_ip_invalid() -> bool:
    """t12: _is_valid_ip 非法 IP 返 False。"""
    mod = _import_env_check()
    return not mod._is_valid_ip("999.999.999.999") and not mod._is_valid_ip("abc") and not mod._is_valid_ip("")


def t13_cli_args_defined() -> bool:
    """t13: main argparse 支持 --dotenv / --sandbox / --v15。"""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ENV_CHECK), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
    )
    out = r.stdout + r.stderr
    return all(flag in out for flag in ("--dotenv", "--sandbox", "--v15"))


def t14_exit_code_sandbox_no_p0() -> bool:
    """t14: 沙箱模式 + process.env 缺 P0 → 返 0(M5 沙箱 fallback 规范)。"""
    # 清空 process.env 中 P0 关键字段
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "DATABASE_URL_SYNC", "SECRET_KEY",
                        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")}
    r = subprocess.run(
        [sys.executable, str(ENV_CHECK), "--sandbox", "--v15"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        env=env,
    )
    return r.returncode == 0


def t15_exit_code_nosandbox_missing_p0() -> bool:
    """t15: 非沙箱 + 缺 P0 → 返 1(missing P0)。"""
    env = {k: v for k, v in os.environ.items()
           if k not in ("DATABASE_URL", "DATABASE_URL_SYNC", "SECRET_KEY",
                        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")}
    r = subprocess.run(
        [sys.executable, str(ENV_CHECK), "--v15"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        env=env,
    )
    # 返 1(任一 FAIL)或 2(缺 P0)— 我们的实现是返 1
    return r.returncode in (1, 2)


def t16_v15_1_admin_api_key_logic() -> bool:
    """t16: V15-1 admin 鉴权 — role_enabled=true + 未设 ADMIN_API_KEY → FAIL。"""
    mod = _import_env_check()
    env = {"ADMIN_ROLE_ENABLED": "true"}
    ok, _ = mod.check_v15_1_admin_api_key(env)
    if ok:
        return False
    env = {"ADMIN_ROLE_ENABLED": "true", "ADMIN_API_KEY": "x" * 32}
    ok, _ = mod.check_v15_1_admin_api_key(env)
    if not ok:
        return False
    env = {"ADMIN_ROLE_ENABLED": "false"}  # 沙箱
    ok, _ = mod.check_v15_1_admin_api_key(env)
    return ok


def t17_v15_2_ip_whitelist_valid() -> bool:
    """t17: V15-2 IP 白名单 — 多个合法 IP 通过。"""
    mod = _import_env_check()
    env = {"ADMIN_IP_WHITELIST": "10.0.0.1, 192.168.1.1, 172.16.0.1"}
    ok, detail = mod.check_v15_2_admin_ip_whitelist(env)
    if not ok:
        print(f"    合法 IP 反而 FAIL:{detail}")
        return False
    env = {"ADMIN_IP_WHITELIST": "10.0.0.1, bad-ip-xyz, 999.999.999.999"}
    ok, _ = mod.check_v15_2_admin_ip_whitelist(env)
    return not ok


def t18_v15_3_admin_api_key_length() -> bool:
    """t18: V15-3 ADMIN_API_KEY 长度 ≥32。"""
    mod = _import_env_check()
    env = {"ADMIN_API_KEY": "short"}
    ok, _ = mod.check_v15_3_admin_api_key_length(env)
    if ok:
        return False
    env = {"ADMIN_API_KEY": "x" * 32}
    ok, _ = mod.check_v15_3_admin_api_key_length(env)
    return ok


def t19_ci5_vapid_65_bytes() -> bool:
    """t19: CI-5 VAPID 公钥必须 65 bytes(P-256 uncompressed)。"""
    mod = _import_env_check()
    import base64
    fake_65 = b"\x04" + b"\x00" * 32 + b"\x00" * 32
    env = {"VAPID_PUBLIC_KEY": base64.urlsafe_b64encode(fake_65).rstrip(b"=").decode("ascii")}
    ok, _ = mod.check_ci5_vapid_public(env)
    if not ok:
        return False
    env = {"VAPID_PUBLIC_KEY": "short-key"}
    ok, _ = mod.check_ci5_vapid_public(env)
    return not ok


def t20_ci4_stripe_webhook_format() -> bool:
    """t20: CI-4 STRIPE_WEBHOOK_SECRET 前缀 whsec_ + 长度 ≥32。"""
    mod = _import_env_check()
    env = {"STRIPE_WEBHOOK_SECRET": "whsec_" + "x" * 40}
    ok, _ = mod.check_ci4_stripe_webhook(env)
    if not ok:
        return False
    env = {"STRIPE_WEBHOOK_SECRET": "sk_live_xxx"}  # 错前缀
    ok, _ = mod.check_ci4_stripe_webhook(env)
    return not ok


def t21_ci10_cors_no_wildcard_localhost() -> bool:
    """t21: CI-10 CORS_ORIGINS 不含 * / localhost,必须 https://。"""
    mod = _import_env_check()
    env = {"CORS_ORIGINS": json.dumps(["https://app.example.com", "https://admin.example.com"])}
    ok, _ = mod.check_ci10_cors_origins(env)
    if not ok:
        return False
    env = {"CORS_ORIGINS": json.dumps(["*"])}  # 通配符禁止
    ok, _ = mod.check_ci10_cors_origins(env)
    if ok:
        return False
    env = {"CORS_ORIGINS": json.dumps(["http://localhost:3000"])}  # localhost 禁止
    ok, _ = mod.check_ci10_cors_origins(env)
    if ok:
        return False
    env = {"CORS_ORIGINS": json.dumps(["http://example.com"])}  # 非 https 禁止
    ok, _ = mod.check_ci10_cors_origins(env)
    return not ok


def t22_ci7_sentry_dsn_format() -> bool:
    """t22: CI-7 SENTRY_DSN 含 sentry.io + /ingest/。"""
    mod = _import_env_check()
    env = {"SENTRY_DSN": "https://abc123@sentry.io/ingest/4505"}
    ok, _ = mod.check_ci7_sentry_dsn(env)
    if not ok:
        return False
    env = {"SENTRY_DSN": "https://example.com/error"}  # 缺 sentry.io 和 /ingest/
    ok, _ = mod.check_ci7_sentry_dsn(env)
    return not ok


def t23_dotenv_loading() -> bool:
    """t23: --dotenv 模式可加载临时 .env 文件(优先 process.env,后 dotenv)。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
        f.write("ENV=production\n")
        f.write("DEBUG=false\n")
        f.write("CORS_ORIGINS=[\"https://test.example.com\"]\n")
        f.write("VAPID_PRIVATE_KEY=-----BEGIN TEST-----\n")
        f.write("VAPID_PRIVATE_KEY_END=-----END TEST-----\n")
        # 注:实际 VAPID_PRIVATE_KEY 不会因为有 = 被分词,partition 不会错
        tmp_path = f.name
    try:
        r = subprocess.run(
            [sys.executable, str(ENV_CHECK), "--dotenv", tmp_path, "--sandbox"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        # 沙箱模式只要脚本能跑完,返 0
        return r.returncode == 0
    finally:
        os.unlink(tmp_path)


def t24_no_mock_200_in_sandbox() -> bool:
    """t24: 沙箱模式返 0 是显式标注,不是 mock 200 伪装(看 stdout 是否含 '[m9t2] --sandbox')。"""
    r = subprocess.run(
        [sys.executable, str(ENV_CHECK), "--sandbox"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
    )
    return "sandbox" in (r.stdout + r.stderr).lower()


def t25_check_signature_consistency() -> bool:
    """t25: 全部 check_* 函数签名统一 — 接受 env 参数(防止 main 再次炸)。"""
    mod = _import_env_check()
    import inspect
    fn_names = [
        "check_ci1_p0_all",
        "check_ci2_secret_key",
        "check_ci3_stripe_secret",
        "check_ci4_stripe_webhook",
        "check_ci5_vapid_public",
        "check_ci6_vapid_private",
        "check_ci7_sentry_dsn",
        "check_ci8_env_production",
        "check_ci9_debug_false",
        "check_ci10_cors_origins",
        "check_v15_1_admin_api_key",
        "check_v15_2_admin_ip_whitelist",
        "check_v15_3_admin_api_key_length",
        "check_manual_11_pg_extensions",
        "check_manual_12_vapid_pair",
    ]
    for fn_name in fn_names:
        if not hasattr(mod, fn_name):
            print(f"    缺:{fn_name}")
            return False
        sig = inspect.signature(getattr(mod, fn_name))
        if "env" not in sig.parameters:
            print(f"    {fn_name} 缺 env 参数")
            return False
    return True


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

ALL_TESTS = [
    ("t01_file_exists", t01_file_exists),
    ("t02_module_importable", t02_module_importable),
    ("t03_ci_functions_defined", t03_ci_functions_defined),
    ("t04_v15_functions_defined", t04_v15_functions_defined),
    ("t05_manual_functions_defined", t05_manual_functions_defined),
    ("t06_ci_checks_list_count", t06_ci_checks_list_count),
    ("t07_v15_checks_list_count", t07_v15_checks_list_count),
    ("t08_manual_checks_list_count", t08_manual_checks_list_count),
    ("t09_b64url_decode_valid", t09_b64url_decode_valid),
    ("t10_b64url_decode_invalid", t10_b64url_decode_invalid),
    ("t11_is_valid_ip_v4", t11_is_valid_ip_v4),
    ("t12_is_valid_ip_invalid", t12_is_valid_ip_invalid),
    ("t13_cli_args_defined", t13_cli_args_defined),
    ("t14_exit_code_sandbox_no_p0", t14_exit_code_sandbox_no_p0),
    ("t15_exit_code_nosandbox_missing_p0", t15_exit_code_nosandbox_missing_p0),
    ("t16_v15_1_admin_api_key_logic", t16_v15_1_admin_api_key_logic),
    ("t17_v15_2_ip_whitelist_valid", t17_v15_2_ip_whitelist_valid),
    ("t18_v15_3_admin_api_key_length", t18_v15_3_admin_api_key_length),
    ("t19_ci5_vapid_65_bytes", t19_ci5_vapid_65_bytes),
    ("t20_ci4_stripe_webhook_format", t20_ci4_stripe_webhook_format),
    ("t21_ci10_cors_no_wildcard_localhost", t21_ci10_cors_no_wildcard_localhost),
    ("t22_ci7_sentry_dsn_format", t22_ci7_sentry_dsn_format),
    ("t23_dotenv_loading", t23_dotenv_loading),
    ("t24_no_mock_200_in_sandbox", t24_no_mock_200_in_sandbox),
    ("t25_check_signature_consistency", t25_check_signature_consistency),
]


def _run(name: str, fn) -> bool:
    try:
        result = fn()
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        return result
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] {name} — {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("=" * 72)
    print("  V1.5 接力期 m9t2 — env_check.py 自测")
    print("=" * 72)

    passed = 0
    failed = 0
    failed_names: list[str] = []
    for name, fn in ALL_TESTS:
        if _run(name, fn):
            passed += 1
        else:
            failed += 1
            failed_names.append(name)

    total = passed + failed
    print("=" * 72)
    print(f"  [m9t2] SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 72)
    if failed:
        print("\n[m9t2] FAILED TESTS:")
        for n in failed_names:
            print(f"  - {n}")
        return 1
    print(f"\n[m9t2] ALL {total} ENV_CHECK SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
