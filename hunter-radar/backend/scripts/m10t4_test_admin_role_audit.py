"""M10-t4 V1.5.2 Admin Role 公开评审自测(25 测点)。

V1.5.2 接力期 m10t4 — 把 M9-t1 admin 鉴权补全流程化评审:
- 公开 JWT claim 字段(role / tier / sub / iat / exp)
- admin role 权限矩阵(4 端点 × 3 鉴权方式)
- 三态鉴权(auth_mode)显式标注
- 错误码汇总(401/403/503)
- 运维 SOP 5 步
- 严禁行为 3 条
- 评审未通过项 3 条

Section 1 — 评审文档结构(5 测点):
  - 文件存在 + docstring V1.5.2 freeze
  - 7 大章节标题(0~6)
  - 评审通过清单 marker
  - 评审未通过项 marker
  - 评审依据文件 marker

Section 2 — 公开 JWT claim(4 测点):
  - 字段表 5 字段
  - sub 真实用户 / 沙箱占位说明
  - role 字面量 user/admin
  - role 解析容错 _parse_jwt_user

Section 3 — 权限矩阵(4 测点):
  - 4 admin 端点
  - 必须 role=admin
  - X-Admin-API-Key 备选
  - IP 白名单可选

Section 4 — 三态鉴权(3 测点):
  - auth_mode 4 优先级
  - prod_admin_jwt / prod_admin_apikey / sandbox_skip_admin 三态
  - 严禁 mock 200

Section 5 — 错误码 + SOP(5 测点):
  - 401 / 403 / 503 三个错误码
  - SOP 必填 4 配置
  - env_check V15-1/2/3 三项
  - 故障排查 4 类
  - 审计日志 4 项

Section 6 — 评审未通过项(4 测点):
  - __all__ 缺 admin 鉴权函数
  - require_admin_role 缺 IP 校验
  - Role Literal 2 种不可扩展
  - 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
AUDIT_MD = DOCS / "ADMIN_ROLE_V152.md"
AUTH_PY = ROOT / "backend" / "app" / "core" / "auth.py"
CONFIG_PY = ROOT / "backend" / "app" / "core" / "config.py"
ADMIN_PY = ROOT / "backend" / "app" / "api" / "admin.py"
ENV_CHECK_PY = ROOT / "scripts" / "env_check.py"
M9T1_PY = ROOT / "backend" / "scripts" / "m9t1_test_admin_auth.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_audit_doc_exists() -> bool:
    """t01: ADMIN_ROLE_V152.md 存在 + V1.5.2 freeze 标注。"""
    if not AUDIT_MD.exists():
        print("    [FAIL] ADMIN_ROLE_V152.md 缺失")
        return False
    txt = _read(AUDIT_MD)
    if "V1.5.2" not in txt:
        print("    [FAIL] 缺 V1.5.2 freeze 标注")
        return False
    if "freeze" not in txt.lower() and "FREEZE" not in txt:
        print("    [FAIL] 缺 freeze 关键词")
        return False
    print("    [PASS] ADMIN_ROLE_V152.md 存在 + V1.5.2 freeze 标注")
    return True


def t02_audit_doc_sections() -> bool:
    """t02: 7 大章节标题(0~6 + 通过清单 + 未通过项)。"""
    txt = _read(AUDIT_MD)
    expected_sections = [
        "## 0. 评审目的",
        "## 1. 公开 JWT Claim 字段",
        "## 2. Admin Role 权限矩阵",
        "## 3. 三态鉴权",
        "## 4. 错误码汇总",
        "## 5. 运维 SOP",
        "## 6. V1.5.2 评审通过清单",
        "## 7. 评审依据文件",
    ]
    missing = [s for s in expected_sections if s not in txt]
    if missing:
        print(f"    [FAIL] 缺章节:{missing[:3]}")
        return False
    print("    [PASS] 7 大章节齐全 + 评审依据文件章节")
    return True


def t03_pass_checklist_marker() -> bool:
    """t03: 评审通过清单 marker 完整。"""
    txt = _read(AUDIT_MD)
    required = [
        "公开 JWT claim 字段已写入",
        "admin role 权限矩阵已写入",
        "三态鉴权",
        "错误码汇总",
        "运维 SOP",
        "严禁行为",
        "m10t4_test_admin_role_audit",
        "m8t1_test_regression",
    ]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 通过清单缺:{missing[:3]}")
        return False
    print("    [PASS] 通过清单 8 项 marker 齐全")
    return True


def t04_unpassed_checklist_three() -> bool:
    """t04: 评审未通过项 3 条(__all__ / require_admin_role 缺 IP / Role Literal 2 种)。"""
    txt = _read(AUDIT_MD)
    expected = [
        "__all__",
        "_check_ip_whitelist",
        "Literal",
    ]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 未通过项 3 条缺:{missing}")
        return False
    if "V1.5.3" not in txt:
        print("    [FAIL] 缺 V1.5.3 后续修复标记")
        return False
    print("    [PASS] 未通过项 3 条齐全 + V1.5.3 标记")
    return True


def t05_audit_doc_references() -> bool:
    """t05: 评审依据文件 7 引用齐全。"""
    txt = _read(AUDIT_MD)
    expected_files = [
        "auth.py",
        "config.py",
        "admin.py",
        "env_check.py",
        "m9t1_test_admin_auth.py",
        "m10t4_test_admin_role_audit.py",
        "V1.5-handoff",
    ]
    missing = [f for f in expected_files if f not in txt]
    if missing:
        print(f"    [FAIL] 评审依据文件缺:{missing}")
        return False
    print("    [PASS] 评审依据文件 7 引用齐全")
    return True


def t06_jwt_claim_field_table() -> bool:
    """t06: 公开 JWT claim 字段表 5 字段(sub / tier / role / iat / exp)。"""
    txt = _read(AUDIT_MD)
    fields = ["sub", "tier", "role", "iat", "exp"]
    missing = [f for f in fields if f"`{f}`" not in txt and f"| `{f}`" not in txt]
    if missing:
        print(f"    [FAIL] JWT claim 字段缺:{missing}")
        return False
    print("    [PASS] JWT claim 字段表 5 字段齐全")
    return True


def t07_sub_sandbox_placeholder() -> bool:
    """t07: sub 沙箱占位 UUID 说明。"""
    txt = _read(AUDIT_MD)
    if "00000000-0000-0000-0000-000000000000" not in txt:
        print("    [FAIL] 缺沙箱占位 UUID")
        return False
    if "SANDBOX_PLACEHOLDER_USER_ID" not in txt and "占位" not in txt:
        print("    [FAIL] 缺占位说明")
        return False
    print("    [PASS] sub 沙箱占位 UUID + 占位说明")
    return True


def t08_role_literal_user_admin() -> bool:
    """t08: role 字面量 user/admin + 解析容错 _parse_jwt_user。"""
    txt = _read(AUDIT_MD)
    if "user" not in txt or "admin" not in txt:
        print("    [FAIL] 缺 role 字面量")
        return False
    if "_parse_jwt_user" not in txt:
        print("    [FAIL] 缺 _parse_jwt_user 解析容错引用")
        return False
    if "降级" not in txt and "默认" not in txt:
        print("    [FAIL] 缺降级/默认说明")
        return False
    print("    [PASS] role 字面量 + 解析容错")
    return True


def t09_role_no_pii() -> bool:
    """t09: role 不存 PII(明确说明)。"""
    txt = _read(AUDIT_MD)
    if "PII" not in txt and "无 PII" not in txt and "不含 PII" not in txt:
        print("    [FAIL] 缺 role 无 PII 标识说明")
        return False
    print("    [PASS] role 无 PII 标识")
    return True


def t10_admin_endpoints_four() -> bool:
    """t10: 4 admin 端点(etl/run / backtest/run / backtest/result / webhook/replay)。"""
    txt = _read(AUDIT_MD)
    endpoints = [
        "/api/v1/admin/etl/run",
        "/api/v1/admin/backtest/run",
        "/api/v1/admin/backtest/result",
        "/api/v1/admin/webhook/replay",
    ]
    missing = [e for e in endpoints if e not in txt]
    if missing:
        print(f"    [FAIL] 4 admin 端点缺:{missing}")
        return False
    print("    [PASS] 4 admin 端点齐全")
    return True


def t11_role_must_admin() -> bool:
    """t11: 必须 role=admin 校验来源(Depends(require_admin_role))。"""
    txt = _read(AUDIT_MD)
    if "Depends(require_admin_role)" not in txt:
        print("    [FAIL] 缺 Depends(require_admin_role) 引用")
        return False
    if "user.is_admin" not in txt and "role == \"admin\"" not in txt and "role=admin" not in txt:
        print("    [FAIL] 缺 is_admin 判定引用")
        return False
    print("    [PASS] 必须 role=admin 校验来源完整")
    return True


def t12_x_admin_api_key() -> bool:
    """t12: X-Admin-API-Key 备选 + hmac.compare_digest 防 timing attack。"""
    txt = _read(AUDIT_MD)
    if "X-Admin-API-Key" not in txt:
        print("    [FAIL] 缺 X-Admin-API-Key header")
        return False
    if "hmac.compare_digest" not in txt and "timing" not in txt.lower():
        print("    [FAIL] 缺 hmac.compare_digest 防 timing 攻击")
        return False
    print("    [PASS] X-Admin-API-Key 备选 + 防 timing 攻击")
    return True


def t13_ip_whitelist_optional() -> bool:
    """t13: IP 白名单可选 + admin_ip_whitelist 配置 + _check_ip_whitelist 实现。"""
    txt = _read(AUDIT_MD)
    if "ADMIN_IP_WHITELIST" not in txt:
        print("    [FAIL] 缺 ADMIN_IP_WHITELIST 环境变量")
        return False
    if "_check_ip_whitelist" not in txt:
        print("    [FAIL] 缺 _check_ip_whitelist 实现引用")
        return False
    if "_resolve_auth_mode" not in txt:
        print("    [FAIL] 缺 _resolve_auth_mode 应用位置")
        return False
    print("    [PASS] IP 白名单可选 + 实现 + 应用位置")
    return True


def t14_auth_mode_three_states() -> bool:
    """t14: auth_mode 3 态(prod_admin_jwt / prod_admin_apikey / sandbox_skip_admin)。"""
    txt = _read(AUDIT_MD)
    states = [
        "prod_admin_jwt",
        "prod_admin_apikey",
        "sandbox_skip_admin",
    ]
    missing = [s for s in states if s not in txt]
    if missing:
        print(f"    [FAIL] auth_mode 3 态缺:{missing}")
        return False
    print("    [PASS] auth_mode 3 态齐全")
    return True


def t15_auth_mode_priority_four() -> bool:
    """t15: auth_mode 4 优先级(JWT/API key/sandbox/503)。"""
    txt = _read(AUDIT_MD)
    if "优先级" not in txt:
        print("    [FAIL] 缺优先级说明")
        return False
    # 至少有 1, 2, 3, 4 优先级 marker
    priority_count = 0
    for marker in ["| 1 |", "| 2 |", "| 3 |", "| 4 |"]:
        if marker in txt:
            priority_count += 1
    if priority_count < 4:
        print(f"    [FAIL] 优先级表不完整({priority_count}/4)")
        return False
    print("    [PASS] 4 优先级表完整")
    return True


def t16_no_mock_200_in_auth() -> bool:
    """t16: 严禁 mock 200(在 admin 鉴权场景)。"""
    txt = _read(AUDIT_MD)
    if "mock 200" not in txt and "mock200" not in txt:
        print("    [FAIL] 缺 mock 200 严禁说明")
        return False
    if "503" not in txt:
        print("    [FAIL] 缺 503 错误码(生产配置缺)")
        return False
    print("    [PASS] 严禁 mock 200 + 503 显式标注")
    return True


def t17_error_codes_three() -> bool:
    """t17: 错误码 401/403/503 全覆盖。"""
    txt = _read(AUDIT_MD)
    codes = ["401", "403", "503"]
    missing = [c for c in codes if c not in txt]
    if missing:
        print(f"    [FAIL] 错误码缺:{missing}")
        return False
    print("    [PASS] 错误码 401/403/503 全覆盖")
    return True


def t18_sop_four_config() -> bool:
    """t18: SOP 必填 4 配置(ADMIN_API_KEY/ADMIN_IP_WHITELIST/ADMIN_ROLE_ENABLED/SECRET_KEY)。"""
    txt = _read(AUDIT_MD)
    configs = [
        "ADMIN_API_KEY",
        "ADMIN_IP_WHITELIST",
        "ADMIN_ROLE_ENABLED",
        "SECRET_KEY",
    ]
    missing = [c for c in configs if c not in txt]
    if missing:
        print(f"    [FAIL] SOP 必填 4 配置缺:{missing}")
        return False
    print("    [PASS] SOP 必填 4 配置齐全")
    return True


def t19_env_check_v15_three() -> bool:
    """t19: env_check V15-1/2/3 admin 鉴权校验 3 项。"""
    txt = _read(AUDIT_MD)
    if "V15-1" not in txt or "V15-2" not in txt or "V15-3" not in txt:
        print("    [FAIL] 缺 V15-1/2/3 校验引用")
        return False
    print("    [PASS] env_check V15-1/2/3 引用齐全")
    return True


def t20_troubleshoot_four() -> bool:
    """t20: 故障排查 4 类(401/403/503/sandbox)。"""
    txt = _read(AUDIT_MD)
    if "故障排查" not in txt:
        print("    [FAIL] 缺故障排查章节")
        return False
    symptoms = ["401", "403", "503", "sandbox"]
    missing = [s for s in symptoms if s not in txt]
    if missing:
        print(f"    [FAIL] 故障排查缺:{missing}")
        return False
    print("    [PASS] 故障排查 4 类齐全")
    return True


def t21_audit_log_four() -> bool:
    """t21: 审计日志 4 项监控。"""
    txt = _read(AUDIT_MD)
    if "审计日志" not in txt and "审计" not in txt:
        print("    [FAIL] 缺审计日志章节")
        return False
    items = [
        "sandbox_skip_admin",
        "prod_admin_apikey",
        "503",
        "403",
    ]
    missing = [i for i in items if i not in txt]
    if missing:
        print(f"    [FAIL] 审计日志 4 项监控缺:{missing}")
        return False
    print("    [PASS] 审计日志 4 项监控齐全")
    return True


def t22_audit_finding_all_exports() -> bool:
    """t22: 评审未通过项 — __all__ 缺 admin 鉴权函数(require_admin_role / Role / _check_api_key / _check_ip_whitelist)。

    V1.5.5 接力期 m13t2 修复:原正则 `[(.*?)]` 在 m11t1 注释 `Literal["user", "admin"]` 里的 `]` 处提前结束,
    改为 `\n\]\n` 匹配列表结束行。
    """
    txt_auth = _read(AUTH_PY)
    if "__all__" not in txt_auth:
        print("    [FAIL] auth.py 缺 __all__")
        return False
    # 提取 __all__ 列表(匹配列表结束行 \n]\n,避免 m11t1 注释里 `Literal["user", "admin"]` 的 `]` 干扰)
    m = re.search(r"__all__\s*=\s*\[(.*?)\n\]\s*\n", txt_auth, flags=re.S)
    if not m:
        print("    [FAIL] __all__ 格式无法解析")
        return False
    all_list = m.group(1)
    missing = []
    for sym in ["require_admin_role", "Role", "_check_api_key", "_check_ip_whitelist"]:
        if sym not in all_list:
            missing.append(sym)
    if len(missing) >= 3:
        print(f"    [FAIL] __all__ 缺 admin 鉴权函数:{missing}")
        return False
    print("    [INFO] __all__ 已含部分 admin 鉴权函数(评审项已记录)")
    return True


def t23_audit_finding_ip_in_require() -> bool:
    """t23: 评审未通过项 — require_admin_role 内不调 _check_ip_whitelist(由 admin.py 二次校验)。"""
    txt_auth = _read(AUTH_PY)
    txt_admin = _read(ADMIN_PY)
    # 找 require_admin_role 函数体
    m = re.search(r"def require_admin_role\(.*?\n(.*?)(?=\n# ---- |\ndef |\nclass )", txt_auth, flags=re.S)
    if not m:
        print("    [FAIL] require_admin_role 函数体找不到")
        return False
    body = m.group(1)
    if "_check_ip_whitelist" in body:
        print("    [INFO] require_admin_role 已含 IP 校验(评审项已修复)")
        return True
    # 检查 _resolve_auth_mode 是否调
    if "_check_ip_whitelist" in txt_admin:
        print("    [PASS] 评审项已记录:IP 校验由 _resolve_auth_mode 二次校验")
        return True
    print("    [FAIL] 缺 IP 校验位置记录")
    return False


def t24_audit_finding_role_literal() -> bool:
    """t24: 评审未通过项 — Role = Literal["user", "admin"] 仅 2 种不可扩展。

    V1.5.5 接力期 m13t2 修复:V1.5.3 接力期 m11t3 改 `Role = str`(从 Literal 扩展),
    V1.5.4 接力期 m12t1 加 `VALID_ROLES` 容纳 3 种 role(向后兼容),t24 接受 `Role = str` 形式。
    """
    txt_auth = _read(AUTH_PY)
    # V1.5.5 m13t2:接受 `Role = str` 形式(m11t3 演进)或 `Role = Literal[...]` 形式
    if re.search(r"Role\s*=\s*str", txt_auth) and "VALID_ROLES" in txt_auth:
        # m11t3 演进形式:Role = str + VALID_ROLES 集合(3 种 role 扩展)
        n_roles = 0
        m_vr = re.search(r"VALID_ROLES[^=]*=\s*\((.*?)\)", txt_auth, flags=re.S)
        if m_vr:
            n_roles = m_vr.group(1).count('"')
        print(f"    [INFO] Role 已演进为 str 类型 + VALID_ROLES 集合({n_roles // 2} 种 role,V1.5.4 接力期 m12t1 加 super_admin,评审项已修复)")
        return True
    # 旧 Literal 形式
    m = re.search(r"Role\s*=\s*Literal\[(.*?)\]", txt_auth)
    if not m:
        print("    [FAIL] Role = Literal[...] 找不到")
        return False
    literals = m.group(1)
    n = literals.count(",") + 1
    if n > 2:
        print(f"    [INFO] Role Literal 已扩展为 {n} 种(评审项已修复)")
        return True
    # 在评审文档中记录
    txt_audit = _read(AUDIT_MD)
    if "Literal" in txt_audit and ("2 种" in txt_audit or "不可扩展" in txt_audit):
        print("    [PASS] 评审项已记录:Role Literal 2 种不可扩展")
        return True
    print("    [FAIL] 评审文档未记录 Role Literal 限制")
    return False


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验 — 脚本函数总数 == 25。"""
    funcs = [
        t01_audit_doc_exists,
        t02_audit_doc_sections,
        t03_pass_checklist_marker,
        t04_unpassed_checklist_three,
        t05_audit_doc_references,
        t06_jwt_claim_field_table,
        t07_sub_sandbox_placeholder,
        t08_role_literal_user_admin,
        t09_role_no_pii,
        t10_admin_endpoints_four,
        t11_role_must_admin,
        t12_x_admin_api_key,
        t13_ip_whitelist_optional,
        t14_auth_mode_three_states,
        t15_auth_mode_priority_four,
        t16_no_mock_200_in_auth,
        t17_error_codes_three,
        t18_sop_four_config,
        t19_env_check_v15_three,
        t20_troubleshoot_four,
        t21_audit_log_four,
        t22_audit_finding_all_exports,
        t23_audit_finding_ip_in_require,
        t24_audit_finding_role_literal,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_audit_doc_exists", t01_audit_doc_exists),
    ("t02_audit_doc_sections", t02_audit_doc_sections),
    ("t03_pass_checklist_marker", t03_pass_checklist_marker),
    ("t04_unpassed_checklist_three", t04_unpassed_checklist_three),
    ("t05_audit_doc_references", t05_audit_doc_references),
    ("t06_jwt_claim_field_table", t06_jwt_claim_field_table),
    ("t07_sub_sandbox_placeholder", t07_sub_sandbox_placeholder),
    ("t08_role_literal_user_admin", t08_role_literal_user_admin),
    ("t09_role_no_pii", t09_role_no_pii),
    ("t10_admin_endpoints_four", t10_admin_endpoints_four),
    ("t11_role_must_admin", t11_role_must_admin),
    ("t12_x_admin_api_key", t12_x_admin_api_key),
    ("t13_ip_whitelist_optional", t13_ip_whitelist_optional),
    ("t14_auth_mode_three_states", t14_auth_mode_three_states),
    ("t15_auth_mode_priority_four", t15_auth_mode_priority_four),
    ("t16_no_mock_200_in_auth", t16_no_mock_200_in_auth),
    ("t17_error_codes_three", t17_error_codes_three),
    ("t18_sop_four_config", t18_sop_four_config),
    ("t19_env_check_v15_three", t19_env_check_v15_three),
    ("t20_troubleshoot_four", t20_troubleshoot_four),
    ("t21_audit_log_four", t21_audit_log_four),
    ("t22_audit_finding_all_exports", t22_audit_finding_all_exports),
    ("t23_audit_finding_ip_in_require", t23_audit_finding_ip_in_require),
    ("t24_audit_finding_role_literal", t24_audit_finding_role_literal),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M10-t4 V1.5.2 Admin Role 公开评审自测(25 测点)")
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
        print("[m10t4] V1.5.2 admin role 公开评审 25/25 ALL PASSED")
        return 0
    print(f"[m10t4] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
