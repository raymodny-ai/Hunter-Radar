"""m19t2 V1.6.0 P1 模型优化自测(25 测点)。

Section 1: ML 权重优化器 weight_optimizer (5)
Section 2: VWMA 做空去噪 short_metrics (5)
Section 3: 物化视图 SQL (5)
Section 4: 归因分析服务 + API (5)
Section 5: Regime Timeline API (5)

静态分析为主,不依赖数据库运行时。
"""

from __future__ import annotations

import ast
import inspect
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
# Section 1: ML 权重优化器 (5)
# ============================================================
def test_weight_optimizer() -> None:
    print("\n=== Section 1: ML 权重优化器 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "weight_optimizer.py"

    # t1: 文件存在
    t("wo_file_exists", fp.exists(), str(fp))

    src = fp.read_text(encoding="utf-8")

    # t2: compute_prediction_contribution 函数
    t("wo_compute_prediction_contribution", "def compute_prediction_contribution" in src)

    # t3: optimize_weights 函数
    t("wo_optimize_weights", "def optimize_weights" in src)

    # t4: get_ml_weights 入口函数
    t("wo_get_ml_weights", "def get_ml_weights" in src)

    # t5: MLOptimizationResult dataclass
    t("wo_ml_optimization_result", "class MLOptimizationResult" in src)


# ============================================================
# Section 2: VWMA 做空去噪 (5)
# ============================================================
def test_vwma_short() -> None:
    print("\n=== Section 2: VWMA 做空去噪 (5) ===", flush=True)
    fp = BACKEND / "app" / "services" / "short_metrics.py"

    # t1: 文件存在
    t("sm_file_exists", fp.exists(), str(fp))

    src = fp.read_text(encoding="utf-8")

    # t2: compute_vwma_short_ratio 函数
    t("sm_compute_vwma", "def compute_vwma_short_ratio" in src)

    # t3: margin_balance_cross_validation 函数
    t("sm_margin_balance", "def margin_balance_cross_validation" in src)

    # t4: z_score_rolling 有 smoothing 参数
    t("sm_smoothing_param", "smoothing" in src and "def z_score_rolling" in src)

    # t5: volume 加权逻辑
    t("sm_volume_weighted", "volume" in src.lower() and ("w_i" in src or "weights" in src or "/ sum" in src))


# ============================================================
# Section 3: 物化视图 SQL (5)
# ============================================================
def test_materialized_view() -> None:
    print("\n=== Section 3: 物化视图 SQL (5) ===", flush=True)
    fp = BACKEND / "sql" / "02_v1.6.0_materialized_views.sql"

    # t1: SQL 文件存在
    t("mv_sql_exists", fp.exists(), str(fp))

    src = fp.read_text(encoding="utf-8")

    # t2: CREATE MATERIALIZED VIEW
    t("mv_create_view", "MATERIALIZED VIEW" in src.upper())

    # t3: mv_screener_top100
    t("mv_screener_top100", "mv_screener_top100" in src)

    # t4: UNIQUE INDEX
    t("mv_unique_index", "UNIQUE INDEX" in src.upper())

    # t5: CONCURRENTLY refresh
    t("mv_concurrently", "CONCURRENTLY" in src.upper())


# ============================================================
# Section 4: 归因分析服务 + API (5)
# ============================================================
def test_attribution() -> None:
    print("\n=== Section 4: 归因分析服务 + API (5) ===", flush=True)

    # t1: 服务文件存在
    svc_fp = BACKEND / "app" / "services" / "attribution.py"
    t("attr_service_exists", svc_fp.exists(), str(svc_fp))

    svc_src = svc_fp.read_text(encoding="utf-8") if svc_fp.exists() else ""

    # t2: compute_attribution 函数
    t("attr_compute_fn", "def compute_attribution" in svc_src)

    # t3: AttributionBreakdown dataclass
    t("attr_breakdown", "class AttributionBreakdown" in svc_src)

    # t4: API 文件存在
    api_fp = BACKEND / "app" / "api" / "attribution.py"
    t("attr_api_exists", api_fp.exists(), str(api_fp))

    # t5: main.py 注册
    main_fp = BACKEND / "app" / "main.py"
    main_src = main_fp.read_text(encoding="utf-8") if main_fp.exists() else ""
    t("attr_registered", "attribution" in main_src and "include_router" in main_src)


# ============================================================
# Section 5: Regime Timeline API (5)
# ============================================================
def test_regime_timeline() -> None:
    print("\n=== Section 5: Regime Timeline API (5) ===", flush=True)

    # t1: API 文件存在
    api_fp = BACKEND / "app" / "api" / "regime_timeline.py"
    t("rt_api_exists", api_fp.exists(), str(api_fp))

    api_src = api_fp.read_text(encoding="utf-8") if api_fp.exists() else ""

    # t2: /regime/timeline 路由
    t("rt_route", "/regime/timeline" in api_src)

    # t3: is_transition 字段
    t("rt_is_transition", "is_transition" in api_src)

    # t4: decide_regime 引用
    t("rt_decide_regime", "decide_regime" in api_src)

    # t5: main.py 注册
    main_fp = BACKEND / "app" / "main.py"
    main_src = main_fp.read_text(encoding="utf-8") if main_fp.exists() else ""
    t("rt_registered", "regime_timeline" in main_src and "include_router" in main_src)


# ============================================================
# main
# ============================================================
def main() -> int:
    test_weight_optimizer()
    test_vwma_short()
    test_materialized_view()
    test_attribution()
    test_regime_timeline()

    print(flush=True)
    ok = _passed == _total
    if ok:
        print(f"[m19t2] {_passed}/{_total} ALL PASSED")
    else:
        print(f"[m19t2] {_passed}/{_total} ({_total - _passed} FAILED)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
