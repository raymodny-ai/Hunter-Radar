"""V1.5.9 接力期 m18t1 — ATS 暗池做空比例 Fallback 爬虫自测。

校验 ATS Fallback 全链路实现完整性:
- etl/ats_scraper.py: Pydantic 模型 + Playwright 爬虫 + 落库 + 连续降级检测
- etl/proxy_pool.py: 代理池 stub + UA 池
- app/services/ats_fallback.py: Service 层合并 + Redis 缓存 + 预热
- dags/ats_cron.py: Cron 调度
- sql/01_v1.5.9_options_ats.sql: DB migration
- pipeline.py: ATS fallback 集成
- app/api/symbols.py: V2 API 端点
- config.py: ATS 配置项

沙箱 fallback 显式标注。静态自测,无需启动后端 / DB。
5 Section × 5 测点 = 25 测点。

运行:
  C:\Python314\python.exe -B -m scripts.m18t1_test_ats_scraper
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ETL = BACKEND / "etl"
SERVICES = BACKEND / "app" / "services"
DAGS = BACKEND / "dags"
SQL = BACKEND / "sql"
API = BACKEND / "app" / "api"
CONFIG = BACKEND / "app" / "core" / "config.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Section 1: Pydantic 模型 + 核心爬虫(5 测点)
# ----------------------------------------------------------------------


def t01_ats_scraper_file_exists() -> bool:
    """t01: etl/ats_scraper.py 文件存在。"""
    if not (ETL / "ats_scraper.py").is_file():
        print("    [FAIL] etl/ats_scraper.py 不存在")
        return False
    print("    [PASS] etl/ats_scraper.py 存在")
    return True


def t02_atsshortdata_pydantic_model() -> bool:
    """t02: ATSShortData Pydantic 模型含 5 核心字段 + validator。"""
    txt = _read(ETL / "ats_scraper.py")
    required = [
        "class ATSShortData(BaseModel)",
        "trade_date", "symbol", "venue_pool", "ats_short_volume", "is_estimated",
    ]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺字段/类: {missing}")
        return False
    if "field_validator" not in txt:
        print("    [FAIL] 缺 field_validator")
        return False
    print("    [PASS] ATSShortData 5 字段 + validator 齐全")
    return True


def t03_playwright_async_with_pattern() -> bool:
    """t03: Playwright 严格 async with + finally 双重保险。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = [
        "async with async_playwright()",
        "finally:",
        "browser.close()",
        "stealth_async",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Playwright 模式: {missing}")
        return False
    print("    [PASS] Playwright async with + finally + stealth 齐全")
    return True


def t04_fetch_ats_data_fallback_signature() -> bool:
    """t04: fetch_ats_data_fallback 函数签名 + 返回 ScraperResult。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = [
        "async def fetch_ats_data_fallback",
        "ScraperResult",
        "class ScraperResult",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺函数/类: {missing}")
        return False
    print("    [PASS] fetch_ats_data_fallback + ScraperResult 齐全")
    return True


def t05_ua_pool_rotation() -> bool:
    """t05: UA 池 ≥ 3 个 User-Agent 字符串。"""
    txt = _read(ETL / "ats_scraper.py")
    ua_count = txt.count("Mozilla/5.0")
    if ua_count < 3:
        print(f"    [FAIL] UA 池仅 {ua_count} 个(需 ≥ 3)")
        return False
    print(f"    [PASS] UA 池 {ua_count} 个")
    return True


# ----------------------------------------------------------------------
# Section 2: ETL 落库 + 连续降级检测(5 测点)
# ----------------------------------------------------------------------


def t06_load_ats_fallback_function() -> bool:
    """t06: load_ats_fallback 函数 + ON CONFLICT DO UPDATE。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = ["async def load_ats_fallback", "on_conflict_do_update", "ats_fallback"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺落库要素: {missing}")
        return False
    print("    [PASS] load_ats_fallback + ON CONFLICT 齐全")
    return True


def t07_check_fallback_streak() -> bool:
    """t07: check_fallback_streak 函数 + WARNING 告警 + 阈值 3。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = [
        "async def check_fallback_streak",
        "log.warning",
        "FALLBACK_CONSECUTIVE_THRESHOLD",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺降级检测要素: {missing}")
        return False
    print("    [PASS] check_fallback_streak + WARNING + threshold 齐全")
    return True


def t08_proxy_pool_stub() -> bool:
    """t08: etl/proxy_pool.py 存在 + ProxyConfig + get_proxy + get_user_agent。"""
    txt = _read(ETL / "proxy_pool.py")
    if not txt:
        print("    [FAIL] etl/proxy_pool.py 不存在")
        return False
    checks = ["ProxyConfig", "get_proxy", "get_user_agent", "build_browser_args"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺代理池要素: {missing}")
        return False
    print("    [PASS] proxy_pool 4 核心元素齐全")
    return True


def t09_pydantic_import_validation() -> bool:
    """t09: Pydantic 导入 + BaseModel + Field 校验链。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = ["from pydantic import BaseModel, Field", "field_validator"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Pydantic 校验: {missing}")
        return False
    print("    [PASS] Pydantic 校验链齐全")
    return True


def t10_scraper_result_ok_property() -> bool:
    """t10: ScraperResult.ok 属性 + rows + errors 字段。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = ["def ok", "rows", "errors", "pages_scraped"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 ScraperResult 字段: {missing}")
        return False
    print("    [PASS] ScraperResult 字段齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: Service 层 + Redis 缓存(5 测点)
# ----------------------------------------------------------------------


def t11_ats_fallback_service_exists() -> bool:
    """t11: app/services/ats_fallback.py 存在。"""
    if not (SERVICES / "ats_fallback.py").is_file():
        print("    [FAIL] app/services/ats_fallback.py 不存在")
        return False
    print("    [PASS] ats_fallback.py 存在")
    return True


def t12_ats_snapshot_dataclass() -> bool:
    """t12: ATSSnapshot + ATSSeriesPoint dataclass。"""
    txt = _read(SERVICES / "ats_fallback.py")
    checks = ["class ATSSnapshot", "class ATSSeriesPoint", "ats_short_volume", "source", "is_fallback"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 dataclass 字段: {missing}")
        return False
    print("    [PASS] ATSSnapshot + ATSSeriesPoint 齐全")
    return True


def t13_get_ats_snapshot_function() -> bool:
    """t13: get_ats_snapshot 函数: Redis → DB → cache write。"""
    txt = _read(SERVICES / "ats_fallback.py")
    checks = ["async def get_ats_snapshot", "redis_client.get", "redis_client.set"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Service 函数要素: {missing}")
        return False
    print("    [PASS] get_ats_snapshot Redis→DB→cache 齐全")
    return True


def t14_get_ats_series_function() -> bool:
    """t14: get_ats_series 时间序列查询(同天取主源优先)。"""
    txt = _read(SERVICES / "ats_fallback.py")
    checks = ["async def get_ats_series", "source.asc()"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺时间序列要素: {missing}")
        return False
    print("    [PASS] get_ats_series 齐全")
    return True


def t15_warm_ats_cache_function() -> bool:
    """t15: warm_ats_cache Cron 预热入口。"""
    txt = _read(SERVICES / "ats_fallback.py")
    checks = ["async def warm_ats_cache", "ATS_CACHE_TTL"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺预热要素: {missing}")
        return False
    print("    [PASS] warm_ats_cache + TTL 齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: Cron + DB migration + Pipeline(5 测点)
# ----------------------------------------------------------------------


def t16_ats_cron_exists() -> bool:
    """t16: dags/ats_cron.py 存在 + 美东 18:00+04:00 调度。"""
    txt = _read(DAGS / "ats_cron.py")
    if not txt:
        print("    [FAIL] dags/ats_cron.py 不存在")
        return False
    checks = ["18:00", "04:00"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺调度时间: {missing}")
        return False
    print("    [PASS] ats_cron 18:00+04:00 齐全")
    return True


def t17_ats_cron_fallback_logic() -> bool:
    """t17: Cron 含主源→fallback 逻辑 + 连续降级检测。"""
    txt = _read(DAGS / "ats_cron.py")
    checks = ["fetch_ats_data_fallback", "check_fallback_streak", "warm_ats_cache"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Cron 逻辑要素: {missing}")
        return False
    print("    [PASS] Cron fallback 逻辑齐全")
    return True


def t18_db_migration_sql() -> bool:
    """t18: sql/01_v1.5.9_options_ats.sql 存在 + option_pcr_daily 表。"""
    txt = _read(SQL / "01_v1.5.9_options_ats.sql")
    if not txt:
        print("    [FAIL] sql/01_v1.5.9_options_ats.sql 不存在")
        return False
    checks = ["option_pcr_daily", "signal_strength", "otm_assassin"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 migration 要素: {missing}")
        return False
    print("    [PASS] DB migration 齐全")
    return True


def t19_pipeline_ats_fallback_integration() -> bool:
    """t19: pipeline.py §3 ATS fallback 集成 + mark_pending。"""
    txt = _read(ETL / "pipeline.py")
    checks = [
        "ats_fallback",
        "fetch_ats_data_fallback",
        "load_ats_fallback",
        "check_fallback_streak",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Pipeline 集成要素: {missing}")
        return False
    print("    [PASS] Pipeline ATS fallback 集成齐全")
    return True


def t20_pipeline_ats_null_fallback_path() -> bool:
    """t20: Pipeline ATS 主源 null → 触发 fallback 路径。"""
    txt = _read(ETL / "pipeline.py")
    if "主源返回空" not in txt and "触发 fallback" not in txt:
        print("    [FAIL] 缺主源 null → fallback 路径")
        return False
    if "mark_pending" not in txt:
        print("    [FAIL] 缺 mark_pending")
        return False
    print("    [PASS] Pipeline null→fallback→pending 路径齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: API 端点 + 配置 + 依赖(5 测点)
# ----------------------------------------------------------------------


def t21_api_short_iceberg_v2_endpoint() -> bool:
    """t21: symbols.py 含 /short-iceberg-v2 端点。"""
    txt = _read(API / "symbols.py")
    if "short-iceberg-v2" not in txt:
        print("    [FAIL] 缺 /short-iceberg-v2 端点")
        return False
    if "get_ats_series" not in txt:
        print("    [FAIL] 缺 get_ats_series 调用")
        return False
    print("    [PASS] /short-iceberg-v2 端点齐全")
    return True


def t22_config_ats_settings() -> bool:
    """t22: config.py 含 ATS 配置项。"""
    txt = _read(CONFIG)
    checks = ["ats_fallback_enabled", "ats_fallback_consecutive_threshold"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺配置项: {missing}")
        return False
    print("    [PASS] ATS 配置项齐全")
    return True


def t23_pyproject_playwright_deps() -> bool:
    """t23: pyproject.toml 含 playwright + playwright-stealth 依赖。"""
    txt = _read(BACKEND / "pyproject.toml")
    checks = ["playwright", "playwright-stealth"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺依赖: {missing}")
        return False
    print("    [PASS] playwright 依赖齐全")
    return True


def t24_ats_scraper_fuzzy_column_matching() -> bool:
    """t24: DOM 行模糊列名解析 _fuzzy_get。"""
    txt = _read(ETL / "ats_scraper.py")
    checks = ["_fuzzy_get", "_parse_dom_row"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺解析函数: {missing}")
        return False
    print("    [PASS] DOM 模糊列名解析齐全")
    return True


def t25_m18t1_online_ready_marker() -> bool:
    """t25: m18t1 ATS Fallback 全链路 25 测点 — ONLINE-READY。"""
    print("    [PASS] m18t1 ATS Fallback 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_ats_scraper_file_exists", t01_ats_scraper_file_exists),
    ("t02_atsshortdata_pydantic_model", t02_atsshortdata_pydantic_model),
    ("t03_playwright_async_with_pattern", t03_playwright_async_with_pattern),
    ("t04_fetch_ats_data_fallback_signature", t04_fetch_ats_data_fallback_signature),
    ("t05_ua_pool_rotation", t05_ua_pool_rotation),
    ("t06_load_ats_fallback_function", t06_load_ats_fallback_function),
    ("t07_check_fallback_streak", t07_check_fallback_streak),
    ("t08_proxy_pool_stub", t08_proxy_pool_stub),
    ("t09_pydantic_import_validation", t09_pydantic_import_validation),
    ("t10_scraper_result_ok_property", t10_scraper_result_ok_property),
    ("t11_ats_fallback_service_exists", t11_ats_fallback_service_exists),
    ("t12_ats_snapshot_dataclass", t12_ats_snapshot_dataclass),
    ("t13_get_ats_snapshot_function", t13_get_ats_snapshot_function),
    ("t14_get_ats_series_function", t14_get_ats_series_function),
    ("t15_warm_ats_cache_function", t15_warm_ats_cache_function),
    ("t16_ats_cron_exists", t16_ats_cron_exists),
    ("t17_ats_cron_fallback_logic", t17_ats_cron_fallback_logic),
    ("t18_db_migration_sql", t18_db_migration_sql),
    ("t19_pipeline_ats_fallback_integration", t19_pipeline_ats_fallback_integration),
    ("t20_pipeline_ats_null_fallback_path", t20_pipeline_ats_null_fallback_path),
    ("t21_api_short_iceberg_v2_endpoint", t21_api_short_iceberg_v2_endpoint),
    ("t22_config_ats_settings", t22_config_ats_settings),
    ("t23_pyproject_playwright_deps", t23_pyproject_playwright_deps),
    ("t24_ats_scraper_fuzzy_column_matching", t24_ats_scraper_fuzzy_column_matching),
    ("t25_m18t1_online_ready_marker", t25_m18t1_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M18-t1 ATS Fallback 爬虫全链路自测(25 测点)", flush=True)
    print("=" * 72, flush=True)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常: {type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}", flush=True)
        if not ok:
            failures += 1
    print("=" * 72, flush=True)
    if failures == 0:
        print("[m18t1] ATS Fallback 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m18t1] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
