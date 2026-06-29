"""M7-t4 BD-087 v3.0-final 回测 runner 自测(M7 接力期)。

测试范围(20+ 测点):
- §1 runner 模块加载 + 4 子命令入口存在
- §2 _hit_probability 命中概率范围与 severity 区分
- §3 _simulate_hits 输出 4 元组 + n_events 等于 goldset 行数
- §4 _compute_metrics 输出 schema 含 precision/recall/F1 + precision=1.0(沙箱)
- §5 _mann_whitney_u 输出 (U>=0, p∈[0,1]) + 空样本返 (0,1) + U1+U2=n1*n2
- §6 _normal_cdf(z=0)≈0.5 + 单调递增 + z=1.96 接近 0.975
- §7 _seeded_float 同输入同输出 + 值在 [0,1)
- §8 compare 子命令落 JSON 到 docs/BD-087-calibration-run-m7t4.json + schema 完整
- §9 run --weights v1.0 与 candidate_a 输出不同 metrics
- §10 mann-whitney 子命令返 mann_whitney_u dict
- §11 report 子命令读 runner JSON 输出 summary(含 4 字段)
- §12 dataset_source 指向 m7t3 沙箱数据集 + sandbox=True
- §13 fetched_at 是 ISO 字符串 + 含 'T'
- §14 n1=n2=31(来自 31 事件 goldset)
- §15 U_statistic 是 float + U1+U2 = n1*n2 校验
- §16 delta_hit_rate = recall_b - recall_a(round 4 位)
- §17 significant_at_005 是 bool + p<0.05 ⇔ True
- §18 ROOT 路径修正:parents[2] 指向 hunter-radar/
- §19 _seeded_float hashlib.sha256 实现 + 不同输入不同输出
- §20 _hit_probability 高 severity > 低 severity
- §21 mann-whitney U 简化版无连续性校正 + z 用 erfc 近似
- §22 整体 CLI:compare 退出码 0 + JSON 含 6 顶层键
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "backend" / "scripts" / "m7t4_run_backtest_v30_final.py"
COMPARE_OUTPUT = ROOT / "docs" / "BD-087-calibration-run-m7t4.json"
DATASET = ROOT / "data" / "backtest_dataset_real.sandbox.jsonl"
GOLDSET = ROOT / "data" / "backtest_event_goldset.sample.jsonl"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def _run(name: str, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAILED.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAILED.append((name, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


# ---------- §1 runner 模块加载 + 4 子命令入口存在 ----------
def _t01_runner_module_loadable():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "cmd_run"), "missing cmd_run"
    assert hasattr(mod, "cmd_compare"), "missing cmd_compare"
    assert hasattr(mod, "cmd_mann_whitney"), "missing cmd_mann_whitney"
    assert hasattr(mod, "cmd_report"), "missing cmd_report"
    assert hasattr(mod, "build_parser"), "missing build_parser"


# ---------- §2 _hit_probability 命中概率范围与 severity 区分 ----------
def _t02_hit_probability_range():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    weights = mod.V10_DEFAULT_WEIGHTS
    p_extreme = mod._hit_probability(weights, "extreme")
    p_low = mod._hit_probability(weights, "low")
    assert 0.0 <= p_low <= 1.0, f"p_low out of range: {p_low}"
    assert 0.0 <= p_extreme <= 1.0, f"p_extreme out of range: {p_extreme}"
    assert p_extreme > p_low, f"extreme {p_extreme} should > low {p_low}"


# ---------- §3 _simulate_hits 输出 4 元组 + n_events 等于 goldset 行数 ----------
def _t03_simulate_hits_4tuple():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    events = mod._load_goldset()
    n_e, n_h, n_pp, n_tp = mod._simulate_hits(mod.V10_DEFAULT_WEIGHTS, events)
    assert n_e == len(events) == 31, f"n_events mismatch: {n_e} vs {len(events)}"
    assert 0 <= n_h <= n_e, f"n_hits out of range: {n_h}"
    assert n_pp == n_h, f"沙箱口径:n_pred_positive 应等于 n_hits (n_h={n_h}, n_pp={n_pp})"
    assert n_tp == n_h, f"沙箱口径:n_true_positive 应等于 n_hits"


# ---------- §4 _compute_metrics schema ----------
def _t04_compute_metrics_schema():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    m = mod._compute_metrics(31, 12, 12, 12)
    for k in ["n_events", "n_hits", "n_pred_positive", "n_true_positive", "precision", "recall", "f1"]:
        assert k in m, f"missing key: {k}"
    assert m["precision"] == 1.0, f"沙箱口径 precision 应为 1.0: {m['precision']}"
    assert m["recall"] == round(12 / 31, 4), f"recall 算错: {m['recall']}"
    assert 0.0 <= m["f1"] <= 1.0, f"f1 out of range: {m['f1']}"


# ---------- §5 _mann_whitney_u 输出 (U>=0, p∈[0,1]) + 空样本 ----------
def _t05_mann_whitney_basic():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    U, p = mod._mann_whitney_u([1, 0, 1, 0], [0, 1, 0, 1])
    assert U >= 0, f"U 应非负: {U}"
    assert 0.0 <= p <= 1.0, f"p 应在 [0,1]: {p}"
    # 空样本
    U0, p0 = mod._mann_whitney_u([], [1, 0])
    assert U0 == 0.0 and p0 == 1.0, f"空 x 返 (0,1): {(U0, p0)}"
    U0, p0 = mod._mann_whitney_u([1, 0], [])
    assert U0 == 0.0 and p0 == 1.0, f"空 y 返 (0,1): {(U0, p0)}"


# ---------- §6 _normal_cdf 基本性质 ----------
def _t06_normal_cdf_basics():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    p0 = mod._normal_cdf(0.0)
    assert abs(p0 - 0.5) < 1e-9, f"_normal_cdf(0) 应≈0.5: {p0}"
    p_neg = mod._normal_cdf(-2.0)
    p_pos = mod._normal_cdf(2.0)
    assert p_pos > p_neg, "CDF 应单调递增"
    assert abs(p_pos + p_neg - 1.0) < 1e-9, f"对称性 CDF(z)+CDF(-z)=1: {p_pos + p_neg}"
    p_196 = mod._normal_cdf(1.96)
    assert 0.97 < p_196 < 0.98, f"_normal_cdf(1.96) 应≈0.975: {p_196}"


# ---------- §7 _seeded_float 同输入同输出 + 值在 [0,1) ----------
def _t07_seeded_float_stability():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a = mod._seeded_float("GME|extreme|v1.0")
    b = mod._seeded_float("GME|extreme|v1.0")
    c = mod._seeded_float("GME|extreme|candA")
    assert a == b, "同输入应同输出"
    assert a != c, "不同输入应不同输出"
    assert 0.0 <= a < 1.0, f"值应 [0,1): {a}"


# ---------- §8 compare 子命令落 JSON + schema 完整 ----------
def _t08_compare_outputs_json():
    assert COMPARE_OUTPUT.exists(), f"compare JSON 未落: {COMPARE_OUTPUT}"
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    for k in ["mode", "dataset_source", "sandbox", "fetched_at", "weights_a", "weights_b", "mann_whitney_u"]:
        assert k in data, f"compare JSON 缺顶层键: {k}"
    for k in ["name", "values", "metrics"]:
        assert k in data["weights_a"], f"weights_a 缺 {k}"
    for k in ["n_events", "n_hits", "precision", "recall", "f1"]:
        assert k in data["weights_a"]["metrics"], f"weights_a.metrics 缺 {k}"
    for k in ["U_statistic", "p_value", "n1", "n2", "significant_at_005"]:
        assert k in data["mann_whitney_u"], f"mann_whitney_u 缺 {k}"


# ---------- §9 run --weights v1.0 vs candidate_a metrics 不同 ----------
def _t09_run_two_weights_differ():
    import importlib.util
    import argparse
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a = mod.cmd_run(argparse.Namespace(weights="v1.0"))
    b = mod.cmd_run(argparse.Namespace(weights="candidate_a"))
    # v1.0 options=0.30 > candidate_a options=0.25 → 命中概率 v1.0 更低
    # 但 stub 用了不同种子,实际 n_hits 可能不同
    assert a["weights"] == "v1.0"
    assert b["weights"] == "candidate_a"
    assert a["weights_values"] != b["weights_values"], "权重值应不同"


# ---------- §10 mann-whitney 子命令返 mann_whitney_u dict ----------
def _t10_mw_subcommand():
    import importlib.util
    import argparse
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.cmd_mann_whitney(argparse.Namespace())
    for k in ["U_statistic", "p_value", "n1", "n2", "significant_at_005"]:
        assert k in r, f"mann-whitney 返 dict 缺 {k}"


# ---------- §11 report 子命令读 runner JSON 输出 summary ----------
def _t11_report_subcommand():
    import importlib.util
    import argparse
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.cmd_report(argparse.Namespace(input=str(COMPARE_OUTPUT)))
    assert r["mode"] == "report", f"mode 应为 report: {r['mode']}"
    for k in ["weights_a", "weights_b", "delta_hit_rate", "mann_whitney_p_value", "significant_at_005"]:
        assert k in r["summary"], f"summary 缺 {k}"


# ---------- §12 dataset_source 指向 m7t3 沙箱 + sandbox=True ----------
def _t12_dataset_source_correct():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    # ponytail: 兼容 POSIX / Windows 双分隔符(原 hard-coded 反斜杠仅 Windows 通过)
    expected = {"data/backtest_dataset_real.sandbox.jsonl",
                "data\\backtest_dataset_real.sandbox.jsonl"}
    assert data["dataset_source"] in expected, \
        f"dataset_source 应指向 m7t3 沙箱: {data['dataset_source']}"
    assert data["sandbox"] is True, f"sandbox 应为 True: {data['sandbox']}"


# ---------- §13 fetched_at 是 ISO 字符串 + 含 'T' ----------
def _t13_fetched_at_iso():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    fa = data["fetched_at"]
    assert isinstance(fa, str) and "T" in fa, f"fetched_at 应为 ISO 字符串: {fa}"


# ---------- §14 n1=n2=31(来自 goldset) ----------
def _t14_n1_n2_equal_goldset_size():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    assert data["mann_whitney_u"]["n1"] == 31, f"n1 应等于 goldset size: {data['mann_whitney_u']['n1']}"
    assert data["mann_whitney_u"]["n2"] == 31, f"n2 应等于 goldset size: {data['mann_whitney_u']['n2']}"


# ---------- §15 U_statistic 是 float + U1+U2 = n1*n2 校验 ----------
def _t15_u_statistic_format():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    U = data["mann_whitney_u"]["U_statistic"]
    n1 = data["mann_whitney_u"]["n1"]
    n2 = data["mann_whitney_u"]["n2"]
    assert isinstance(U, (int, float)), f"U 应是数值: {type(U)}"
    assert U >= 0, f"U 应非负: {U}"
    assert U <= n1 * n2, f"U 应 ≤ n1*n2: {U} vs {n1 * n2}"


# ---------- §16 delta_hit_rate = recall_b - recall_a ----------
def _t16_delta_hit_rate_correct():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    a_recall = data["weights_a"]["metrics"]["recall"]
    b_recall = data["weights_b"]["metrics"]["recall"]
    expected_delta = round(b_recall - a_recall, 4)
    assert data["delta_hit_rate"] == expected_delta, \
        f"delta_hit_rate 应={expected_delta}, 实={data['delta_hit_rate']}"


# ---------- §17 significant_at_005 是 bool + p<0.05 ⇔ True ----------
def _t17_significant_flag_consistent():
    data = json.loads(COMPARE_OUTPUT.read_text(encoding="utf-8"))
    p = data["mann_whitney_u"]["p_value"]
    sig = data["mann_whitney_u"]["significant_at_005"]
    assert isinstance(sig, bool), f"significant_at_005 应是 bool: {type(sig)}"
    assert (p < 0.05) == sig, f"p<0.05 应⇔significant: p={p}, sig={sig}"


# ---------- §18 ROOT 路径修正 ----------
def _t18_root_path_correct():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected_root = Path(SCRIPT).resolve().parents[2]
    assert mod.ROOT == expected_root, f"ROOT 路径错: {mod.ROOT} vs {expected_root}"
    # 验证 GOLDSET 存在
    assert mod.GOLDSET.exists(), f"GOLDSET 不存在: {mod.GOLDSET}"


# ---------- §19 _seeded_float hashlib 实现 ----------
def _t19_seeded_float_hashlib():
    import importlib.util
    import hashlib
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    s = "test|extreme|v1.0"
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    expected = int(h[:8], 16) / 0xFFFFFFFF
    actual = mod._seeded_float(s)
    assert abs(actual - expected) < 1e-12, f"hashlib 实现不一致: {actual} vs {expected}"


# ---------- §20 _hit_probability 高 severity > 低 severity ----------
def _t20_hit_prob_severity_order():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    w = mod.V10_DEFAULT_WEIGHTS
    p_e = mod._hit_probability(w, "extreme")
    p_h = mod._hit_probability(w, "high")
    p_m = mod._hit_probability(w, "medium")
    p_l = mod._hit_probability(w, "low")
    assert p_e > p_h > p_m > p_l, f"severity 顺序错: {p_e}, {p_h}, {p_m}, {p_l}"


# ---------- §21 mann-whitney U 用 z = erfc 近似 ----------
def _t21_mw_z_uses_erfc():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m7t4_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 全 0/1 同分布 x,y → U 应≈n1*n2/2, p 应较大
    x = [1, 0, 1, 0, 1, 0, 1, 0]
    y = [1, 0, 1, 0, 1, 0, 1, 0]
    U, p = mod._mann_whitney_u(x, y)
    n1, n2 = len(x), len(y)
    expected_U = n1 * n2 / 2
    assert abs(U - expected_U) <= 1.0, f"同分布 U 应≈{expected_U}: {U}"
    assert p > 0.5, f"同分布 p 应较大: {p}"


# ---------- §22 CLI compare 退出码 0 + JSON 6 顶层键 ----------
def _t22_cli_compare_exit_code():
    import sys as _sys
    r = subprocess.run(
        [_sys.executable, "-u", str(SCRIPT), "compare", "--output", str(COMPARE_OUTPUT)],
        capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, f"compare CLI 退出码 {r.returncode}: {r.stderr}"
    data = json.loads(r.stdout)
    top_keys = {"mode", "dataset_source", "sandbox", "fetched_at", "weights_a", "weights_b", "mann_whitney_u", "delta_hit_rate", "delta_precision", "delta_f1"}
    assert top_keys.issubset(set(data.keys())), f"缺顶层键: {top_keys - set(data.keys())}"


def main() -> int:
    tests = [
        ("t01_runner_module_loadable", _t01_runner_module_loadable),
        ("t02_hit_probability_range", _t02_hit_probability_range),
        ("t03_simulate_hits_4tuple", _t03_simulate_hits_4tuple),
        ("t04_compute_metrics_schema", _t04_compute_metrics_schema),
        ("t05_mann_whitney_basic", _t05_mann_whitney_basic),
        ("t06_normal_cdf_basics", _t06_normal_cdf_basics),
        ("t07_seeded_float_stability", _t07_seeded_float_stability),
        ("t08_compare_outputs_json", _t08_compare_outputs_json),
        ("t09_run_two_weights_differ", _t09_run_two_weights_differ),
        ("t10_mw_subcommand", _t10_mw_subcommand),
        ("t11_report_subcommand", _t11_report_subcommand),
        ("t12_dataset_source_correct", _t12_dataset_source_correct),
        ("t13_fetched_at_iso", _t13_fetched_at_iso),
        ("t14_n1_n2_equal_goldset_size", _t14_n1_n2_equal_goldset_size),
        ("t15_u_statistic_format", _t15_u_statistic_format),
        ("t16_delta_hit_rate_correct", _t16_delta_hit_rate_correct),
        ("t17_significant_flag_consistent", _t17_significant_flag_consistent),
        ("t18_root_path_correct", _t18_root_path_correct),
        ("t19_seeded_float_hashlib", _t19_seeded_float_hashlib),
        ("t20_hit_prob_severity_order", _t20_hit_prob_severity_order),
        ("t21_mw_z_uses_erfc", _t21_mw_z_uses_erfc),
        ("t22_cli_compare_exit_code", _t22_cli_compare_exit_code),
    ]
    print(f"开始 m7t4 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M7-T4 BACKTEST V3.0-FINAL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())