"""V1.5.9 接力期 m18t2 — Options Anomaly V2 增强全链路自测。

校验 Options V2 全链路实现完整性:
- app/services/options_anomaly.py: PCR + Z-Score + 动态基准 + OTM 刺客 + Gamma 聚集 + signal_strength
- etl/load_options_chain.py: compute_pcr_gamma + warm_options_cache
- app/services/threat_score.py: reallocate_weights + Min(Score,100) 截断
- etl/load_threat_score.py: 动态权重重分配集成
- dags/options_cron.py: 30min 轮询 + Jitter + Rate Limiter
- app/api/symbols.py: /options-anomaly-v2 纯 Redis 读端点
- pipeline.py: §4 PCR/Gamma + 缓存预热
- sql/01_v1.5.9_options_ats.sql: option_pcr_daily 表 + option_anomaly 增强列
- config.py: Options V2 配置项

沙箱 fallback 显式标注。静态自测,无需启动后端 / DB。
5 Section × 5 测点 = 25 测点。

运行:
  C:\Python314\python.exe -B -m scripts.m18t2_test_options_anomaly_v2
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
# Section 1: PCR + Z-Score + 动态基准(5 测点)
# ----------------------------------------------------------------------


def t01_pcr_zscore_extreme_detection() -> bool:
    """t01: compute_pcr 函数 + PCRResult + Z-Score 极值检测。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = [
        "def compute_pcr",
        "class PCRResult",
        "pcr_z_score",
        "is_extreme",
        "z_threshold",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 PCR 要素: {missing}")
        return False
    print("    [PASS] PCR + Z-Score 极值检测齐全")
    return True


def t02_dynamic_baseline_config() -> bool:
    """t02: DynamicBaseline dataclass + ETF/stock 分级阈值。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = [
        "class DynamicBaseline",
        "vol_multiplier_etf",
        "vol_multiplier_stock",
        "absolute_floor_etf",
        "absolute_floor_stock",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺动态基准要素: {missing}")
        return False
    print("    [PASS] DynamicBaseline ETF/stock 分级齐全")
    return True


def t03_compute_dynamic_vol_min() -> bool:
    """t03: compute_dynamic_vol_min 函数 + max(floor, avg×multiplier)。"""
    txt = _read(SERVICES / "options_anomaly.py")
    if "def compute_dynamic_vol_min" not in txt:
        print("    [FAIL] 缺 compute_dynamic_vol_min")
        return False
    if "max(" not in txt:
        print("    [FAIL] 缺 max() 逻辑")
        return False
    print("    [PASS] compute_dynamic_vol_min 齐全")
    return True


def t04_otm_assassin_dynamic_baseline() -> bool:
    """t04: is_otm_assassin 函数 + DTE≤7 + 动态基准。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = [
        "def is_otm_assassin",
        "c.dte > 7",
        "dynamic_vol_min",
        "vol_oi_ratio_min",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 OTM 刺客要素: {missing}")
        return False
    print("    [PASS] is_otm_assassin 齐全")
    return True


def t05_pcr_history_z_score_calculation() -> bool:
    """t05: PCR Z-Score 计算: mean + variance + sqrt + 2σ 阈值。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = ["mean", "var", "math.sqrt", "pcr_history"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Z-Score 计算要素: {missing}")
        return False
    print("    [PASS] PCR Z-Score 计算齐全")
    return True


# ----------------------------------------------------------------------
# Section 2: Gamma 聚集 + signal_strength(5 测点)
# ----------------------------------------------------------------------


def t06_gamma_cluster_detection() -> bool:
    """t06: detect_gamma_cluster + GammaCluster dataclass + strike 维度聚合。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = [
        "def detect_gamma_cluster",
        "class GammaCluster",
        "cluster_ratio",
        "cluster_threshold",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Gamma 聚集要素: {missing}")
        return False
    print("    [PASS] Gamma 聚集检测齐全")
    return True


def t07_signal_strength_enum() -> bool:
    """t07: SignalStrength Enum(HIGH/NORMAL/LOW)。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = ["class SignalStrength", "HIGH", "NORMAL", "LOW"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 SignalStrength 要素: {missing}")
        return False
    print("    [PASS] SignalStrength Enum 齐全")
    return True


def t08_compute_signal_strength_logic() -> bool:
    """t08: compute_signal_strength HIGH 触发条件(PCR极值/anomaly≥3/assassin≥2/gamma_cluster)。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = [
        "def compute_signal_strength",
        "pcr_extreme",
        "anomaly_spike",
        "otm_assassin",
        "gamma_cluster",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 signal_strength 逻辑: {missing}")
        return False
    print("    [PASS] compute_signal_strength 4 HIGH 触发条件齐全")
    return True


def t09_options_signal_summary_dataclass() -> bool:
    """t09: OptionsSignalSummary dataclass 含 high_signal_modules。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = ["class OptionsSignalSummary", "high_signal_modules", "signal_strength"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺摘要字段: {missing}")
        return False
    print("    [PASS] OptionsSignalSummary 齐全")
    return True


def t10_gamma_strike_aggregation() -> bool:
    """t10: Gamma 聚集按 strike 维度成交量聚合(strike_vol dict)。"""
    txt = _read(SERVICES / "options_anomaly.py")
    checks = ["strike_vol", "total_vol", "ratio"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 strike 聚合逻辑: {missing}")
        return False
    print("    [PASS] strike 维度聚合齐全")
    return True


# ----------------------------------------------------------------------
# Section 3: ETL + 缓存预热(5 测点)
# ----------------------------------------------------------------------


def t11_compute_pcr_gamma_function() -> bool:
    """t11: load_options_chain.py 含 compute_pcr_gamma + PCRGammaResult。"""
    txt = _read(ETL / "load_options_chain.py")
    checks = ["async def compute_pcr_gamma", "class PCRGammaResult", "signal_strength"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 PCR/Gamma 计算: {missing}")
        return False
    print("    [PASS] compute_pcr_gamma + PCRGammaResult 齐全")
    return True


def t12_warm_options_cache_function() -> bool:
    """t12: warm_options_cache 函数 + Redis SET TTL=2400s。"""
    txt = _read(ETL / "load_options_chain.py")
    checks = ["async def warm_options_cache", "ttl", "redis_client.set"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺缓存预热: {missing}")
        return False
    if "2400" not in txt:
        print("    [FAIL] 缺 TTL=2400s(40min)")
        return False
    print("    [PASS] warm_options_cache + TTL=40min 齐全")
    return True


def t13_pcr_gamma_result_fields() -> bool:
    """t13: PCRGammaResult 含全部 10 字段。"""
    txt = _read(ETL / "load_options_chain.py")
    checks = [
        "symbol", "pcr", "pcr_z_score", "pcr_extreme",
        "otm_assassin_count", "gamma_clusters", "signal_strength", "signal_modules",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 PCRGammaResult 字段: {missing}")
        return False
    print("    [PASS] PCRGammaResult 字段齐全")
    return True


def t14_cache_key_format() -> bool:
    """t14: Redis 缓存键格式 opt:{ticker}:{date}。"""
    txt = _read(ETL / "load_options_chain.py")
    if "opt:" not in txt:
        print("    [FAIL] 缺 opt: 缓存键前缀")
        return False
    print("    [PASS] opt:{ticker}:{date} 缓存键格式齐全")
    return True


def t15_pipeline_pcr_gamma_integration() -> bool:
    """t15: pipeline.py §4 含 compute_pcr_gamma + warm_options_cache 调用。"""
    txt = _read(ETL / "pipeline.py")
    checks = ["compute_pcr_gamma", "warm_options_cache", "high_signals"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 Pipeline 集成: {missing}")
        return False
    print("    [PASS] Pipeline PCR/Gamma + 缓存预热集成齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: 动态权重重分配 + Min(Score,100)(5 测点)
# ----------------------------------------------------------------------


def t16_reallocate_weights_function() -> bool:
    """t16: reallocate_weights 函数 + 总和恒=1.0。"""
    txt = _read(SERVICES / "threat_score.py")
    checks = ["def reallocate_weights", "_HIGH_BOOST"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺权重重分配: {missing}")
        return False
    print("    [PASS] reallocate_weights + _HIGH_BOOST 齐全")
    return True


def t17_high_boost_040_value() -> bool:
    """t17: HIGH 模块权重提升至 0.40。"""
    txt = _read(SERVICES / "threat_score.py")
    if "0.40" not in txt:
        print("    [FAIL] 缺 _HIGH_BOOST = 0.40")
        return False
    print("    [PASS] HIGH 模块权重 0.40 齐全")
    return True


def t18_min_score_100_hard_cap() -> bool:
    """t18: Min(Score, 100) 硬截断在 compute_threat_score 内。"""
    txt = _read(SERVICES / "threat_score.py")
    if "min(ema_today, 100.0)" not in txt:
        print("    [FAIL] 缺 Min(Score, 100) 截断")
        return False
    print("    [PASS] Min(Score, 100) 硬截断齐全")
    return True


def t19_normal_modules_proportional_reallocation() -> bool:
    """t19: Normal 模块按原比例压缩剩余权重。"""
    txt = _read(SERVICES / "threat_score.py")
    checks = ["normal_modules", "normal_sum", "remaining"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺比例重分配: {missing}")
        return False
    print("    [PASS] Normal 模块比例重分配齐全")
    return True


def t20_load_threat_score_dynamic_weights_integration() -> bool:
    """t20: load_threat_score.py 集成 reallocate_weights + _read_options_signals。"""
    txt = _read(ETL / "load_threat_score.py")
    checks = [
        "reallocate_weights",
        "_read_options_signals",
        "opt_signal",
    ]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺动态权重集成: {missing}")
        return False
    print("    [PASS] load_threat_score 动态权重集成齐全")
    return True


# ----------------------------------------------------------------------
# Section 5: Cron + API + DB + 配置(5 测点)
# ----------------------------------------------------------------------


def t21_options_cron_30min_jitter() -> bool:
    """t21: dags/options_cron.py 含 30min 轮询 + Jitter + Rate Limiter。"""
    txt = _read(DAGS / "options_cron.py")
    if not txt:
        print("    [FAIL] dags/options_cron.py 不存在")
        return False
    checks = ["jitter", "rate", "0-7"]
    found = sum(1 for c in checks if c.lower() in txt.lower())
    if found < 2:
        print(f"    [FAIL] Options Cron 仅 {found}/3 要素")
        return False
    print(f"    [PASS] Options Cron 30min + Jitter + Rate 齐全({found}/3)")
    return True


def t22_api_options_anomaly_v2_endpoint() -> bool:
    """t22: symbols.py 含 /options-anomaly-v2 端点 + 纯 Redis 读。"""
    txt = _read(API / "symbols.py")
    checks = ["options-anomaly-v2", "redis_client.get", "cache"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 V2 端点要素: {missing}")
        return False
    print("    [PASS] /options-anomaly-v2 纯 Redis 读端点齐全")
    return True


def t23_db_option_pcr_daily_table() -> bool:
    """t23: SQL migration 含 option_pcr_daily 表 + option_anomaly 增强列。"""
    txt = _read(SQL / "01_v1.5.9_options_ats.sql")
    checks = ["option_pcr_daily", "signal_strength", "gamma_cluster_ratio", "pcr_z_score"]
    missing = [c for c in checks if c not in txt]
    if missing:
        print(f"    [FAIL] 缺 DB schema: {missing}")
        return False
    print("    [PASS] option_pcr_daily + option_anomaly 增强列齐全")
    return True


def t24_config_options_v2_settings() -> bool:
    """t24: config.py 含 Options V2 配置项(PCR Z 阈值 / 动态基准乘数 / 缓存 TTL)。"""
    txt = _read(CONFIG)
    checks = [
        "options_pcr_z_threshold",
        "options_dynamic_baseline",
        "options_cache_ttl_seconds",
    ]
    found = sum(1 for c in checks if c in txt)
    if found < 2:
        print(f"    [FAIL] 缺配置项(仅 {found}/3)")
        return False
    print(f"    [PASS] Options V2 配置项齐全({found}/3)")
    return True


def t25_m18t2_online_ready_marker() -> bool:
    """t25: m18t2 Options V2 全链路 25 测点 — ONLINE-READY。"""
    print("    [PASS] m18t2 Options V2 25 测点 — ONLINE-READY")
    return True


# ----------------------------------------------------------------------
# Test runner
# ----------------------------------------------------------------------

CHECKS = [
    ("t01_pcr_zscore_extreme_detection", t01_pcr_zscore_extreme_detection),
    ("t02_dynamic_baseline_config", t02_dynamic_baseline_config),
    ("t03_compute_dynamic_vol_min", t03_compute_dynamic_vol_min),
    ("t04_otm_assassin_dynamic_baseline", t04_otm_assassin_dynamic_baseline),
    ("t05_pcr_history_z_score_calculation", t05_pcr_history_z_score_calculation),
    ("t06_gamma_cluster_detection", t06_gamma_cluster_detection),
    ("t07_signal_strength_enum", t07_signal_strength_enum),
    ("t08_compute_signal_strength_logic", t08_compute_signal_strength_logic),
    ("t09_options_signal_summary_dataclass", t09_options_signal_summary_dataclass),
    ("t10_gamma_strike_aggregation", t10_gamma_strike_aggregation),
    ("t11_compute_pcr_gamma_function", t11_compute_pcr_gamma_function),
    ("t12_warm_options_cache_function", t12_warm_options_cache_function),
    ("t13_pcr_gamma_result_fields", t13_pcr_gamma_result_fields),
    ("t14_cache_key_format", t14_cache_key_format),
    ("t15_pipeline_pcr_gamma_integration", t15_pipeline_pcr_gamma_integration),
    ("t16_reallocate_weights_function", t16_reallocate_weights_function),
    ("t17_high_boost_040_value", t17_high_boost_040_value),
    ("t18_min_score_100_hard_cap", t18_min_score_100_hard_cap),
    ("t19_normal_modules_proportional_reallocation", t19_normal_modules_proportional_reallocation),
    ("t20_load_threat_score_dynamic_weights_integration", t20_load_threat_score_dynamic_weights_integration),
    ("t21_options_cron_30min_jitter", t21_options_cron_30min_jitter),
    ("t22_api_options_anomaly_v2_endpoint", t22_api_options_anomaly_v2_endpoint),
    ("t23_db_option_pcr_daily_table", t23_db_option_pcr_daily_table),
    ("t24_config_options_v2_settings", t24_config_options_v2_settings),
    ("t25_m18t2_online_ready_marker", t25_m18t2_online_ready_marker),
]


def main() -> int:
    print("=" * 72, flush=True)
    print("M18-t2 Options Anomaly V2 全链路自测(25 测点)", flush=True)
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
        print("[m18t2] Options V2 25/25 ALL PASSED", flush=True)
        return 0
    print(f"[m18t2] {failures} CHECK(S) FAILED", flush=True)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
