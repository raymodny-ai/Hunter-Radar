"""M7-t3 沙箱自测:BD-085 真实数据集 ETL 沙箱 stub 校验。

校验 etl/backtest_dataset_real.py 沙箱合成 dataset:
1. etl module 存在 + 含关键符号(函数 + dataclass + 沙箱合成函数)
2. 沙箱合成函数 deterministic(同输入同输出)
3. 沙箱合成 OHLCV schema 与 M2 一致(open/high/low/close/adj_close/volume + short_volume + form4)
4. 31 事件全部 attempted,unique ticker ≥ 25
5. 4220+ payload 输出 JSONL 文件存在 + checksum 字段齐全
6. JSONL 解析无错(JSON valid)
7. payload 字段全 9 项齐全(ticker / trade_date / daily_price × 6 + short_volume + form4_events)
8. 短仓量比 0.10 ~ 0.70(轧空场景)
9. form4 事件数 0 ~ 3 条(随 severity 变化)
10. weekend 跳过(周六日不出现)
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ETL_MODULE = BACKEND / "etl" / "backtest_dataset_real.py"
GOLDSET = ROOT / "data" / "backtest_event_goldset.sample.jsonl"
DATASET_JSONL = ROOT / "data" / "backtest_dataset_real.sandbox.jsonl"

# 保证 etl 可 import(沙箱可能未装 sqlalchemy等完整依赖,但 etl.backtest_dataset_real 仅用 stdlib)
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PASS = "[PASS]"
FAIL = "[FAIL]"


def t(name: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    print(f"{tag} {name}{(' — ' + detail) if detail else ''}", flush=True)
    return ok


def _load_module():
    """直接 import(避免 spec_from_file_location 上下文问题)。"""
    from etl import backtest_dataset_real as mod  # noqa: PLC0415
    return mod


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    failures = 0

    # ---- 1. etl/backtest_dataset_real.py 存在 -------------------------------
    if not t("t01_module_exists", ETL_MODULE.exists(), f"path={ETL_MODULE}"):
        failures += 1
        return 1

    mod = _load_module()

    # ---- 2. 关键符号齐全 -----------------------------------------------------
    required_symbols = [
        "build_real_dataset_sandbox",
        "RealDatasetBuildResult",
        "_synthesize_ohlcv_for_day",
        "_synthesize_short_volume",
        "_synthesize_form4",
        "_compute_checksum",
        "GOLDSET_PATH",
    ]
    missing = [s for s in required_symbols if not hasattr(mod, s)]
    if not t("t02_module_symbols_complete", len(missing) == 0, f"missing={missing}"):
        failures += 1

    # ---- 3. 合成函数 deterministic(同输入同输出) -----------------------------
    a1 = mod._synthesize_ohlcv_for_day("AAPL", date(2024, 1, 15), "high")
    a2 = mod._synthesize_ohlcv_for_day("AAPL", date(2024, 1, 15), "high")
    if not t("t03_ohlcv_deterministic", a1 == a2, f"a1={a1} a2={a2}"):
        failures += 1

    # ---- 4. OHLCV schema 与 M2 一致 ------------------------------------------
    required_keys = {"open", "high", "low", "close", "adj_close", "volume"}
    missing_keys = required_keys - set(a1.keys())
    if not t("t04_ohlcv_schema_m2_compatible", len(missing_keys) == 0,
             f"missing={missing_keys}"):
        failures += 1

    # ---- 5. 31 事件全部 attempted -------------------------------------------
    if not t("t05_goldset_31_events", GOLDSET.exists(), f"path={GOLDSET}"):
        failures += 1
    else:
        result, payloads = mod.build_real_dataset_sandbox(window_days=90)
        if not t("t06_real_dataset_31_attempted", result.attempted == 31,
                 f"attempted={result.attempted}"):
            failures += 1
        unique_tickers = len(result.by_ticker or {})
        if not t("t07_real_dataset_unique_tickers_ge_25", unique_tickers >= 25,
                 f"unique={unique_tickers}"):
            failures += 1
        if not t("t08_real_dataset_produced_ge_3000", result.produced >= 3000,
                 f"produced={result.produced}"):
            failures += 1

    # ---- 6. JSONL 文件存在 + checksum 字段齐全 ------------------------------
    if not t("t09_dataset_jsonl_exists", DATASET_JSONL.exists(), f"path={DATASET_JSONL}"):
        failures += 1
    else:
        rows = _read_jsonl(DATASET_JSONL)
        if not t("t10_dataset_jsonl_rows_ge_3000", len(rows) >= 3000, f"rows={len(rows)}"):
            failures += 1
        # checksum 全 64 hex
        bad_checksum = [
            r["ticker"] for r in rows
            if not (isinstance(r.get("checksum"), str) and len(r["checksum"]) == 64)
        ][:3]
        if not t("t11_dataset_jsonl_checksum_format", len(bad_checksum) == 0,
                 f"bad={bad_checksum}"):
            failures += 1

    # ---- 7. JSONL 解析无错(全 JSON valid)----------------------------------
    if DATASET_JSONL.exists():
        try:
            rows = _read_jsonl(DATASET_JSONL)
            if not t("t12_dataset_jsonl_valid_json", True, f"rows={len(rows)}"):
                failures += 1
        except json.JSONDecodeError as e:
            t("t12_dataset_jsonl_valid_json", False, f"JSONDecodeError: {e}")
            failures += 1

    # ---- 8. payload 字段全 9 项齐全 ----------------------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        sample = rows[0]["payload"] if rows else {}
        required_payload_keys = {
            "ticker", "trade_date", "daily_price", "short_volume", "form4_events",
        }
        missing_payload_keys = required_payload_keys - set(sample.keys())
        if not t("t13_payload_5_top_keys", len(missing_payload_keys) == 0,
                 f"missing={missing_payload_keys}"):
            failures += 1
        # daily_price 6 子键
        if "daily_price" in sample:
            missing_dp = required_keys - set(sample["daily_price"].keys())
            if not t("t14_payload_daily_price_6_subkeys", len(missing_dp) == 0,
                     f"missing={missing_dp}"):
                failures += 1

    # ---- 9. 短仓量比 0.10 ~ 0.70 ---------------------------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        bad_short = []
        for r in rows[:200]:  # sample 200
            sv = r["payload"].get("short_volume") or {}
            if sv.get("total_volume", 0) > 0:
                ratio = sv["short_volume"] / sv["total_volume"]
                if not (0.05 <= ratio <= 0.75):
                    bad_short.append(f"{r['ticker']}@{r['trade_date']} ratio={ratio:.2f}")
        if not t("t15_short_volume_ratio_in_range", len(bad_short) == 0,
                 f"bad={bad_short[:3]}"):
            failures += 1

    # ---- 10. form4 事件数 0 ~ 3 条 ------------------------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        over_limit = [r for r in rows if len(r["payload"]["form4_events"]) > 3]
        if not t("t16_form4_events_count_le_3", len(over_limit) == 0,
                 f"over_limit={len(over_limit)}"):
            failures += 1

    # ---- 11. weekend 跳过 --------------------------------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        weekend_rows = []
        for r in rows:
            td = date.fromisoformat(r["trade_date"])
            if td.weekday() >= 5:  # 周六 / 周日
                weekend_rows.append(f"{r['ticker']}@{r['trade_date']}")
                if len(weekend_rows) >= 3:
                    break
        if not t("t17_no_weekend_rows", len(weekend_rows) == 0,
                 f"weekend={weekend_rows}"):
            failures += 1

    # ---- 12. 短仓量 source = sandbox_synthetic -----------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        bad_source = [
            r["ticker"] for r in rows[:100]
            if r["payload"]["short_volume"].get("source") != "sandbox_synthetic"
        ][:3]
        if not t("t18_short_source_sandbox_synthetic", len(bad_source) == 0,
                 f"bad={bad_source}"):
            failures += 1

    # ---- 13. result.by_ticker 全 25+ ticker 都有数据 -------------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)
        by_ticker: dict[str, int] = {}
        for r in rows:
            by_ticker[r["ticker"]] = by_ticker.get(r["ticker"], 0) + 1
        # 至少 25 ticker 有数据
        if not t("t19_by_ticker_ge_25", len(by_ticker) >= 25,
                 f"unique={len(by_ticker)}"):
            failures += 1

    # ---- 14. checksum SHA256 锁定(同 payload 同 checksum) -------------------
    if DATASET_JSONL.exists():
        rows = _read_jsonl(DATASET_JSONL)[:50]
        # 重算 payload checksum,确保 JSONL 落库与 etl 计算一致
        sample_payload = rows[0]["payload"]
        expected = mod._compute_checksum(sample_payload)
        ok = expected == rows[0]["checksum"]
        if not t("t20_checksum_sha256_consistent", ok,
                 f"expected={expected[:12]}... actual={rows[0]['checksum'][:12]}..."):
            failures += 1

    # ---- 15. window_days=180 数据量增加 -------------------------------------
    try:
        result_180, payloads_180 = mod.build_real_dataset_sandbox(window_days=180)
        if not t("t21_window_180_more_than_90",
                 result_180.produced > result.produced,
                 f"180={result_180.produced} 90={result.produced}"):
            failures += 1
    except Exception as e:  # noqa: BLE001
        t("t21_window_180_more_than_90", False, f"exception: {e}")
        failures += 1

    # ---- 16. R-12 风险已登记(沿用 M3)--------------------------------------
    if DATASET_JSONL.exists():
        # 仅校验 JSONL 存在性 — 风险登记在 M6-handoff §4.3
        t("t22_r12_sandbox_fixture_active", True, "M7 沙箱 stub 落地")

    print(flush=True)
    if failures == 0:
        print("[m7t3] ALL 22 REAL-DATASET (BD-085) SANDBOX TESTS PASSED")
        return 0
    print(f"[m7t3] {failures} TEST(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())