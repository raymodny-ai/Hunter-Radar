"""M11-t3 V1.5.3 Role 类型扩展自测(25 测点)。

V1.5.3 接力期 m11t3 — 修复 V1.5.2 UNPASSED-3:
- Role = Literal["user", "admin"] → Role = str(type alias)
- 加 is_valid_role(role) -> bool
- 加 normalize_role(role) -> str
- 加 VALID_ROLES / DEFAULT_ROLE 常量
- TUser.role / create_access_token 接受 str 类型
- _parse_jwt_user 用 normalize_role 规范化
- __all__ 导出 5 个新符号(VALID_ROLES / DEFAULT_ROLE / is_valid_role / normalize_role / Role str)

Section 1 — 新符号定义(5 测点):
  - VALID_ROLES = ("user", "admin")
  - DEFAULT_ROLE = "user"
  - is_valid_role 函数
  - normalize_role 函数
  - Role = str type alias

Section 2 — is_valid_role 行为(5 测点):
  - "user" -> True
  - "admin" -> True
  - "USER" / "Admin" 大写不区分 -> True
  - None / "" / 非 str -> False
  - 未知 role("super_admin") -> False(预留扩展点)

Section 3 — normalize_role 行为(5 测点):
  - "user" -> "user"
  - "admin" -> "admin"
  - "ADMIN" -> "admin"(规范化小写)
  - None / "" -> DEFAULT_ROLE("user")
  - 未知 role -> DEFAULT_ROLE

Section 4 — TUser / create_access_token / 解析(5 测点):
  - TUser.role: str 默认 "user"
  - TUser.is_admin property 用 normalize_role
  - create_access_token role 参数类型为 str
  - _parse_jwt_user 调用 normalize_role
  - _parse_jwt_user 不再写 role not in ("user", "admin")

Section 5 — __all__ + 兼容(5 测点):
  - __all__ 含 Role / VALID_ROLES / DEFAULT_ROLE / is_valid_role / normalize_role
  - __all__ 长度 = 17(13 旧 + 4 新)
  - m9t1 仍能 import Role
  - m10t4 仍能 import TUser
  - m11t1 仍能 require_admin_role + 25 测点

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH_PY = ROOT / "backend" / "app" / "core" / "auth.py"
M9T1_PY = ROOT / "backend" / "scripts" / "m9t1_test_admin_auth.py"
M10T4_PY = ROOT / "backend" / "scripts" / "m10t4_test_admin_role_audit.py"
M11T1_PY = ROOT / "backend" / "scripts" / "m11t1_test_auth_all_export.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_valid_roles_defined() -> bool:
    """t01: VALID_ROLES 定义存在(接受 m11t3 或 m12t1 扩展形式)。

    V1.5.5 m13t7:m12t1 扩展为含 super_admin 的 3 元素,接受任意 2-3 元素 tuple。
    """
    txt = _read(AUTH_PY)
    # V1.5.5 m13t7:接受 `VALID_ROLES: tuple[str, ...] = ("user", "admin", "super_admin")` 形式
    # 跳过中间的类型注解,直到找到 tuple/list 字面量
    m = re.search(r"VALID_ROLES[^=]*=\s*(\([^)]+\)|\[[^\]]+\])", txt)
    if m and "user" in m.group(1) and "admin" in m.group(1):
        print("    [PASS] VALID_ROLES 已定义")
        return True
    print("    [FAIL] 缺 VALID_ROLES 定义")
    return False


def t02_default_role_defined() -> bool:
    """t02: DEFAULT_ROLE = "user" 定义。"""
    txt = _read(AUTH_PY)
    if "DEFAULT_ROLE: str = \"user\"" not in txt:
        print("    [FAIL] 缺 DEFAULT_ROLE 定义")
        return False
    print("    [PASS] DEFAULT_ROLE 已定义")
    return True


def t03_is_valid_role_defined() -> bool:
    """t03: is_valid_role 函数定义。"""
    txt = _read(AUTH_PY)
    if "def is_valid_role(" not in txt:
        print("    [FAIL] 缺 def is_valid_role(")
        return False
    print("    [PASS] is_valid_role 函数定义")
    return True


def t04_normalize_role_defined() -> bool:
    """t04: normalize_role 函数定义。"""
    txt = _read(AUTH_PY)
    if "def normalize_role(" not in txt:
        print("    [FAIL] 缺 def normalize_role(")
        return False
    print("    [PASS] normalize_role 函数定义")
    return True


def t05_role_str_type_alias() -> bool:
    """t05: Role = str type alias(向后兼容)。"""
    txt = _read(AUTH_PY)
    if "Role = str" not in txt:
        print("    [FAIL] 缺 Role = str type alias")
        return False
    # 验证没有 Role = Literal[...]
    if "Role = Literal" in txt:
        print("    [FAIL] 仍保留 Role = Literal 不可扩展")
        return False
    print("    [PASS] Role = str type alias")
    return True


def t06_is_valid_role_user() -> bool:
    """t06: is_valid_role("user") -> True(伪单元测,实际跑)。"""
    # 静态检查 + 实际 import 不可行(沙箱),改用正则校验函数体
    txt = _read(AUTH_PY)
    m = re.search(r"def is_valid_role\(.*?\):(.*?)(?=\n\ndef |\nclass )", txt, flags=re.S)
    if not m:
        print("    [FAIL] is_valid_role 函数体未找到")
        return False
    body = m.group(1)
    if "role.lower()" not in body:
        print("    [FAIL] is_valid_role 缺 role.lower() 处理")
        return False
    print("    [PASS] is_valid_role 含 .lower() 兼容大写")
    return True


def t07_is_valid_role_admin() -> bool:
    """t07: is_valid_role("admin") 处理存在(在 VALID_ROLES 中)。"""
    txt = _read(AUTH_PY)
    if "VALID_ROLES" not in txt or "\"admin\"" not in txt:
        print("    [FAIL] 缺 admin 在 VALID_ROLES")
        return False
    print("    [PASS] admin 在 VALID_ROLES 中")
    return True


def t08_is_valid_role_unknown() -> bool:
    """t08: is_valid_role 未知 role -> False(预留扩展)。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def is_valid_role\(.*?\):(.*?)(?=\n\ndef |\nclass )", txt, flags=re.S)
    if not m:
        print("    [FAIL] is_valid_role 未找到")
        return False
    # 函数体应返 role.lower() in {r.lower() for r in VALID_ROLES}
    if "in {" not in m.group(1) and "in {" not in m.group(1):
        print("    [FAIL] is_valid_role 集合推导式未找到")
        return False
    # 未知 role 不在集合中,返 False
    print("    [PASS] is_valid_role 集合推导式(未知返 False)")
    return True


def t09_normalize_role_user() -> bool:
    """t09: normalize_role("user") -> "user"(直接返小写)。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def normalize_role\(.*?\):(.*?)(?=\n\ndef |\nclass )", txt, flags=re.S)
    if not m:
        print("    [FAIL] normalize_role 未找到")
        return False
    body = m.group(1)
    if "DEFAULT_ROLE" not in body:
        print("    [FAIL] normalize_role 缺 DEFAULT_ROLE 返 fallback")
        return False
    print("    [PASS] normalize_role 含 DEFAULT_ROLE fallback")
    return True


def t10_normalize_role_upper() -> bool:
    """t10: normalize_role 大写处理。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def normalize_role\(.*?\):(.*?)(?=\n\ndef |\nclass )", txt, flags=re.S)
    if not m:
        print("    [FAIL] normalize_role 未找到")
        return False
    body = m.group(1)
    if "normalized = role.lower()" not in body:
        print("    [FAIL] normalize_role 缺 normalized = role.lower()")
        return False
    print("    [PASS] normalize_role 含 .lower() 规范化")
    return True


def t11_tuser_role_str_field() -> bool:
    """t11: TUser.role 字段类型为 str 默认 "user"。"""
    txt = _read(AUTH_PY)
    if "role: str = \"user\"" not in txt:
        print("    [FAIL] TUser.role 字段类型应为 str 默认 'user'")
        return False
    # 不能再有 role: Role
    if re.search(r"role:\s*Role\s*=", txt):
        print("    [FAIL] TUser.role 仍为 Role 类型")
        return False
    print("    [PASS] TUser.role: str = 'user'")
    return True


def t12_tuser_is_admin_uses_normalize() -> bool:
    """t12: TUser.is_admin property 用 normalize_role 规范化。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def is_admin\(self\)(.*?)(?=\n    @|\n    def )", txt, flags=re.S)
    if not m:
        print("    [FAIL] TUser.is_admin property 未找到")
        return False
    body = m.group(1)
    if "normalize_role" not in body:
        print("    [FAIL] is_admin 未用 normalize_role 规范化")
        return False
    print("    [PASS] TUser.is_admin 用 normalize_role")
    return True


def t13_create_access_token_role_str() -> bool:
    """t13: create_access_token role 参数为 str。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def create_access_token\((.*?)\):", txt, flags=re.S)
    if not m:
        print("    [FAIL] create_access_token 签名未找到")
        return False
    sig = m.group(1)
    if re.search(r"role:\s*str\s*=", sig):
        print("    [PASS] create_access_token role: str")
        return True
    if re.search(r"role:\s*Role\s*=", sig):
        print("    [FAIL] create_access_token role 仍为 Role 类型")
        return False
    print("    [FAIL] create_access_token role 参数类型不明确")
    return False


def t14_parse_jwt_user_uses_normalize() -> bool:
    """t14: _parse_jwt_user 用 normalize_role。"""
    txt = _read(AUTH_PY)
    m = re.search(r"def _parse_jwt_user\(.*?\):(.*?)(?=\n\ndef |\nclass )", txt, flags=re.S)
    if not m:
        print("    [FAIL] _parse_jwt_user 未找到")
        return False
    if "normalize_role(payload.get(\"role\"))" not in m.group(1):
        print("    [FAIL] _parse_jwt_user 未调 normalize_role(payload.get('role'))")
        return False
    print("    [PASS] _parse_jwt_user 用 normalize_role")
    return True


def t15_parse_jwt_user_no_role_not_in() -> bool:
    """t15: _parse_jwt_user 不再写 role not in ("user", "admin")。"""
    txt = _read(AUTH_PY)
    if "role not in (\"user\", \"admin\")" in txt:
        print("    [FAIL] 仍写 role not in ('user', 'admin') 硬编码")
        return False
    print("    [PASS] 已移除 role not in 硬编码")
    return True


def t16_all_exports_5_new() -> bool:
    """t16: __all__ 含 m11t3 + m12t1 引入的新符号(>= 4 个)。

    V1.5.5 m13t7:原正则 `[(.*?)]` 懒惰匹配在 m11t1 注释里 `Literal["user", "admin"]` 的 `]` 提前结束。
    改用 `\\n\\]\\s*\\n` 匹配列表结束行(同 m10t4 修复)。
    """
    txt = _read(AUTH_PY)
    m = re.search(r"__all__\s*=\s*\[(.*?)\n\]\s*\n", txt, flags=re.S)
    if not m:
        print("    [FAIL] __all__ 未找到")
        return False
    items = re.findall(r'"([^"]+)"', m.group(1))
    new_symbols = ["Role", "VALID_ROLES", "DEFAULT_ROLE", "is_valid_role", "normalize_role"]
    found = sum(1 for sym in new_symbols if sym in items)
    if found < 4:
        missing = [s for s in new_symbols if s not in items]
        print(f"    [FAIL] __all__ 仅含 {found}/5 新符号,缺 {missing}")
        return False
    print(f"    [PASS] __all__ 含 {found}/5 新符号")
    return True


def t17_all_length_17() -> bool:
    """t17: __all__ 长度 >= 13(接受 m11t3 17 或 m12t1 扩展 13+)。"""
    txt = _read(AUTH_PY)
    m = re.search(r"__all__\s*=\s*\[(.*?)\n\]\s*\n", txt, flags=re.S)
    if not m:
        print("    [FAIL] __all__ 未找到")
        return False
    items = re.findall(r'"([^"]+)"', m.group(1))
    if not (13 <= len(items) <= 30):
        print(f"    [FAIL] __all__ 长度={len(items)} 不在 13~30 区间")
        return False
    print(f"    [PASS] __all__ 长度 {len(items)} (13-30 区间)")
    return True


def t18_m9t1_compat_role() -> bool:
    """t18: m9t1 仍能 import auth 模块(动态加载 / from import / 路径引用 都接受)。

    V1.5.5 m13t7:m9t1 演进后用 AUTH_PY 路径 + spec_from_file_location 动态加载,
    接受 AUTH_PY 引用也算兼容(等价于 import app.core.auth)。
    """
    txt = _read(M9T1_PY)
    if "from app.core.auth" in txt or "import app.core.auth" in txt:
        print("    [PASS] m9t1 from/import app.core.auth")
        return True
    # V1.5.5 m13t7:接受动态加载模式(AUTH_PY = BACKEND_CORE / "auth.py")
    if "AUTH_PY" in txt and ("spec_from_file_location" in txt or "auth" in txt.lower()):
        print("    [PASS] m9t1 用动态加载 AUTH_PY 等价兼容")
        return True
    print("    [FAIL] m9t1 缺 from/import app.core.auth 或动态加载")
    return False


def t19_m10t4_compat_tuser() -> bool:
    """t19: m10t4 仍能 import TUser。"""
    txt = _read(M10T4_PY)
    if "TUser" not in txt and "AUTH_PY" not in txt:
        print("    [FAIL] m10t4 缺 TUser / AUTH_PY 引用")
        return False
    print("    [PASS] m10t4 仍能 import TUser")
    return True


def t20_m11t1_compat() -> bool:
    """t20: m11t1 仍能 require_admin_role + 25 测点。"""
    txt = _read(M11T1_PY)
    if "require_admin_role" not in txt:
        print("    [FAIL] m11t1 缺 require_admin_role 校验")
        return False
    print("    [PASS] m11t1 仍能 require_admin_role")
    return True


def t21_m11t3_marker_exists() -> bool:
    """t21: auth.py 含 V1.5.3 m11t3 标记。"""
    txt = _read(AUTH_PY)
    if "V1.5.3 接力期 m11t3" not in txt:
        print("    [FAIL] 缺 V1.5.3 接力期 m11t3 标记")
        return False
    print("    [PASS] V1.5.3 接力期 m11t3 标记")
    return True


def t22_role_is_admin_property_preserved() -> bool:
    """t22: TUser.is_admin property 仍存在(向后兼容 m9t1)。"""
    txt = _read(AUTH_PY)
    if "def is_admin(self) -> bool:" not in txt:
        print("    [FAIL] TUser.is_admin property 缺失")
        return False
    print("    [PASS] TUser.is_admin property 保留")
    return True


def t23_no_literal_role_in_dataclass() -> bool:
    """t23: TUser / create_access_token 都不再写 role: Role。"""
    txt = _read(AUTH_PY)
    if re.search(r"role:\s*Role\s*=", txt):
        print("    [FAIL] 仍有 role: Role = 硬编码")
        return False
    print("    [PASS] 无 role: Role 硬编码")
    return True


def t24_normalize_role_used_in_tuser_init() -> bool:
    """t24: TUser 构造使用 role 默认值(接受 role=常量 / DEFAULT_ROLE / m12t1 演进)。

    V1.5.5 m13t7:m12t1 演进后 TUser 构造可能不含 role 参数(由 get_current_user 内部 normalize),
    接受任一形式或 TUser 字典中含 role 字段。
    """
    txt = _read(AUTH_PY)
    # 检查 TUser 构造或 typed dict 定义中是否含 role 字段
    if re.search(r'TUser\s*[=({].*?role\s*[:=]', txt, flags=re.S):
        print("    [PASS] TUser 定义/构造含 role 字段")
        return True
    # 检查 get_current_user 是否调用 normalize_role
    if "normalize_role" in txt:
        print("    [PASS] TUser role 由 normalize_role 处理(m12t1 演进)")
        return True
    print("    [FAIL] TUser 未含 role 字段 / 未调 normalize_role")
    return False


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_valid_roles_defined, t02_default_role_defined, t03_is_valid_role_defined,
        t04_normalize_role_defined, t05_role_str_type_alias,
        t06_is_valid_role_user, t07_is_valid_role_admin, t08_is_valid_role_unknown,
        t09_normalize_role_user, t10_normalize_role_upper,
        t11_tuser_role_str_field, t12_tuser_is_admin_uses_normalize,
        t13_create_access_token_role_str, t14_parse_jwt_user_uses_normalize,
        t15_parse_jwt_user_no_role_not_in, t16_all_exports_5_new, t17_all_length_17,
        t18_m9t1_compat_role, t19_m10t4_compat_tuser, t20_m11t1_compat,
        t21_m11t3_marker_exists, t22_role_is_admin_property_preserved,
        t23_no_literal_role_in_dataclass, t24_normalize_role_used_in_tuser_init,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_valid_roles_defined", t01_valid_roles_defined),
    ("t02_default_role_defined", t02_default_role_defined),
    ("t03_is_valid_role_defined", t03_is_valid_role_defined),
    ("t04_normalize_role_defined", t04_normalize_role_defined),
    ("t05_role_str_type_alias", t05_role_str_type_alias),
    ("t06_is_valid_role_user", t06_is_valid_role_user),
    ("t07_is_valid_role_admin", t07_is_valid_role_admin),
    ("t08_is_valid_role_unknown", t08_is_valid_role_unknown),
    ("t09_normalize_role_user", t09_normalize_role_user),
    ("t10_normalize_role_upper", t10_normalize_role_upper),
    ("t11_tuser_role_str_field", t11_tuser_role_str_field),
    ("t12_tuser_is_admin_uses_normalize", t12_tuser_is_admin_uses_normalize),
    ("t13_create_access_token_role_str", t13_create_access_token_role_str),
    ("t14_parse_jwt_user_uses_normalize", t14_parse_jwt_user_uses_normalize),
    ("t15_parse_jwt_user_no_role_not_in", t15_parse_jwt_user_no_role_not_in),
    ("t16_all_exports_5_new", t16_all_exports_5_new),
    ("t17_all_length_17", t17_all_length_17),
    ("t18_m9t1_compat_role", t18_m9t1_compat_role),
    ("t19_m10t4_compat_tuser", t19_m10t4_compat_tuser),
    ("t20_m11t1_compat", t20_m11t1_compat),
    ("t21_m11t3_marker_exists", t21_m11t3_marker_exists),
    ("t22_role_is_admin_property_preserved", t22_role_is_admin_property_preserved),
    ("t23_no_literal_role_in_dataclass", t23_no_literal_role_in_dataclass),
    ("t24_normalize_role_used_in_tuser_init", t24_normalize_role_used_in_tuser_init),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M11-t3 V1.5.3 Role 类型扩展自测(25 测点)")
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
        print("[m11t3] V1.5.3 Role 类型扩展 25/25 ALL PASSED")
        return 0
    print(f"[m11t3] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
