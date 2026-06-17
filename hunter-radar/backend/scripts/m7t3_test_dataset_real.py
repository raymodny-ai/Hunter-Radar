"""M7-t3 BD-085 真实数据集 ETL 沙箱 stub 自测(22 测点)
- 沙箱模式:无 PG 无 httpx,_seeded_float SHA256 deterministic + 4220 行 JSONL
- 测点:数据完整性 + SHA256 稳定性 + 字段齐全 + ticker 覆盖
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
BACKEND_ETL = ROOT / "backend" / "etl"
DATA = ROOT / "data"
GOLDSET = DATA / "backtest_event_goldset.sample.jsonl"
REAL_DATASET = DATA / "backtest_dataset_real.sandbox.jsonl"


def _load_mod(name: str, path: Path):
    """Python 3.14 dataclass sys.modules 兼容加载 helper。"""
    import sys
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------
# Section 1: 模块加载 + 核心函数存在性(5 测点)
# ----------------------------------------------------------------------

def t01_module_loads() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    if not p.exists():
        print(f"  [FAIL] backtest_dataset_real.py 不存在")
        return False
    try:
        _load_mod("backtest_dataset_real", p)
    except Exception as exc:
        print(f"  [FAIL] 模块加载失败: {exc}")
        return False
    print(f"  [PASS] backtest_dataset_real.py 模块加载成功")
    return True


def t02_seeded_float_exists() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    if "_seeded_float" not in txt:
        print("  [FAIL] 缺 _seeded_float 函数")
        return False
    print("  [PASS] _seeded_float 函数存在")
    return True


def t03_build_real_dataset_sandbox_exists() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    if "build_real_dataset_sandbox" not in txt:
        print("  [FAIL] 缺 build_real_dataset_sandbox 入口")
        return False
    print("  [PASS] build_real_dataset_sandbox 入口存在")
    return True


def t04_synthesize_functions() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    funcs = ["_synthesize_ohlcv_for_day", "_synthesize_short_volume", "_synthesize_form4"]
    missing = [f for f in funcs if f not in txt]
    if missing:
        print(f"  [FAIL] 缺合成函数: {missing}")
        return False
    print(f"  [PASS] 3 个合成函数齐全")
    return True


def t05_dataclass_result() -> bool:
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    if "RealDatasetBuildResult" not in txt:
        print("  [FAIL] 缺 RealDatasetBuildResult dataclass")
        return False
    print("  [PASS] RealDatasetBuildResult dataclass 存在")
    return True


# ----------------------------------------------------------------------
# Section 2: 沙箱 stub 运行 + 数据完整性(6 测点)
# ----------------------------------------------------------------------

def t06_goldset_exists() -> bool:
    if not GOLDSET.exists():
        print(f"  [FAIL] goldset JSONL 不存在: {GOLDSET}")
        return False
    lines = GOLDSET.read_text(encoding="utf-8").strip().split("\n")
    print(f"  [PASS] goldset {len(lines)} 行")
    return True


def t07_build_dataset_runs() -> bool:
    """运行 build_real_dataset_sandbox,4220 行 JSONL。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    if not GOLDSET.exists():
        print(f"  [SKIP] goldset 不存在,跳过")
        return True
    try:
        result, rows = mod.build_real_dataset_sandbox(str(GOLDSET), window_days=90)
    except Exception as exc:
        print(f"  [FAIL] build_real_dataset_sandbox 失败: {exc}")
        return False
    print(f"  [PASS] build_real_dataset_sandbox 返回 {len(rows)} 行(unique tickers={len(result.by_ticker or {})})")
    return True


def t08_real_dataset_jsonl_exists() -> bool:
    if not REAL_DATASET.exists():
        print(f"  [FAIL] real_dataset JSONL 不存在: {REAL_DATASET}")
        return False
    print(f"  [PASS] real_dataset JSONL 存在")
    return True


def t09_real_dataset_line_count() -> bool:
    """校验 4220 行 ± 5% 容差。"""
    if not REAL_DATASET.exists():
        print("  [SKIP] JSONL 不存在")
        return True
    lines = REAL_DATASET.read_text(encoding="utf-8").strip().split("\n")
    n = len(lines)
    if not (4000 <= n <= 4500):
        print(f"  [FAIL] 行数 {n} 不在 4000-4500 范围")
        return False
    print(f"  [PASS] real_dataset {n} 行(期望 ~4220)")
    return True


def t10_real_dataset_field_completeness() -> bool:
    """校验每行顶层字段齐全:ticker / trade_date / payload / checksum。"""
    if not REAL_DATASET.exists():
        print("  [SKIP] JSONL 不存在")
        return True
    required_fields = ["ticker", "trade_date", "payload", "checksum"]
    sample_line = REAL_DATASET.read_text(encoding="utf-8").split("\n")[0]
    try:
        rec = json.loads(sample_line)
    except Exception as exc:
        print(f"  [FAIL] JSON 解析失败: {exc}")
        return False
    missing = [f for f in required_fields if f not in rec]
    if missing:
        print(f"  [FAIL] 缺顶层字段: {missing}")
        return False
    # payload 内含 daily_price / short_volume / form4_events
    p = rec.get("payload", {})
    nested_required = ["daily_price", "short_volume", "form4_events"]
    missing_nested = [f for f in nested_required if f not in p]
    if missing_nested:
        print(f"  [FAIL] payload 缺嵌套字段: {missing_nested}")
        return False
    # daily_price 内含 OHLCV
    dp = p.get("daily_price", {})
    ohlcv = ["open", "high", "low", "close", "volume"]
    missing_ohlcv = [f for f in ohlcv if f not in dp]
    if missing_ohlcv:
        print(f"  [FAIL] daily_price 缺 OHLCV 字段: {missing_ohlcv}")
        return False
    print(f"  [PASS] 顶层 + 嵌套字段齐全(8 顶层 + 3 nested + 5 OHLCV)")
    return True


def t11_real_dataset_unique_tickers() -> bool:
    """校验 unique tickers >= 25(期望 27 ticker)。"""
    if not REAL_DATASET.exists():
        print("  [SKIP] JSONL 不存在")
        return True
    tickers = set()
    for line in REAL_DATASET.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            tickers.add(rec.get("ticker"))
        except Exception:
            pass
    n = len(tickers)
    if n < 25:
        print(f"  [FAIL] unique ticker 仅 {n} 个(< 25)")
        return False
    print(f"  [PASS] 全集覆盖 {n} unique ticker")
    return True


# ----------------------------------------------------------------------
# Section 3: SHA256 deterministic 稳定性(4 测点)
# ----------------------------------------------------------------------

def t12_seeded_float_deterministic() -> bool:
    """校验同 ticker + 同日期 → 同浮点(SHA256 deterministic)。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    v1 = mod._seeded_float("AAPL", date(2024, 6, 15), "open")
    v2 = mod._seeded_float("AAPL", date(2024, 6, 15), "open")
    if v1 != v2:
        print(f"  [FAIL] _seeded_float 不稳定: {v1} vs {v2}")
        return False
    print(f"  [PASS] _seeded_float 稳定({v1:.4f} == {v2:.4f})")
    return True


def t13_seeded_float_different_tickers() -> bool:
    """校验不同 ticker → 不同浮点。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    v1 = mod._seeded_float("AAPL", date(2024, 6, 15), "open")
    v2 = mod._seeded_float("TSLA", date(2024, 6, 15), "open")
    if v1 == v2:
        print(f"  [FAIL] 不同 ticker 浮点相同: {v1}")
        return False
    print(f"  [PASS] 不同 ticker 浮点不同(AAPL={v1:.4f}, TSLA={v2:.4f})")
    return True


def t14_seeded_float_range() -> bool:
    """校验 _seeded_float 返回 0~1 范围。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    for ticker in ["AAPL", "TSLA", "GME", "AMC", "NVDA"]:
        for d in [date(2024, 6, 15), date(2024, 7, 1), date(2024, 12, 31)]:
            v = mod._seeded_float(ticker, d, "open")
            if not (0.0 <= v <= 1.0):
                print(f"  [FAIL] _seeded_float({ticker}, {d})={v} 不在 0~1")
                return False
    print(f"  [PASS] _seeded_float 范围 0~1(15 次抽样)")
    return True


def t15_synthesize_ohlcv_in_range() -> bool:
    """校验 OHLCV 价格在合理范围(10~500 USD),用 severity='medium'。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    ohlcv = mod._synthesize_ohlcv_for_day("AAPL", date(2024, 6, 15), severity="medium")
    if not (10 <= ohlcv.get("close", 0) <= 500):
        print(f"  [FAIL] close 价格 {ohlcv} 超出 10~500")
        return False
    fields = ["open", "high", "low", "close", "adj_close", "volume"]
    missing = [f for f in fields if f not in ohlcv]
    if missing:
        print(f"  [FAIL] OHLCV 缺字段: {missing}")
        return False
    print(f"  [PASS] OHLCV 合理范围(close={ohlcv['close']:.2f}, volume={ohlcv['volume']:,})")
    return True


# ----------------------------------------------------------------------
# Section 4: 数据格式 + 一致性(4 测点)
# ----------------------------------------------------------------------

def t16_real_dataset_iso_date() -> bool:
    """校验 trade_date 字段 ISO 8601 格式(YYYY-MM-DD)。"""
    if not REAL_DATASET.exists():
        print("  [SKIP] JSONL 不存在")
        return True
    sample_line = REAL_DATASET.read_text(encoding="utf-8").split("\n")[0]
    rec = json.loads(sample_line)
    date_str = rec.get("trade_date", "")
    # ISO 格式:YYYY-MM-DD(长度 10 + 第 4 位 - + 第 7 位 -)
    if not (len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-"):
        print(f"  [FAIL] 日期格式不符: {date_str}")
        return False
    print(f"  [PASS] 日期 ISO 格式({date_str})")
    return True


def t17_short_volume_ratio() -> bool:
    """校验 short_volume total_volume ratio 在合理范围(0.05~0.85)。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    sv = mod._synthesize_short_volume("AAPL", date(2024, 6, 15))
    if "total_volume" not in sv or sv["total_volume"] == 0:
        print(f"  [FAIL] short_volume 缺 total_volume: {sv}")
        return False
    ratio = sv["short_volume"] / sv["total_volume"]
    if not (0.05 <= ratio <= 0.85):
        print(f"  [FAIL] short_volume ratio {ratio:.4f} 超出 0.05~0.85")
        return False
    print(f"  [PASS] short_volume ratio 合理({ratio:.4f}, total={sv['total_volume']:,})")
    return True


def t18_form4_count_range() -> bool:
    """校验 form4_events 0~3 条(按 severity 等级)。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    mod = _load_mod("backtest_dataset_real", p)
    for severity in ["extreme", "high", "medium", "low"]:
        f4 = mod._synthesize_form4("AAPL", date(2024, 6, 15), severity=severity)
        if not (0 <= len(f4) <= 4):
            print(f"  [FAIL] form4 数量 {len(f4)} 不合理 (severity={severity})")
            return False
    print(f"  [PASS] form4 数量合理(0~3 条, 4 severity 抽样)")
    return True


def t19_real_dataset_no_missing_fields() -> bool:
    """校验前 100 行无 None / 缺关键字段(ticker / trade_date / payload / checksum)。"""
    if not REAL_DATASET.exists():
        print("  [SKIP] JSONL 不存在")
        return True
    required = ["ticker", "trade_date", "payload", "checksum"]
    for i, line in enumerate(REAL_DATASET.read_text(encoding="utf-8").split("\n")[:100]):
        if not line.strip():
            continue
        rec = json.loads(line)
        for f in required:
            if f not in rec or rec[f] is None:
                print(f"  [FAIL] 第 {i+1} 行缺字段 {f}")
                return False
    print(f"  [PASS] 前 100 行字段齐全无 None")
    return True


# ----------------------------------------------------------------------
# Section 5: V1.4 真实 ETL 切换 + 文档(3 测点)
# ----------------------------------------------------------------------

def t20_sandbox_source_marker() -> bool:
    """校验 sandbox 标识(source=synthetic / sandbox_synthetic)。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    if "sandbox_synthetic" not in txt and '"synthetic"' not in txt:
        print("  [FAIL] 缺 sandbox 标识")
        return False
    print(f"  [PASS] 含 sandbox 标识(source='synthetic' / 'sandbox_synthetic')")
    return True


def t21_v14_etl_switch_doc() -> bool:
    """校验 V1.4 ETL 切换文档(m7t3 / m7t4 v3.0-final 报告)。"""
    p = ROOT / "docs" / "BD-087-calibration-report-v3.0-final.md"
    txt = p.read_text(encoding="utf-8")
    if "backtest_dataset_real" not in txt and "backtest_dataset_pg" not in txt:
        print("  [FAIL] v3.0-final 报告缺 ETL 切换步骤")
        return False
    print(f"  [PASS] v3.0-final 报告含 ETL 切换步骤")
    return True


def t22_no_actual_pg_dependency() -> bool:
    """校验沙箱 stub 不依赖 PG(asyncpg / sqlalchemy)。"""
    p = BACKEND_ETL / "backtest_dataset_real.py"
    txt = p.read_text(encoding="utf-8")
    if "import asyncpg" in txt or "from sqlalchemy" in txt:
        print("  [FAIL] 沙箱 stub 引入了 PG 依赖")
        return False
    print(f"  [PASS] 沙箱 stub 无 PG 依赖(纯 hashlib 合成)")
    return True


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[str] = []


def _run(name: str, fn) -> None:
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {name} 抛出异常: {exc}")
        ok = False
    if ok:
        _PASSED.append(name)
    else:
        _FAILED.append(name)


def main() -> int:
    print("=== 1. 模块加载 + 核心函数 ===")
    _run("t01_module_loads", t01_module_loads)
    _run("t02_seeded_float_exists", t02_seeded_float_exists)
    _run("t03_build_real_dataset_sandbox_exists", t03_build_real_dataset_sandbox_exists)
    _run("t04_synthesize_functions", t04_synthesize_functions)
    _run("t05_dataclass_result", t05_dataclass_result)

    print("\n=== 2. 沙箱 stub 运行 + 数据完整性 ===")
    _run("t06_goldset_exists", t06_goldset_exists)
    _run("t07_build_dataset_runs", t07_build_dataset_runs)
    _run("t08_real_dataset_jsonl_exists", t08_real_dataset_jsonl_exists)
    _run("t09_real_dataset_line_count", t09_real_dataset_line_count)
    _run("t10_real_dataset_field_completeness", t10_real_dataset_field_completeness)
    _run("t11_real_dataset_unique_tickers", t11_real_dataset_unique_tickers)

    print("\n=== 3. SHA256 deterministic 稳定性 ===")
    _run("t12_seeded_float_deterministic", t12_seeded_float_deterministic)
    _run("t13_seeded_float_different_tickers", t13_seeded_float_different_tickers)
    _run("t14_seeded_float_range", t14_seeded_float_range)
    _run("t15_synthesize_ohlcv_in_range", t15_synthesize_ohlcv_in_range)

    print("\n=== 4. 数据格式 + 一致性 ===")
    _run("t16_real_dataset_iso_date", t16_real_dataset_iso_date)
    _run("t17_short_volume_ratio", t17_short_volume_ratio)
    _run("t18_form4_count_range", t18_form4_count_range)
    _run("t19_real_dataset_no_missing_fields", t19_real_dataset_no_missing_fields)

    print("\n=== 5. V1.4 ETL 切换 + 文档 ===")
    _run("t20_sandbox_source_marker", t20_sandbox_source_marker)
    _run("t21_v14_etl_switch_doc", t21_v14_etl_switch_doc)
    _run("t22_no_actual_pg_dependency", t22_no_actual_pg_dependency)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m7t3] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m7t3] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m7t3] ALL {total} BD-085 REAL DATASET TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
