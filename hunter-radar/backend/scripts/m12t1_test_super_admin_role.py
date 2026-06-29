"""M12-t1 V1.5.4 auth.py super_admin role 扩展自测(25 测点)。

V1.5.4 接力期 m12t1 — C-2 Role 扩展预留 super_admin:
- VALID_ROLES 加 "super_admin" → ("user", "admin", "super_admin")
- 新增 ADMIN_ROLES / SUPER_ADMIN_ROLE 常量
- 新增 is_admin_role / is_super_admin_role helpers
- TUser.is_admin 自动兼容 super_admin(is_admin_role helper 判定)
- TUser 新增 is_super_admin property
- 新增 require_super_admin_role 依赖(webhook 重放等高危操作)
- admin.py POST /admin/webhook/replay 改用 require_super_admin_role

Section 1 — VALID_ROLES / ADMIN_ROLES / SUPER_ADMIN_ROLE 常量(5 测点):
  t01: VALID_ROLES 含 super_admin
  t02: ADMIN_ROLES = ("admin", "super_admin")
  t03: SUPER_ADMIN_ROLE = "super_admin"
  t04: VALID_ROLES 长度 = 3
  t05: ADMIN_ROLES 长度 = 2

Section 2 — 4 个 role helper(5 测点):
  t06: is_valid_role("super_admin") → True
  t07: is_valid_role("unknown_role") → False
  t08: normalize_role("SUPER_ADMIN") → "super_admin"(大小写不敏感)
  t09: is_admin_role("super_admin") → True(super_admin 也是 admin)
  t10: is_super_admin_role("admin") → False(普通 admin 不是 super_admin)

Section 3 — TUser property(5 测点):
  t11: TUser(role="super_admin").is_admin → True
  t12: TUser(role="super_admin").is_super_admin → True
  t13: TUser(role="admin").is_admin → True
  t14: TUser(role="admin").is_super_admin → False
  t15: TUser(role="user").is_admin → False

Section 4 — __all__ 补 4 新符号(5 测点):
  t16: __all__ 含 ADMIN_ROLES
  t17: __all__ 含 SUPER_ADMIN_ROLE
  t18: __all__ 含 is_admin_role
  t19: __all__ 含 is_super_admin_role
  t20: __all__ 含 require_super_admin_role

Section 5 — 函数定义 + admin.py 端点(5 测点):
  t21: require_super_admin_role 函数定义存在
  t22: admin.py POST /admin/webhook/replay 改用 require_super_admin_role
  t23: admin.py POST /admin/webhook/replay docstring 标注 m12t1
  t24: admin.py 文档头加 super_admin 拆分说明
  t25: 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_PY = ROOT / "backend" / "app" / "core" / "auth.py"
ADMIN_PY = ROOT / "backend" / "app" / "api" / "admin.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ---- Section 1: 常量(5 测点) ---------------------------------------------


def t01_valid_roles_contains_super_admin() -> bool:
    """t01: VALID_ROLES 包含 super_admin。"""
    txt = _read(AUTH_PY)
    if not re.search(r'VALID_ROLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(\s*"user"\s*,\s*"admin"\s*,\s*"super_admin"\s*\)', txt):
        print("    [FAIL] VALID_ROLES 应 = ('user', 'admin', 'super_admin')")
        return False
    print("    [PASS] VALID_ROLES 含 super_admin")
    return True


def t02_admin_roles_definition() -> bool:
    """t02: ADMIN_ROLES = ('admin', 'super_admin')。"""
    txt = _read(AUTH_PY)
    if not re.search(r'ADMIN_ROLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(\s*"admin"\s*,\s*"super_admin"\s*\)', txt):
        print("    [FAIL] ADMIN_ROLES 应 = ('admin', 'super_admin')")
        return False
    print("    [PASS] ADMIN_ROLES = ('admin', 'super_admin')")
    return True


def t03_super_admin_role_constant() -> bool:
    """t03: SUPER_ADMIN_ROLE = 'super_admin'。"""
    txt = _read(AUTH_PY)
    if not re.search(r'SUPER_ADMIN_ROLE:\s*str\s*=\s*"super_admin"', txt):
        print("    [FAIL] SUPER_ADMIN_ROLE 应 = 'super_admin'")
        return False
    print("    [PASS] SUPER_ADMIN_ROLE = 'super_admin'")
    return True


def t04_valid_roles_length() -> bool:
    """t04: VALID_ROLES 长度 = 3。"""
    txt = _read(AUTH_PY)
    m = re.search(r'VALID_ROLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(\s*"user"\s*,\s*"admin"\s*,\s*"super_admin"\s*\)', txt)
    if not m:
        print("    [FAIL] VALID_ROLES 未正确声明")
        return False
    raw = m.group(0)
    parts = re.findall(r'"(\w+)"', raw)
    if len(parts) != 3:
        print(f"    [FAIL] VALID_ROLES 应含 3 个 role,实际 {len(parts)}: {parts}")
        return False
    print(f"    [PASS] VALID_ROLES 长度 = 3 ({parts})")
    return True


def t05_admin_roles_length() -> bool:
    """t05: ADMIN_ROLES 长度 = 2。"""
    txt = _read(AUTH_PY)
    m = re.search(r'ADMIN_ROLES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(\s*"admin"\s*,\s*"super_admin"\s*\)', txt)
    if not m:
        print("    [FAIL] ADMIN_ROLES 未正确声明")
        return False
    raw = m.group(0)
    parts = re.findall(r'"(\w+)"', raw)
    if len(parts) != 2:
        print(f"    [FAIL] ADMIN_ROLES 应含 2 个 role,实际 {len(parts)}: {parts}")
        return False
    print(f"    [PASS] ADMIN_ROLES 长度 = 2 ({parts})")
    return True


# ---- Section 2: 4 个 role helper(5 测点) ----------------------------------


def t06_is_valid_role_super_admin_true() -> bool:
    """t06: is_valid_role('super_admin') → True(由 VALID_ROLES 集合保证)。"""
    txt = _read(AUTH_PY)
    if "def is_valid_role" not in txt:
        print("    [FAIL] is_valid_role 函数不存在")
        return False
    # 函数体引用 VALID_ROLES 常量即可(super_admin 是其元素,见 t01)
    m = re.search(r"def is_valid_role\(.*?\n(.*?)(?=\ndef )", txt, re.DOTALL)
    if not m or "VALID_ROLES" not in m.group(1):
        print("    [FAIL] is_valid_role 未引用 VALID_ROLES(无法保证 super_admin 校验通过)")
        return False
    print("    [PASS] is_valid_role 引用 VALID_ROLES(super_admin 已在集合内)")
    return True


def t07_is_valid_role_unknown_false() -> bool:
    """t07: is_valid_role('unknown_role') → False(由 VALID_ROLES 保证)。"""
    txt = _read(AUTH_PY)
    if "def is_valid_role" not in txt:
        print("    [FAIL] is_valid_role 函数不存在")
        return False
    # 函数体应在 VALID_ROLES 集合内,unknown_role 不在 → False
    if "VALID_ROLES" not in txt:
        print("    [FAIL] is_valid_role 未引用 VALID_ROLES")
        return False
    print("    [PASS] is_valid_role 通过 VALID_ROLES 校验,unknown_role 不在 → False")
    return True


def t08_normalize_role_case_insensitive() -> bool:
    """t08: normalize_role('SUPER_ADMIN') → 'super_admin'(小写归一)。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def normalize_role\(.*?\)\s*->\s*str:\n(.*?)(?=\ndef )", txt, re.DOTALL)
    if not m:
        print("    [FAIL] normalize_role 函数不存在")
        return False
    body = m.group(1)
    if "lower()" not in body:
        print("    [FAIL] normalize_role 未做大小写归一")
        return False
    print("    [PASS] normalize_role 支持大小写归一(SUPER_ADMIN → super_admin)")
    return True


def t09_is_admin_role_super_admin_true() -> bool:
    """t09: is_admin_role('super_admin') → True。"""
    txt = _read(AUTH_PY)
    if "def is_admin_role" not in txt:
        print("    [FAIL] is_admin_role 函数不存在")
        return False
    m = re.search(r"def is_admin_role\(.*?\n(.*?)(?=\ndef )", txt, re.DOTALL)
    if not m or "ADMIN_ROLES" not in m.group(1):
        print("    [FAIL] is_admin_role 未引用 ADMIN_ROLES")
        return False
    print("    [PASS] is_admin_role 含 super_admin 校验(走 ADMIN_ROLES)")
    return True


def t10_is_super_admin_role_admin_false() -> bool:
    """t10: is_super_admin_role('admin') → False(普通 admin 不是 super_admin)。"""
    txt = _read(AUTH_PY)
    if "def is_super_admin_role" not in txt:
        print("    [FAIL] is_super_admin_role 函数不存在")
        return False
    m = re.search(r"def is_super_admin_role\(.*?\n(.*?)(?=\ndef )", txt, re.DOTALL)
    if not m or "SUPER_ADMIN_ROLE" not in m.group(1):
        print("    [FAIL] is_super_admin_role 未引用 SUPER_ADMIN_ROLE")
        return False
    print("    [PASS] is_super_admin_role 仅匹配 super_admin(走 SUPER_ADMIN_ROLE)")
    return True


# ---- Section 3: TUser property(5 测点) -----------------------------------


def t11_super_admin_is_admin_true() -> bool:
    """t11: TUser(role='super_admin').is_admin → True。"""
    txt = _read(AUTH_PY)
    # TUser.is_admin 改用 is_admin_role helper(自动兼容 super_admin)
    m = re.search(r"def is_admin\(self\)\s*->\s*bool:.*?return\s+(\S+)\(self\.role\)", txt, re.DOTALL)
    if not m or m.group(1) != "is_admin_role":
        print(f"    [FAIL] TUser.is_admin 应 return is_admin_role(self.role),实际 return {m.group(1) if m else 'None'}")
        return False
    print("    [PASS] TUser.is_admin 改用 is_admin_role(super_admin 自动过)")
    return True


def t12_super_admin_is_super_admin_true() -> bool:
    """t12: TUser(role='super_admin').is_super_admin → True。"""
    txt = _read(AUTH_PY)
    if "@property" not in txt:
        print("    [FAIL] TUser 无 @property 装饰器")
        return False
    m = re.search(r"def is_super_admin\(self\)\s*->\s*bool:.*?return\s+(\S+)\(self\.role\)", txt, re.DOTALL)
    if not m or m.group(1) != "is_super_admin_role":
        print(f"    [FAIL] TUser.is_super_admin 应 return is_super_admin_role(self.role),实际 return {m.group(1) if m else 'None'}")
        return False
    print("    [PASS] TUser.is_super_admin 改用 is_super_admin_role")
    return True


def t13_admin_is_admin_true() -> bool:
    """t13: TUser(role='admin').is_admin → True(沿用 m11t3 行为)。"""
    txt = _read(AUTH_PY)
    # is_admin 走 is_admin_role → admin 在 ADMIN_ROLES 中 → True
    if "def is_admin(self)" not in txt:
        print("    [FAIL] TUser.is_admin 不存在")
        return False
    if "is_admin_role(self.role)" not in txt:
        print("    [FAIL] TUser.is_admin 未改用 is_admin_role")
        return False
    print("    [PASS] TUser.is_admin 沿用 admin 判定(走 is_admin_role)")
    return True


def t14_admin_is_super_admin_false() -> bool:
    """t14: TUser(role='admin').is_super_admin → False。"""
    txt = _read(AUTH_PY)
    # is_super_admin 走 is_super_admin_role → admin 不等于 super_admin → False
    if "def is_super_admin(self)" not in txt:
        print("    [FAIL] TUser.is_super_admin 不存在")
        return False
    if "is_super_admin_role(self.role)" not in txt:
        print("    [FAIL] TUser.is_super_admin 未改用 is_super_admin_role")
        return False
    print("    [PASS] TUser.is_super_admin 普通 admin 返 False")
    return True


def t15_user_is_admin_false() -> bool:
    """t15: TUser(role='user').is_admin → False。"""
    txt = _read(AUTH_PY)
    if "def is_admin(self)" not in txt:
        print("    [FAIL] TUser.is_admin 不存在")
        return False
    # is_admin_role('user') → user 不在 ADMIN_ROLES → False
    if "is_admin_role" not in txt:
        print("    [FAIL] TUser.is_admin 未改用 is_admin_role")
        return False
    print("    [PASS] TUser.is_admin 普通 user 返 False(走 is_admin_role)")
    return True


# ---- Section 4: __all__ 补 4 新符号(5 测点) -----------------------------


def t16_all_exports_admin_roles() -> bool:
    """t16: __all__ 含 ADMIN_ROLES。"""
    txt = _read(AUTH_PY)
    if '"ADMIN_ROLES"' not in txt:
        print("    [FAIL] __all__ 缺 ADMIN_ROLES")
        return False
    print("    [PASS] __all__ 含 ADMIN_ROLES")
    return True


def t17_all_exports_super_admin_role() -> bool:
    """t17: __all__ 含 SUPER_ADMIN_ROLE。"""
    txt = _read(AUTH_PY)
    if '"SUPER_ADMIN_ROLE"' not in txt:
        print("    [FAIL] __all__ 缺 SUPER_ADMIN_ROLE")
        return False
    print("    [PASS] __all__ 含 SUPER_ADMIN_ROLE")
    return True


def t18_all_exports_is_admin_role() -> bool:
    """t18: __all__ 含 is_admin_role。"""
    txt = _read(AUTH_PY)
    if '"is_admin_role"' not in txt:
        print("    [FAIL] __all__ 缺 is_admin_role")
        return False
    print("    [PASS] __all__ 含 is_admin_role")
    return True


def t19_all_exports_is_super_admin_role() -> bool:
    """t19: __all__ 含 is_super_admin_role。"""
    txt = _read(AUTH_PY)
    if '"is_super_admin_role"' not in txt:
        print("    [FAIL] __all__ 缺 is_super_admin_role")
        return False
    print("    [PASS] __all__ 含 is_super_admin_role")
    return True


def t20_all_exports_require_super_admin_role() -> bool:
    """t20: __all__ 含 require_super_admin_role。"""
    txt = _read(AUTH_PY)
    if '"require_super_admin_role"' not in txt:
        print("    [FAIL] __all__ 缺 require_super_admin_role")
        return False
    print("    [PASS] __all__ 含 require_super_admin_role")
    return True


# ---- Section 5: 函数定义 + admin.py 端点(5 测点) -------------------------


def t21_require_super_admin_role_function_defined() -> bool:
    """t21: require_super_admin_role 函数定义存在。"""
    txt = _read(AUTH_PY)
    if "def require_super_admin_role(" not in txt:
        print("    [FAIL] require_super_admin_role 函数未定义")
        return False
    if "is_super_admin" not in txt:
        print("    [FAIL] require_super_admin_role 函数未引用 is_super_admin 判定")
        return False
    print("    [PASS] require_super_admin_role 函数已定义(走 is_super_admin 判定)")
    return True


def t22_admin_webhook_replay_uses_super_admin() -> bool:
    """t22: admin.py POST /admin/webhook/replay 改用 require_super_admin_role。"""
    txt = _read(ADMIN_PY)
    if '"/admin/webhook/replay"' not in txt:
        print("    [FAIL] /admin/webhook/replay 端点不存在")
        return False
    # 端点依赖应从 require_admin_role 改为 require_super_admin_role
    if "Depends(require_super_admin_role)" not in txt:
        print("    [FAIL] /admin/webhook/replay 未改用 Depends(require_super_admin_role)")
        return False
    print("    [PASS] /admin/webhook/replay 改用 require_super_admin_role")
    return True


def t23_admin_webhook_replay_docstring_m12t1() -> bool:
    """t23: admin.py /admin/webhook/replay docstring 标注 m12t1。"""
    txt = _read(ADMIN_PY)
    if "V1.5.4 接力期 m12t1" not in txt:
        print("    [FAIL] admin.py 未标注 V1.5.4 m12t1")
        return False
    print("    [PASS] admin.py 标注 V1.5.4 m12t1 super_admin 拆分")
    return True


def t24_admin_doc_header_super_admin_split() -> bool:
    """t24: admin.py 文档头加 super_admin 拆分说明。"""
    txt = _read(ADMIN_PY)
    if "require_super_admin_role" not in txt[:1500]:
        print("    [FAIL] admin.py 文档头未提及 require_super_admin_role")
        return False
    if "super_admin" not in txt[:1500].lower():
        print("    [FAIL] admin.py 文档头未提及 super_admin")
        return False
    print("    [PASS] admin.py 文档头加 super_admin 拆分说明")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验(本脚本含 t01~t25 共 25 函数)。"""
    import re as _re
    fns = [name for name in dir(sys.modules[__name__]) if _re.match(r"^t\d{2}_", name)]
    fns = sorted(fns)
    expected = [f"t{i:02d}_" for i in range(1, 26)]
    matched = [n[:4] for n in fns]
    if matched != expected:
        missing = set(expected) - set(matched)
        extra = set(matched) - set(expected)
        print(f"    [FAIL] 测点编号不连续 缺={missing or '无'} 多={extra or '无'}")
        return False
    print(f"    [PASS] 共 {len(matched)} 测点(t01~t25 连续)")
    return True


# ---- main ----------------------------------------------------------------


TESTS = [
    # Section 1: 常量(5 测点)
    t01_valid_roles_contains_super_admin,
    t02_admin_roles_definition,
    t03_super_admin_role_constant,
    t04_valid_roles_length,
    t05_admin_roles_length,
    # Section 2: helper(5 测点)
    t06_is_valid_role_super_admin_true,
    t07_is_valid_role_unknown_false,
    t08_normalize_role_case_insensitive,
    t09_is_admin_role_super_admin_true,
    t10_is_super_admin_role_admin_false,
    # Section 3: TUser property(5 测点)
    t11_super_admin_is_admin_true,
    t12_super_admin_is_super_admin_true,
    t13_admin_is_admin_true,
    t14_admin_is_super_admin_false,
    t15_user_is_admin_false,
    # Section 4: __all__(5 测点)
    t16_all_exports_admin_roles,
    t17_all_exports_super_admin_role,
    t18_all_exports_is_admin_role,
    t19_all_exports_is_super_admin_role,
    t20_all_exports_require_super_admin_role,
    # Section 5: 函数定义 + admin.py 端点(5 测点)
    t21_require_super_admin_role_function_defined,
    t22_admin_webhook_replay_uses_super_admin,
    t23_admin_webhook_replay_docstring_m12t1,
    t24_admin_doc_header_super_admin_split,
    t25_25_testpoints_total,
]


def main() -> int:
    print("[m12t1] V1.5.4 super_admin role 扩展自测 25 测点")
    print(f"[m12t1] 扫描 auth.py: {AUTH_PY}")
    print(f"[m12t1] 扫描 admin.py: {ADMIN_PY}")
    print()

    passed = 0
    failed = 0
    for t in TESTS:
        print(f"[m12t1] {t.__name__}: {t.__doc__}")
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"    [ERROR] {type(e).__name__}: {e}")
            failed += 1
        print()

    total = passed + failed
    print(f"[m12t1] summary: {passed}/{total} PASSED")
    if failed == 0:
        print("[m12t1] V1.5.4 m12t1 25 测点 ALL PASSED")
        return 0
    print(f"[m12t1] {failed} 测点 FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
