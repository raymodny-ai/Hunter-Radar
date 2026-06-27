"""m19t3 V1.6.0 P1 后端 API 完整性自测(25 测点)。

注:项目无 frontend/ 目录,本脚本验证后端 API 层完整性。

Section 1: Attribution API 端点 (5)
Section 2: Regime Timeline API 端点 (5)
Section 3: main.py 路由注册 (5)
Section 4: Screener 物化视图集成 (5)
Section 5: Pipeline 集成 (5)

静态分析为主。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

PASS = "[PASS]"
FAIL = "[FAIL]"
_passed = 0
_total = 0


def t(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _total
    _total += 1
    if ok:
        _passed += 1
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)


# ============================================================
# Section 1: Attribution API 端点 (5)
# ============================================================
def test_attribution_api() -> None:
    print("\n=== Section 1: Attribution API 端点 (5) ===", flush=True)
    fp = BACKEND / "app" / "api" / "attribution.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: router 定义
    t("attr_api_router", "router = APIRouter()" in src)

    # t2: GET 路由
    t("attr_api_get_route", "/symbols/{ticker}/attribution" in src)

    # t3: compute_attribution 调用
    t("attr_api_compute_call", "compute_attribution" in src)

    # t4: weights JSON 解析
    t("attr_api_weights_parse", "json.loads" in src or "json" in src)

    # t5: to_dict 序列化
    t("attr_api_to_dict", "to_dict()" in src)


# ============================================================
# Section 2: Regime Timeline API 端点 (5)
# ============================================================
def test_regime_timeline_api() -> None:
    print("\n=== Section 2: Regime Timeline API 端点 (5) ===", flush=True)
    fp = BACKEND / "app" / "api" / "regime_timeline.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: router 定义
    t("rt_api_router", "router = APIRouter()" in src)

    # t2: GET /regime/timeline
    t("rt_api_route", "/regime/timeline" in src)

    # t3: RegimeTimelineDTO
    t("rt_api_dto", "class RegimeTimelineDTO" in src)

    # t4: RegimeTimelinePoint
    t("rt_api_point", "class RegimeTimelinePoint" in src)

    # t5: decide_regime 使用
    t("rt_api_decide", "decide_regime" in src)


# ============================================================
# Section 3: main.py 路由注册 (5)
# ============================================================
def test_main_registration() -> None:
    print("\n=== Section 3: main.py 路由注册 (5) ===", flush=True)
    fp = BACKEND / "app" / "main.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: attribution import
    t("main_import_attribution", "attribution" in src)

    # t2: regime_timeline import
    t("main_import_regime_timeline", "regime_timeline" in src)

    # t3: attribution router 注册
    t("main_router_attribution", "attribution.router" in src and "include_router" in src)

    # t4: regime_timeline router 注册
    t("main_router_regime_timeline", "regime_timeline.router" in src and "include_router" in src)

    # t5: tag 注册
    t("main_tags", '"attribution"' in src and '"regime-timeline"' in src)


# ============================================================
# Section 4: Screener 物化视图集成 (5)
# ============================================================
def test_screener_mv() -> None:
    print("\n=== Section 4: Screener 物化视图集成 (5) ===", flush=True)
    fp = BACKEND / "app" / "api" / "screener.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: mv_screener_top100 引用
    t("scr_mv_reference", "mv_screener_top100" in src)

    # t2: use_mv 条件
    t("scr_mv_condition", "use_mv" in src)

    # t3: trade_date is None 条件
    t("scr_mv_date_check", "trade_date is None" in src)

    # t4: 降级到原查询(try/except)
    t("scr_mv_fallback", "except" in src and "降级" in src)

    # t5: threat_score DESC LIMIT
    t("scr_mv_order", "threat_score DESC" in src or "ORDER BY threat_score DESC" in src)


# ============================================================
# Section 5: Pipeline 集成 (5)
# ============================================================
def test_pipeline_integration() -> None:
    print("\n=== Section 5: Pipeline 集成 (5) ===", flush=True)
    fp = BACKEND / "etl" / "pipeline.py"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: DataProviderManager import
    t("pipe_provider_mgr", "DataProviderManager" in src or "provider_mgr" in src)

    # t2: validate_daily_price 调用
    t("pipe_validate_price", "validate_daily_price" in src)

    # t3: validate_options_chain 调用
    t("pipe_validate_options", "validate_options_chain" in src)

    # t4: 物化视图刷新
    t("pipe_mv_refresh", "mv_screener_top100" in src and "REFRESH" in src.upper())

    # t5: retry_policy 集成
    t("pipe_retry", "retry_policy" in src or "run_stage_with_retry" in src or "etl_retry" in src)


# ============================================================
# main
# ============================================================
def main() -> int:
    test_attribution_api()
    test_regime_timeline_api()
    test_main_registration()
    test_screener_mv()
    test_pipeline_integration()

    print(flush=True)
    ok = _passed == _total
    if ok:
        print(f"[m19t3] {_passed}/{_total} ALL PASSED")
    else:
        print(f"[m19t3] {_passed}/{_total} ({_total - _passed} FAILED)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
