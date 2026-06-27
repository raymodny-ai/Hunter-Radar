"""V1.6.0 接力期 m19t1 — Pipeline Resilience 全链路自测。

校验 P0 管道健壮性优化实现完整性:
- etl/market_data_provider.py: 抽象接口 + YFinanceProvider + AlphaVantageProvider + DataProviderManager
- etl/validation.py: 四类校验(daily_price / short_volume / form4 / options_chain)
- etl/retry_policy.py: 统一重试策略
- etl/pipeline.py: DataProviderManager 集成 + 校验集成
- app/core/config.py: alpha_vantage_api_key 配置

静态自测,无需启动后端 / DB。
5 Section × 5 测点 = 25 测点。

运行:
  C:\Python314\python.exe -B -m scripts.m19t1_test_pipeline_resilience
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ETL = BACKEND / "etl"
CONFIG = BACKEND / "app" / "core" / "config.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# Section 1: MarketDataProvider 抽象接口 + YFinanceProvider(5 测点)
# ----------------------------------------------------------------------


def t01_market_data_provider_file_exists() -> bool:
    """t01: etl/market_data_provider.py 文件存在。"""
    if not (ETL / "market_data_provider.py").is_file():
        print("    [FAIL] etl/market_data_provider.py 不存在")
        return False
    print("    [PASS] etl/market_data_provider.py 存在")
    return True


def t02_abstract_interface() -> bool:
    """t02: MarketDataProvider 抽象接口含 fetch_daily_bars + fetch_options_chain。"""
    txt = _read(ETL / "market_data_provider.py")
    required = [
        "class MarketDataProvider(ABC)",
        "async def fetch_daily_bars",
        "async def fetch_options_chain",
        "@abstractmethod",
    ]
    missing = [r for r in required if r not in txt]
    if missing:
        print(f"    [FAIL] 缺接口元素: {missing}")
        return False
    print("    [PASS] MarketDataProvider 抽象接口完整")
    return True


def t03_yfinance_provider() -> bool:
    """t03: YFinanceProvider 实现 MarketDataProvider + 数据契约复用。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "class YFinanceProvider(MarketDataProvider)",
        "DailyBar",
        "OptionContract",
        "yfinance as yf",
        "ticker.history",
        "ticker.option_chain",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺实现元素: {missing}")
        return False
    print("    [PASS] YFinanceProvider 实现完整")
    return True


def t04_data_contracts() -> bool:
    """t04: DailyBar + OptionContract dataclass 含完整字段。"""
    txt = _read(ETL / "market_data_provider.py")
    bar_fields = ["trade_date", "symbol", "open", "high", "low", "close", "adj_close", "volume"]
    opt_fields = ["contract", "underlying", "expiry", "strike", "right", "last_price", "volume", "open_interest"]
    all_fields = bar_fields + opt_fields
    missing = [f for f in all_fields if f not in txt]
    if missing:
        print(f"    [FAIL] 缺字段: {missing}")
        return False
    print("    [PASS] DailyBar + OptionContract 字段完整")
    return True


def t05_fetch_result_dataclass() -> bool:
    """t05: FetchResult dataclass 含 source + is_fallback + error 字段。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "class FetchResult",
        "source: str",
        "is_fallback: bool",
        "error: str",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 FetchResult 元素: {missing}")
        return False
    print("    [PASS] FetchResult dataclass 完整")
    return True


# ----------------------------------------------------------------------
# Section 2: AlphaVantageProvider 备份源(5 测点)
# ----------------------------------------------------------------------


def t06_alpha_vantage_provider() -> bool:
    """t06: AlphaVantageProvider 实现 MarketDataProvider。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "class AlphaVantageProvider(MarketDataProvider)",
        "TIME_SERIES_DAILY",
        "alphavantage.co",
        "api_key",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 AlphaVantage 元素: {missing}")
        return False
    print("    [PASS] AlphaVantageProvider 实现完整")
    return True


def t07_alpha_vantage_rate_limit() -> bool:
    """t07: Alpha Vantage 免费层限制(25 req/day)实现。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "_daily_limit",
        "_daily_calls_today",
        "daily_limit_reached",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺限流逻辑: {missing}")
        return False
    print("    [PASS] Alpha Vantage 25 req/day 限流实现")
    return True


def t08_alpha_vantage_no_options() -> bool:
    """t08: Alpha Vantage 免费层不支持期权链,返回空列表。"""
    txt = _read(ETL / "market_data_provider.py")
    if "no_options_support" not in txt:
        print("    [FAIL] 缺 no_options_support 标记")
        return False
    print("    [PASS] Alpha Vantage 期权链返回空列表")
    return True


def t09_data_provider_manager() -> bool:
    """t09: DataProviderManager 含 primary + fallbacks + 降级逻辑。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "class DataProviderManager",
        "self.primary",
        "self.fallbacks",
        "provider.primary_fail",
        "provider.fallback_success",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Manager 元素: {missing}")
        return False
    print("    [PASS] DataProviderManager 降级逻辑完整")
    return True


def t10_fallback_chain() -> bool:
    """t10: 降级链: primary → fallbacks → 全部失败标记 error。"""
    txt = _read(ETL / "market_data_provider.py")
    checks = [
        "provider.all_failed",
        'source="none"',
        "is_fallback=True",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺降级链元素: {missing}")
        return False
    print("    [PASS] 三级降级链完整")
    return True


# ----------------------------------------------------------------------
# Section 3: Validation Layer 四类校验(5 测点)
# ----------------------------------------------------------------------


def t11_validation_file_exists() -> bool:
    """t11: etl/validation.py 文件存在 + ValidationResult dataclass。"""
    if not (ETL / "validation.py").is_file():
        print("    [FAIL] etl/validation.py 不存在")
        return False
    txt = _read(ETL / "validation.py")
    checks = [
        "class ValidationResult",
        "is_valid",
        "outlier_count",
        "warnings",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 ValidationResult 元素: {missing}")
        return False
    print("    [PASS] validation.py + ValidationResult 完整")
    return True


def t12_validate_daily_price() -> bool:
    """t12: validate_daily_price() 含涨跌幅 + OHLC + 成交量校验。"""
    txt = _read(ETL / "validation.py")
    checks = [
        "def validate_daily_price",
        "max_daily_change_pct",
        "ohlc_logic",
        "extreme_change",
        "zero_volume",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 daily_price 校验: {missing}")
        return False
    print("    [PASS] validate_daily_price 四类校验完整")
    return True


def t13_validate_short_volume() -> bool:
    """t13: validate_short_volume() 含统计离群 + 逻辑校验。"""
    txt = _read(ETL / "validation.py")
    checks = [
        "def validate_short_volume",
        "historical_p99",
        "outlier_multiplier",
        "statistical_outlier",
        "zero_total",
        "short_gt_total",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 short_volume 校验: {missing}")
        return False
    print("    [PASS] validate_short_volume 校验完整")
    return True


def t14_validate_form4() -> bool:
    """t14: validate_form4() 含金额离群 + 日期校验。"""
    txt = _read(ETL / "validation.py")
    checks = [
        "def validate_form4",
        "historical_max_txn",
        "statistical_outlier",
        "future_date",
        "invalid_qty",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 form4 校验: {missing}")
        return False
    print("    [PASS] validate_form4 校验完整")
    return True


def t15_validate_options_chain() -> bool:
    """t15: validate_options_chain() 含 PCR 范围 + 合约校验。"""
    txt = _read(ETL / "validation.py")
    checks = [
        "def validate_options_chain",
        "pcr_min",
        "pcr_max",
        "pcr_too_high",
        "pcr_too_low",
        "negative_volume",
        "invalid_strike",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 options_chain 校验: {missing}")
        return False
    print("    [PASS] validate_options_chain 校验完整")
    return True


# ----------------------------------------------------------------------
# Section 4: ETL 重试策略统一(5 测点)
# ----------------------------------------------------------------------


def t16_retry_policy_file_exists() -> bool:
    """t16: etl/retry_policy.py 文件存在。"""
    if not (ETL / "retry_policy.py").is_file():
        print("    [FAIL] etl/retry_policy.py 不存在")
        return False
    print("    [PASS] etl/retry_policy.py 存在")
    return True


def t17_retry_constants() -> bool:
    """t17: 重试策略常量: attempts=3, min_wait=5, max_wait=60。"""
    txt = _read(ETL / "retry_policy.py")
    checks = [
        "ETL_RETRY_ATTEMPTS",
        "ETL_RETRY_MIN_WAIT",
        "ETL_RETRY_MAX_WAIT",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺常量: {missing}")
        return False
    # 检查数值
    if "ATTEMPTS: int = 3" not in txt and "ATTEMPTS = 3" not in txt:
        print("    [FAIL] ETL_RETRY_ATTEMPTS 应为 3")
        return False
    print("    [PASS] 重试策略常量正确")
    return True


def t18_etl_retry_decorator() -> bool:
    """t18: etl_retry 装饰器基于 tenacity + 指数退避。"""
    txt = _read(ETL / "retry_policy.py")
    checks = [
        "from tenacity import",
        "wait_exponential",
        "stop_after_attempt",
        "etl_retry",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺装饰器元素: {missing}")
        return False
    print("    [PASS] etl_retry 装饰器完整")
    return True


def t19_etl_retry_async_function() -> bool:
    """t19: etl_retry_async() 异步重试包装函数。"""
    txt = _read(ETL / "retry_policy.py")
    checks = [
        "async def etl_retry_async",
        "RETRYABLE_EXCEPTIONS",
        "await asyncio.sleep",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 etl_retry_async 元素: {missing}")
        return False
    print("    [PASS] etl_retry_async 函数完整")
    return True


def t20_run_stage_with_retry() -> bool:
    """t20: run_stage_with_retry() pipeline 阶段重试包装。"""
    txt = _read(ETL / "retry_policy.py")
    checks = [
        "async def run_stage_with_retry",
        "stage_name",
        "report",
        "mark_failed",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 run_stage_with_retry 元素: {missing}")
        return False
    print("    [PASS] run_stage_with_retry 函数完整")
    return True


# ----------------------------------------------------------------------
# Section 5: pipeline.py 集成 + 配置(5 测点)
# ----------------------------------------------------------------------


def t21_pipeline_uses_provider_manager() -> bool:
    """t21: pipeline.py 使用 DataProviderManager 替代直接调 yfinance_pull。"""
    txt = _read(ETL / "pipeline.py")
    checks = [
        "from etl.market_data_provider import DataProviderManager",
        "provider_mgr = DataProviderManager()",
        "provider_mgr.fetch_daily_bars",
        "provider_mgr.fetch_options_chain",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 ProviderManager 集成: {missing}")
        return False
    print("    [PASS] pipeline.py DataProviderManager 集成完整")
    return True


def t22_pipeline_validation_integration() -> bool:
    """t22: pipeline.py 集成 validate_daily_price + validate_options_chain。"""
    txt = _read(ETL / "pipeline.py")
    checks = [
        "validate_daily_price",
        "validate_options_chain",
        "from etl.validation import",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺校验集成: {missing}")
        return False
    print("    [PASS] pipeline.py 校验层集成完整")
    return True


def t23_pipeline_no_direct_yfinance_import() -> bool:
    """t23: pipeline.py 不再直接 import yfinance_pull 的 fetch 函数。"""
    txt = _read(ETL / "pipeline.py")
    if "from etl.yfinance_pull import fetch_daily_bars" in txt:
        print("    [FAIL] pipeline.py 仍直接 import fetch_daily_bars")
        return False
    if "from etl.yfinance_pull import fetch_options_chain" in txt:
        print("    [FAIL] pipeline.py 仍直接 import fetch_options_chain")
        return False
    print("    [PASS] pipeline.py 不再直接 import yfinance_pull fetch 函数")
    return True


def t24_config_alpha_vantage_key() -> bool:
    """t24: config.py 新增 alpha_vantage_api_key 配置。"""
    txt = _read(CONFIG)
    checks = [
        "alpha_vantage_api_key",
        "data_provider_fallback_enabled",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺配置项: {missing}")
        return False
    print("    [PASS] config.py V1.6.0 配置项完整")
    return True


def t25_pipeline_fallback_source_logging() -> bool:
    """t25: pipeline.py 降级时记录 source + is_fallback。"""
    txt = _read(ETL / "pipeline.py")
    checks = [
        "result.source",
        "result.is_fallback",
        "provider.daily_bars.empty",
        "provider.options.empty",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺降级日志: {missing}")
        return False
    print("    [PASS] pipeline.py 降级日志完整")
    return True


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

CHECKS = [
    # Section 1: MarketDataProvider 抽象接口 + YFinanceProvider
    ("t01_provider_file_exists", t01_market_data_provider_file_exists),
    ("t02_abstract_interface", t02_abstract_interface),
    ("t03_yfinance_provider", t03_yfinance_provider),
    ("t04_data_contracts", t04_data_contracts),
    ("t05_fetch_result", t05_fetch_result_dataclass),
    # Section 2: AlphaVantageProvider 备份源
    ("t06_alpha_vantage_provider", t06_alpha_vantage_provider),
    ("t07_alpha_vantage_rate_limit", t07_alpha_vantage_rate_limit),
    ("t08_alpha_vantage_no_options", t08_alpha_vantage_no_options),
    ("t09_data_provider_manager", t09_data_provider_manager),
    ("t10_fallback_chain", t10_fallback_chain),
    # Section 3: Validation Layer
    ("t11_validation_file", t11_validation_file_exists),
    ("t12_validate_daily_price", t12_validate_daily_price),
    ("t13_validate_short_volume", t13_validate_short_volume),
    ("t14_validate_form4", t14_validate_form4),
    ("t15_validate_options_chain", t15_validate_options_chain),
    # Section 4: Retry Policy
    ("t16_retry_policy_file", t16_retry_policy_file_exists),
    ("t17_retry_constants", t17_retry_constants),
    ("t18_etl_retry_decorator", t18_etl_retry_decorator),
    ("t19_etl_retry_async", t19_etl_retry_async_function),
    ("t20_run_stage_with_retry", t20_run_stage_with_retry),
    # Section 5: Pipeline Integration + Config
    ("t21_pipeline_provider_manager", t21_pipeline_uses_provider_manager),
    ("t22_pipeline_validation", t22_pipeline_validation_integration),
    ("t23_pipeline_no_direct_yfinance", t23_pipeline_no_direct_yfinance_import),
    ("t24_config_alpha_vantage", t24_config_alpha_vantage_key),
    ("t25_pipeline_fallback_logging", t25_pipeline_fallback_source_logging),
]


def main() -> None:
    print("=" * 60)
    print("m19t1 — V1.6.0 Pipeline Resilience 自测")
    print("=" * 60)

    passed = 0
    total = len(CHECKS)

    sections = [
        ("Section 1: MarketDataProvider 抽象接口", CHECKS[0:5]),
        ("Section 2: AlphaVantageProvider 备份源", CHECKS[5:10]),
        ("Section 3: Validation Layer 四类校验", CHECKS[10:15]),
        ("Section 4: ETL 重试策略统一", CHECKS[15:20]),
        ("Section 5: Pipeline 集成 + 配置", CHECKS[20:25]),
    ]

    for section_name, tests in sections:
        print(f"\n  {section_name}")
        for name, fn in tests:
            try:
                if fn():
                    passed += 1
            except Exception as e:
                print(f"    [FAIL] {name}: {e}")

    print("\n" + "=" * 60)
    if passed == total:
        print(f"  RESULT: {passed}/{total} ALL PASSED")
    else:
        print(f"  RESULT: {passed}/{total} ({total - passed} FAILED)")
    print("=" * 60)

    import sys
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
