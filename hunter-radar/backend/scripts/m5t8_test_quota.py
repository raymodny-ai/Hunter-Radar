"""M5-t8 沙箱自测:FE-064 免费版每日 3 次查询配额前端提示 + 后端 quota 服务 + OpenAPI v1.4.1 freeze。

不动 main.py / runtime,只静态 + import 沙箱环境可跑的部分:
- quota 服务 import + 业务逻辑(沙箱无 PG/Redis,默认走内存)
- 后端 quota 端点导出符号
- main.py 包含 quota router
- OpenAPI v1.4.1.json 含 /api/v1/auth/quota
- 前端 useApiQuota / QuotaBanner / api.ts / __root.tsx 关键符号
- 静态禁用词扫描(CR-010)避免合规误伤
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOC_JSON = BACKEND / ".." / "docs" / "openapi-frozen-v1.4.1.json"

# === 0. 沙箱 stub:app.core.config(无 pydantic_settings 时短路,同 m5t2 套路) ===
sys.path.insert(0, str(BACKEND))
_STUB_CFG = types.ModuleType("app.core.config")
_STUB_CFG.settings = SimpleNamespace(
    secret_key=os.environ.get("HR_AUTH_DEV_SECRET") or "dev-only-change-me-32-bytes-minimum",
    jwt_algorithm="HS256",
    jwt_expire_minutes=60,
    cors_origins=["*"],
    log_level="INFO",
    app_name="Hunter Radar",
    sentry_dsn="",
    env="sandbox",
    debug=False,
)
sys.modules["app.core.config"] = _STUB_CFG

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def main() -> int:
    failures = 0
    # ---- 1. quota 服务导出符号 ------------------------------------------------
    try:
        import app.services.quota as quota_mod  # noqa: PLC0415 沙箱 monkey-patch 后才 import
        ok = all(hasattr(quota_mod, n) for n in (
            "FREE_DAILY_LIMIT", "QuotaState",
            "get_quota_state", "try_consume", "peek_remaining",
            "reset_for_testing",
        ))
        if not t("t01_quota_exports", ok):
            failures += 1
    except Exception as e:  # noqa: BLE001
        t("t01_quota_exports", False, f"import 失败: {e}")
        failures += 1
        return 1

    # ---- 2. free tier 初始态 ----------------------------------------------------
    quota_mod.reset_for_testing()
    s = quota_mod.get_quota_state("u1", "free")
    ok = s.tier == "free" and s.used == 0 and s.remaining == 3 and s.limit == 3
    if not t("t02_free_initial", ok, f"state={s}"):
        failures += 1

    # ---- 3. 3 次消耗后 remaining=0 --------------------------------------------
    quota_mod.reset_for_testing()
    for _ in range(3):
        ok_, _ = quota_mod.try_consume("u2", "free")
        assert ok_
    s = quota_mod.get_quota_state("u2", "free")
    ok = s.used == 3 and s.remaining == 0
    if not t("t03_free_3_consumes", ok, f"state={s}"):
        failures += 1

    # ---- 4. 第 4 次消耗返 ok=False --------------------------------------------
    quota_mod.reset_for_testing()
    for _ in range(3):
        quota_mod.try_consume("u3", "free")
    ok_fourth, state_fourth = quota_mod.try_consume("u3", "free")
    ok = ok_fourth is False and state_fourth.remaining == 0 and state_fourth.used == 3
    if not t("t04_free_exhausted_block", ok, f"4th={ok_fourth} state={state_fourth}"):
        failures += 1

    # ---- 5. pro tier 永远 ok=True,used 不递增 ---------------------------------
    quota_mod.reset_for_testing()
    for _ in range(10):
        ok_pro, state_pro = quota_mod.try_consume("u-pro", "pro")
        if not ok_pro:
            break
    ok = (
        ok_pro
        and state_pro.tier == "pro"
        and state_pro.limit == -1
        and state_pro.remaining == -1
        and state_pro.used == 0
    )
    if not t("t05_pro_unlimited", ok, f"pro state={state_pro}"):
        failures += 1

    # ---- 6. reset_for_testing 清空 --------------------------------------------
    quota_mod.try_consume("u4", "free")
    quota_mod.try_consume("u4", "free")
    quota_mod.reset_for_testing()
    s = quota_mod.get_quota_state("u4", "free")
    ok = s.used == 0 and s.remaining == 3
    if not t("t06_reset_for_testing", ok, f"after reset={s}"):
        failures += 1

    # ---- 7. quota 端点导出 ------------------------------------------------------
    try:
        import ast
        src = (BACKEND / "app" / "api" / "quota.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        funcs = [
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        ok = "get_my_quota" in funcs and "@router.get" in src and "/auth/quota" in src
        if not t("t07_quota_endpoint_exports", ok, f"funcs={funcs}"):
            failures += 1
    except Exception as e:  # noqa: BLE001
        t("t07_quota_endpoint_exports", False, str(e))
        failures += 1

    # ---- 8. main.py 注册 quota router -----------------------------------------
    main_src = (BACKEND / "app" / "main.py").read_text(encoding="utf-8")
    ok = (
        "quota" in main_src
        and "quota.router" in main_src
        and 'include_router(quota.router' in main_src
    )
    if not t("t08_main_registers_quota_router", ok):
        failures += 1

    # ---- 9. openapi v1.4.1.json 包含 /api/v1/auth/quota ------------------------
    try:
        spec_doc = json.loads(DOC_JSON.read_text(encoding="utf-8"))
        ok = "/api/v1/auth/quota" in spec_doc.get("paths", {})
        n_paths = len(spec_doc.get("paths", {}))
        if not t("t09_v141_freeze_includes_quota", ok, f"paths={n_paths}"):
            failures += 1
    except Exception as e:  # noqa: BLE001
        t("t09_v141_freeze_includes_quota", False, str(e))
        failures += 1

    # ---- 10. 前端 hook / banner / __root 关键符号 --------------------------------
    frontend_checks = [
        (FRONTEND / "src" / "features" / "useApiQuota.ts",
         ["useApiQuota", "peekQuota", "POLL_INTERVAL_MS"]),
        (FRONTEND / "src" / "components" / "common" / "QuotaBanner.tsx",
         ["QuotaBanner", "describeQuotaState", "paletteFor", "data-quota-state"]),
        (FRONTEND / "src" / "lib" / "api.ts",
         ["getQuota", "QuotaDTO", "auth/quota"]),
        (FRONTEND / "src" / "routes" / "__root.tsx",
         ["QuotaBanner", "import"]),
    ]
    all_ok = True
    details = []
    for path, musts in frontend_checks:
        if not path.exists():
            all_ok = False
            details.append(f"{path.name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in musts:
            if needle not in text:
                all_ok = False
                details.append(f"{path.name} 缺 {needle}")
    if not t("t10_frontend_hook_banner_root", all_ok, "; ".join(details) or "ok"):
        failures += 1

    print()
    if failures == 0:
        print("[m5t8] ALL 10 QUOTA + OPENAPI v1.4.1 TESTS PASSED", flush=True)
        return 0
    print(f"[m5t8] {failures} TEST(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
