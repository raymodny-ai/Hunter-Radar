"""m19t6 V1.6.0 Handoff 文档完整性验证(25 测点)。

Section 1: Handoff 文档结构 (5)
Section 2: Task 清单完整性 (5)
Section 3: 新建文件验证 (5)
Section 4: 修改文件验证 (5)
Section 5: m8t1 回归 + ONLINE-READY (5)

静态分析。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DOCS = ROOT / "docs"

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
# Section 1: Handoff 文档结构 (5)
# ============================================================
def test_handoff_structure() -> None:
    print("\n=== Section 1: Handoff 文档结构 (5) ===", flush=True)
    fp = DOCS / "V1.6.0-handoff.md"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: 文档存在
    t("ho_file_exists", fp.exists(), str(fp))

    # t2: 概述章节
    t("ho_section_overview", "## 1." in src and "概述" in src)

    # t3: Task 清单章节
    t("ho_section_tasks", "## 2." in src and "Task" in src)

    # t4: 变更文件章节
    t("ho_section_changes", "## 4." in src and "变更文件" in src)

    # t5: ONLINE-READY 结论
    t("ho_section_conclusion", "ONLINE-READY" in src and "结论" in src)


# ============================================================
# Section 2: Task 清单完整性 (5)
# ============================================================
def test_task_list() -> None:
    print("\n=== Section 2: Task 清单完整性 (5) ===", flush=True)
    fp = DOCS / "V1.6.0-handoff.md"
    src = fp.read_text(encoding="utf-8") if fp.exists() else ""

    # t1: P0 tasks
    t("ho_p0_tasks", "多源冗余" in src and "校验层" in src and "重试" in src)

    # t2: P1 tasks
    t("ho_p1_tasks", "ML 动态权重" in src and "VWMA" in src and "物化视图" in src)

    # t3: Attribution + Timeline
    t("ho_attr_timeline", "归因" in src and "时间轴" in src)

    # t4: P2 tasks
    t("ho_p2_tasks", "RAG" in src and "Docker" in src)

    # t5: 收尾 tasks
    t("ho_closing_tasks", "m8t1" in src and "handoff" in src.lower() and "Git" in src)


# ============================================================
# Section 3: 新建文件验证 (5)
# ============================================================
def test_new_files() -> None:
    print("\n=== Section 3: 新建文件验证 (5) ===", flush=True)

    # t1: 核心 ETL 新文件
    files = [
        BACKEND / "etl" / "market_data_provider.py",
        BACKEND / "etl" / "validation.py",
        BACKEND / "etl" / "retry_policy.py",
    ]
    t("new_etl_files", all(f.exists() for f in files))

    # t2: 服务层新文件
    svc_files = [
        BACKEND / "app" / "services" / "weight_optimizer.py",
        BACKEND / "app" / "services" / "attribution.py",
        BACKEND / "app" / "services" / "rag_knowledge_base.py",
    ]
    t("new_svc_files", all(f.exists() for f in svc_files))

    # t3: API 层新文件
    api_files = [
        BACKEND / "app" / "api" / "attribution.py",
        BACKEND / "app" / "api" / "regime_timeline.py",
    ]
    t("new_api_files", all(f.exists() for f in api_files))

    # t4: SQL 新文件
    sql_files = [
        BACKEND / "sql" / "02_v1.6.0_materialized_views.sql",
        BACKEND / "sql" / "03_v1.6.0_rag.sql",
    ]
    t("new_sql_files", all(f.exists() for f in sql_files))

    # t5: Docker 新文件
    docker_files = [
        BACKEND / "Dockerfile",
        BACKEND / ".dockerignore",
        ROOT / "docker" / "control.sh",
    ]
    t("new_docker_files", all(f.exists() for f in docker_files))


# ============================================================
# Section 4: 修改文件验证 (5)
# ============================================================
def test_modified_files() -> None:
    print("\n=== Section 4: 修改文件验证 (5) ===", flush=True)

    # t1: config.py 新配置
    cfg = BACKEND / "app" / "core" / "config.py"
    cfg_src = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    t("mod_config", "alpha_vantage_api_key" in cfg_src or "data_provider_fallback" in cfg_src)

    # t2: pipeline.py 集成
    pipe = BACKEND / "etl" / "pipeline.py"
    pipe_src = pipe.read_text(encoding="utf-8") if pipe.exists() else ""
    t("mod_pipeline", "DataProviderManager" in pipe_src and "validate_daily_price" in pipe_src)

    # t3: screener.py MV
    scr = BACKEND / "app" / "api" / "screener.py"
    scr_src = scr.read_text(encoding="utf-8") if scr.exists() else ""
    t("mod_screener", "mv_screener_top100" in scr_src)

    # t4: short_metrics.py VWMA
    sm = BACKEND / "app" / "services" / "short_metrics.py"
    sm_src = sm.read_text(encoding="utf-8") if sm.exists() else ""
    t("mod_short_metrics", "compute_vwma_short_ratio" in sm_src)

    # t5: llm.py RAG
    llm = BACKEND / "app" / "api" / "llm.py"
    llm_src = llm.read_text(encoding="utf-8") if llm.exists() else ""
    t("mod_llm", "rag_knowledge_base" in llm_src or "get_rag_context" in llm_src)


# ============================================================
# Section 5: m8t1 回归 + ONLINE-READY (5)
# ============================================================
def test_regression() -> None:
    print("\n=== Section 5: m8t1 回归 + ONLINE-READY (5) ===", flush=True)

    # t1: m8t1 包含 M19
    m8t1 = BACKEND / "scripts" / "m8t1_test_regression.py"
    m8t1_src = m8t1.read_text(encoding="utf-8") if m8t1.exists() else ""
    t("reg_m19_included", "M19_SCRIPTS" in m8t1_src)

    # t2: m8t1 包含 m19t1~m19t5
    t("reg_m19_scripts", all(
        f"m19t{i}" in m8t1_src for i in range(1, 6)
    ))

    # t3: 73 脚本
    t("reg_73_scripts", "73" in m8t1_src or "73 个脚本" in m8t1_src)

    # t4: 1602 测点
    t("reg_1602_tp", "1602" in m8t1_src or "1,602" in m8t1_src)

    # t5: V1.6.0 ONLINE-READY
    t("reg_v160_ready", "V1.6.0-ONLINE-READY" in m8t1_src or "V1.6.0 ONLINE-READY" in m8t1_src)


# ============================================================
# main
# ============================================================
def main() -> int:
    test_handoff_structure()
    test_task_list()
    test_new_files()
    test_modified_files()
    test_regression()

    print(flush=True)
    ok = _passed == _total
    if ok:
        print(f"[m19t6] {_passed}/{_total} ALL PASSED")
    else:
        print(f"[m19t6] {_passed}/{_total} ({_total - _passed} FAILED)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
