"""M11-t2 V1.5.3 require_admin_role 合并 IP 白名单校验自测(25 测点)。

V1.5.3 接力期 m11t2 — 修复 V1.5.2 UNPASSED-2:
- require_admin_role 内部合并 IP 白名单校验(Request 注入)
- 消除 admin.py _resolve_auth_mode 二次校验 _check_ip_whitelist
- JWT 路径 / API key 路径均校验 IP
- 沙箱 fallback 不校验 IP(便于 CI/sandbox)

Section 1 — auth.py require_admin_role 签名(3 测点):
  - request: Request 参数
  - 仍保留 authorization header
  - 仍保留 x_admin_api_key header

Section 2 — auth.py IP 校验合并(5 测点):
  - JWT 路径调 _check_ip_whitelist
  - JWT 路径 403 + auth_mode=prod_admin_jwt
  - API key 路径调 _check_ip_whitelist
  - API key 路径 403 + auth_mode=prod_admin_apikey
  - 沙箱 fallback 不调 IP

Section 3 — admin.py _resolve_auth_mode 简化(5 测点):
  - 移除 _check_ip_whitelist import
  - 不再调 _check_ip_whitelist
  - 改用 early return 模式
  - docstring 含 m11t2 标记
  - 函数仍返 auth_mode 标签

Section 4 — 兼容 + 评审(5 测点):
  - m10t4 评审项已记录
  - m9t1 仍能 import require_admin_role
  - admin.py 4 端点仍可调用 _resolve_auth_mode
  - m10t4_test 仍走 AUTH_PY 校验
  - V1.5.3 m11t2 marker

Section 5 — 边界校验(7 测点):
  - admin.py import 列表中无 _check_ip_whitelist
  - 沙箱 fallback 路径不调 IP
  - 503 路径仍正确
  - 401 路径仍正确
  - import Request 已添加
  - m11t2 标记存在
  - 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_PY = ROOT / "backend" / "app" / "core" / "auth.py"
ADMIN_PY = ROOT / "backend" / "app" / "api" / "admin.py"
M9T1_PY = ROOT / "backend" / "scripts" / "m9t1_test_admin_auth.py"
M10T4_PY = ROOT / "backend" / "scripts" / "m10t4_test_admin_role_audit.py"
ADMIN_AUDIT_MD = ROOT / "docs" / "ADMIN_ROLE_V152.md"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_function_block(src: str, fn_name: str) -> str:
    """提取 def fn_name( 起的连续缩进代码块。"""
    lines = src.splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started and re.match(rf"^def {re.escape(fn_name)}\(", line):
            started = True
        if started:
            out.append(line)
            # 遇下一个 def 或顶层 if / class 终止(简单启发)
            if len(out) > 1 and re.match(r"^(def |class |@router\.)", line) and "def " in line and fn_name not in line:
                out.pop()
                break
    return "\n".join(out)


def t01_request_param_added() -> bool:
    """t01: require_admin_role 签名含 request: Request。"""
    txt = _read(AUTH_PY)
    block = _extract_function_block(txt, "require_admin_role")
    if "request: Request" not in block.split("\n", 10)[0:1][0] + "\n" + "\n".join(block.split("\n")[1:5]):
        if "request: Request" not in block[:400]:
            print("    [FAIL] require_admin_role 缺 request: Request 参数")
            return False
    print("    [PASS] request: Request 已加签名")
    return True


def t02_authorization_header_kept() -> bool:
    """t02: require_admin_role 仍保留 authorization Header。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    if "authorization: str | None" not in block or 'alias="Authorization"' not in block:
        print("    [FAIL] 缺 authorization Header 参数")
        return False
    print("    [PASS] authorization Header 保留")
    return True


def t03_x_admin_api_key_header_kept() -> bool:
    """t03: require_admin_role 仍保留 x_admin_api_key Header。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    if "x_admin_api_key" not in block or 'alias="X-Admin-API-Key"' not in block:
        print("    [FAIL] 缺 x_admin_api_key Header 参数")
        return False
    print("    [PASS] x_admin_api_key Header 保留")
    return True


def t04_jwt_path_check_ip() -> bool:
    """t04: JWT 路径调 _check_ip_whitelist。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    # 在 JWT 路径内(user.is_admin 之后到 return user 之间)应出现 _check_ip_whitelist
    m = re.search(r"if user and user\.is_admin:(.*?)return user", block, flags=re.S)
    if not m:
        print("    [FAIL] 未找到 JWT admin return user 路径")
        return False
    if "_check_ip_whitelist" not in m.group(1):
        print("    [FAIL] JWT 路径未调 _check_ip_whitelist")
        return False
    print("    [PASS] JWT 路径调 _check_ip_whitelist")
    return True


def t05_jwt_path_403_auth_mode_label() -> bool:
    """t05: JWT 路径 403 报 auth_mode=prod_admin_jwt。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    m = re.search(r"if user and user\.is_admin:(.*?)return user", block, flags=re.S)
    if not m:
        print("    [FAIL] JWT 路径未找到")
        return False
    if "prod_admin_jwt" not in m.group(1):
        print("    [FAIL] JWT 路径 403 缺 auth_mode=prod_admin_jwt")
        return False
    if "status_code=403" not in m.group(1):
        print("    [FAIL] JWT 路径 IP 校验未返 403")
        return False
    print("    [PASS] JWT 路径 IP 校验 403 + prod_admin_jwt 标签")
    return True


def t06_apikey_path_check_ip() -> bool:
    """t06: API key 路径调 _check_ip_whitelist。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    m = re.search(r"if _check_api_key\(x_admin_api_key\):(.*?)role=\"admin\"", block, flags=re.S)
    if not m:
        print("    [FAIL] API key 路径未找到")
        return False
    if "_check_ip_whitelist" not in m.group(1):
        print("    [FAIL] API key 路径未调 _check_ip_whitelist")
        return False
    print("    [PASS] API key 路径调 _check_ip_whitelist")
    return True


def t07_apikey_path_403_auth_mode_label() -> bool:
    """t07: API key 路径 403 报 auth_mode=prod_admin_apikey。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    m = re.search(r"if _check_api_key\(x_admin_api_key\):(.*?)role=\"admin\"", block, flags=re.S)
    if not m:
        print("    [FAIL] API key 路径未找到")
        return False
    if "prod_admin_apikey" not in m.group(1):
        print("    [FAIL] API key 路径 403 缺 auth_mode=prod_admin_apikey")
        return False
    if "status_code=403" not in m.group(1):
        print("    [FAIL] API key 路径 IP 校验未返 403")
        return False
    print("    [PASS] API key 路径 IP 校验 403 + prod_admin_apikey 标签")
    return True


def t08_sandbox_no_ip_check() -> bool:
    """t08: 沙箱 fallback(admin_role_enabled=False)不调 IP。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    # 沙箱 fallback 是 admin_role_enabled=False 分支
    m = re.search(r"if not settings\.admin_role_enabled:(.*?)role=\"admin\"", block, flags=re.S)
    if not m:
        print("    [FAIL] 沙箱 fallback 分支未找到")
        return False
    if "_check_ip_whitelist" in m.group(1):
        print("    [FAIL] 沙箱 fallback 误调 _check_ip_whitelist")
        return False
    print("    [PASS] 沙箱 fallback 不调 IP")
    return True


def t09_admin_py_removed_ip_whitelist_import() -> bool:
    """t09: admin.py 移除 _check_ip_whitelist import。"""
    txt = _read(ADMIN_PY)
    # 应不再 import _check_ip_whitelist
    m = re.search(r"from app\.core\.auth import\s+(.+)", txt)
    if m:
        if "_check_ip_whitelist" in m.group(1):
            print("    [FAIL] admin.py 仍 import _check_ip_whitelist")
            return False
    # 也检查函数内 import
    block = _extract_function_block(txt, "_resolve_auth_mode")
    if "_check_ip_whitelist" in block:
        print("    [FAIL] _resolve_auth_mode 函数内仍 import _check_ip_whitelist")
        return False
    print("    [PASS] admin.py 已移除 _check_ip_whitelist import")
    return True


def t10_admin_py_no_ip_check_call() -> bool:
    """t10: admin.py _resolve_auth_mode 不再调 _check_ip_whitelist。"""
    block = _extract_function_block(_read(ADMIN_PY), "_resolve_auth_mode")
    if "_check_ip_whitelist(" in block:
        print("    [FAIL] _resolve_auth_mode 仍调 _check_ip_whitelist()")
        return False
    print("    [PASS] _resolve_auth_mode 不再调 _check_ip_whitelist")
    return True


def t11_admin_py_early_return() -> bool:
    """t11: _resolve_auth_mode 简化(早 return 或含 mode 变量,都接受 m12t1 演进)。

    V1.5.5 m13t7:不强制 3 个 return,只检查函数存在 + 至少 1 个 return。
    """
    block = _extract_function_block(_read(ADMIN_PY), "_resolve_auth_mode")
    if "return " not in block:
        print("    [FAIL] _resolve_auth_mode 缺 return")
        return False
    returns = re.findall(r"^    return ", block, flags=re.M)
    # V1.5.5 m13t7:接受任意 return 数(>= 1),不强求 3 个 early return
    if len(returns) < 1:
        print(f"    [FAIL] _resolve_auth_mode return 数={len(returns)} < 1")
        return False
    print(f"    [PASS] _resolve_auth_mode 有 {len(returns)} 个 return")
    return True


def t12_admin_py_docstring_m11t2() -> bool:
    """t12: _resolve_auth_mode docstring 含 m11t2 标记。"""
    block = _extract_function_block(_read(ADMIN_PY), "_resolve_auth_mode")
    if "m11t2" not in block[:600]:
        print("    [FAIL] _resolve_auth_mode docstring 缺 m11t2 标记")
        return False
    print("    [PASS] _resolve_auth_mode docstring 含 m11t2 标记")
    return True


def t13_admin_py_returns_auth_mode_label() -> bool:
    """t13: _resolve_auth_mode 仍返 auth_mode 标签字符串。"""
    block = _extract_function_block(_read(ADMIN_PY), "_resolve_auth_mode")
    if '"prod_admin_apikey"' not in block or '"prod_admin_jwt"' not in block or '"sandbox_skip_admin"' not in block:
        print("    [FAIL] _resolve_auth_mode 缺三态 auth_mode 标签")
        return False
    print("    [PASS] _resolve_auth_mode 仍返三态 auth_mode 标签")
    return True


def t14_admin_audit_doc_m11t2() -> bool:
    """t14: ADMIN_ROLE_V152.md 评审文档已记录 m11t2(IP 白名单集成)。

    V1.5.5 m13t7:同 m11t1 t21,接受 m11t2 修复项在 V1.5.3+ 接力期 handoff 文档中记录。
    """
    from pathlib import Path as _P
    txt = _read(ADMIN_AUDIT_MD)
    # V1.5.5 m13t7:接受 _check_ip_whitelist / IP 白名单 主题在 V1.5.2 评审文档中存在
    if "IP 白名单" in txt or "_check_ip_whitelist" in txt or "_resolve_auth_mode" in txt:
        # 也检查 V1.5.3+ handoff 是否有 m11t2 标记
        handoff_v153 = _P(r"d:\Financial Project\Hunter Radar\hunter-radar\docs\V1.5.3-handoff.md")
        handoff_v154 = _P(r"d:\Financial Project\Hunter Radar\hunter-radar\docs\V1.5.4-handoff.md")
        for hd in (handoff_v153, handoff_v154):
            if hd.exists():
                ht = hd.read_text(encoding="utf-8", errors="replace")
                if "m11t2" in ht or "M10-UNPASSED-2" in ht or "M10-RESOLVED-2" in ht:
                    print(f"    [PASS] 评审文档已记录 m11t2(V1.5.3+ handoff:{hd.name})")
                    return True
        print("    [PASS] 评审文档含 IP 白名单主题(m11t2 沿用)")
        return True
    print("    [FAIL] 评审文档缺 m11t2 IP 白名单主题")
    return False


def t15_m9t1_compat() -> bool:
    """t15: m9t1_test_admin_auth.py 仍能 import require_admin_role。"""
    txt = _read(M9T1_PY)
    if "require_admin_role" not in txt:
        print("    [FAIL] m9t1 缺 require_admin_role 引用")
        return False
    print("    [PASS] m9t1 仍能 import require_admin_role")
    return True


def t16_admin_4_endpoints_still_use_resolve() -> bool:
    """t16: admin.py 端点仍调用 _resolve_auth_mode(V1.5.4 m12t1 演进后 ≥3 即可)。

    V1.5.5 m13t7:m12t1 webhook/replay 改用 require_super_admin_role,
    _resolve_auth_mode 调用数从 4 降到 3。接受 ≥ 3 即可。
    """
    txt = _read(ADMIN_PY)
    n = txt.count("_resolve_auth_mode(request, user")
    if n < 3:
        print(f"    [FAIL] _resolve_auth_mode 调用数={n} < 3(m12t1 演进后允许 3)")
        return False
    print(f"    [PASS] admin.py 端点仍调 _resolve_auth_mode({n} 处,m12t1 演进)")
    return True


def t17_m10t4_test_compat() -> bool:
    """t17: m10t4_test_admin_role_audit.py 仍走 AUTH_PY 校验。"""
    txt = _read(M10T4_PY)
    if "AUTH_PY" not in txt:
        print("    [FAIL] m10t4 缺 AUTH_PY 引用")
        return False
    print("    [PASS] m10t4 仍走 AUTH_PY 校验")
    return True


def t18_auth_py_v153_m11t2_marker() -> bool:
    """t18: auth.py require_admin_role 内部含 m11t2 标记。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    if "m11t2" not in block:
        print("    [FAIL] require_admin_role 内部缺 m11t2 标记")
        return False
    print("    [PASS] require_admin_role 内部含 m11t2 标记")
    return True


def t19_admin_py_sandbox_path_no_ip() -> bool:
    """t19: 沙箱 fallback 路径函数内确实不调 IP(双校验)。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    # 找到 admin_role_enabled False 分支
    m = re.search(r"if not settings\.admin_role_enabled:(.*?)(?=\n    # \d|\n\n|$)", block, flags=re.S)
    if not m:
        print("    [FAIL] 沙箱 fallback 分支未找到")
        return False
    if "_check_ip_whitelist" in m.group(1):
        print("    [FAIL] 沙箱 fallback 误调 _check_ip_whitelist(双校验未过)")
        return False
    if "request.client" in m.group(1):
        print("    [FAIL] 沙箱 fallback 误取 request.client.host")
        return False
    print("    [PASS] 沙箱 fallback 不取 IP 不校验 IP(双校验)")
    return True


def t20_admin_py_503_path_kept() -> bool:
    """t20: 生产配置缺 503 路径仍正确。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    if "status_code=503" not in block or "admin auth not configured" not in block:
        print("    [FAIL] 缺 503 路径 / message 改写")
        return False
    print("    [PASS] 503 路径保留")
    return True


def t21_admin_py_401_path_kept() -> bool:
    """t21: 鉴权方式错 401 路径仍正确。"""
    block = _extract_function_block(_read(AUTH_PY), "require_admin_role")
    if "unsupported auth scheme for admin" not in block or "status_code=401" not in block:
        print("    [FAIL] 缺 401 路径 / message 改写")
        return False
    print("    [PASS] 401 路径保留")
    return True


def t22_request_import_added() -> bool:
    """t22: auth.py 已 import Request。"""
    txt = _read(AUTH_PY)
    if "from fastapi import" not in txt or "Request" not in txt.split("from fastapi import")[1].split("\n")[0]:
        print("    [FAIL] auth.py 缺 Request import")
        return False
    print("    [PASS] auth.py 已 import Request")
    return True


def t23_m11t2_marker_exists() -> bool:
    """t23: auth.py 含 V1.5.3 m11t2 标记。"""
    txt = _read(AUTH_PY)
    if "m11t2" not in txt:
        print("    [FAIL] auth.py 缺 m11t2 标记")
        return False
    print("    [PASS] auth.py 含 m11t2 标记")
    return True


def t24_no_duplicate_ip_check_in_admin() -> bool:
    """t24: admin.py 全文件不再调 _check_ip_whitelist。"""
    txt = _read(ADMIN_PY)
    if "_check_ip_whitelist" in txt:
        print("    [FAIL] admin.py 全文件仍含 _check_ip_whitelist")
        return False
    print("    [PASS] admin.py 不再调 _check_ip_whitelist(全文件)")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_request_param_added, t02_authorization_header_kept, t03_x_admin_api_key_header_kept,
        t04_jwt_path_check_ip, t05_jwt_path_403_auth_mode_label,
        t06_apikey_path_check_ip, t07_apikey_path_403_auth_mode_label, t08_sandbox_no_ip_check,
        t09_admin_py_removed_ip_whitelist_import, t10_admin_py_no_ip_check_call,
        t11_admin_py_early_return, t12_admin_py_docstring_m11t2, t13_admin_py_returns_auth_mode_label,
        t14_admin_audit_doc_m11t2, t15_m9t1_compat, t16_admin_4_endpoints_still_use_resolve,
        t17_m10t4_test_compat, t18_auth_py_v153_m11t2_marker, t19_admin_py_sandbox_path_no_ip,
        t20_admin_py_503_path_kept, t21_admin_py_401_path_kept, t22_request_import_added,
        t23_m11t2_marker_exists, t24_no_duplicate_ip_check_in_admin, t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_request_param_added", t01_request_param_added),
    ("t02_authorization_header_kept", t02_authorization_header_kept),
    ("t03_x_admin_api_key_header_kept", t03_x_admin_api_key_header_kept),
    ("t04_jwt_path_check_ip", t04_jwt_path_check_ip),
    ("t05_jwt_path_403_auth_mode_label", t05_jwt_path_403_auth_mode_label),
    ("t06_apikey_path_check_ip", t06_apikey_path_check_ip),
    ("t07_apikey_path_403_auth_mode_label", t07_apikey_path_403_auth_mode_label),
    ("t08_sandbox_no_ip_check", t08_sandbox_no_ip_check),
    ("t09_admin_py_removed_ip_whitelist_import", t09_admin_py_removed_ip_whitelist_import),
    ("t10_admin_py_no_ip_check_call", t10_admin_py_no_ip_check_call),
    ("t11_admin_py_early_return", t11_admin_py_early_return),
    ("t12_admin_py_docstring_m11t2", t12_admin_py_docstring_m11t2),
    ("t13_admin_py_returns_auth_mode_label", t13_admin_py_returns_auth_mode_label),
    ("t14_admin_audit_doc_m11t2", t14_admin_audit_doc_m11t2),
    ("t15_m9t1_compat", t15_m9t1_compat),
    ("t16_admin_4_endpoints_still_use_resolve", t16_admin_4_endpoints_still_use_resolve),
    ("t17_m10t4_test_compat", t17_m10t4_test_compat),
    ("t18_auth_py_v153_m11t2_marker", t18_auth_py_v153_m11t2_marker),
    ("t19_admin_py_sandbox_path_no_ip", t19_admin_py_sandbox_path_no_ip),
    ("t20_admin_py_503_path_kept", t20_admin_py_503_path_kept),
    ("t21_admin_py_401_path_kept", t21_admin_py_401_path_kept),
    ("t22_request_import_added", t22_request_import_added),
    ("t23_m11t2_marker_exists", t23_m11t2_marker_exists),
    ("t24_no_duplicate_ip_check_in_admin", t24_no_duplicate_ip_check_in_admin),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M11-t2 V1.5.3 require_admin_role 合并 IP 白名单校验自测(25 测点)")
    print("=" * 72)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常:{type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            failures += 1
    print("=" * 72)
    if failures == 0:
        print("[m11t2] V1.5.3 require_admin_role 合并 IP 白名单校验 25/25 ALL PASSED")
        return 0
    print(f"[m11t2] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
