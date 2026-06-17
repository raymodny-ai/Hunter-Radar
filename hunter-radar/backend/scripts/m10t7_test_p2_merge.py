"""M10-t7 V1.5.2 P2 合并工具自测(25 测点)。

V1.5.2 接力期 m10t7 — P2 合并工具自测:
- m10t7_p2_merge.py 双子命令(weight-switch-eval / vapid-separator)
- 候选 A 权重切换评估(Mann-Whitney U p_value 阈值)
- VAPID 沙箱(HR_ 前缀)与生产(无前缀)分离校验
- 4 状态判定(VAPID_PROD_ONLY / SANDBOX_ONLY / DUAL / NONE)
- BD-087 v3.0-final 已知结论沿用

Section 1 — 文件结构(4 测点):
  - m10t7_p2_merge.py 存在
  - V1.5.2 + m10t7 marker
  - weight-switch-eval 子命令
  - vapid-separator 子命令

Section 2 — 候选 A 权重切换(8 测点):
  - P_VALUE_THRESHOLD_DEFAULT = 0.05
  - BD087_V30_FINAL_P_VALUE = 0.3827
  - BD087_V30_FINAL_U_STAT = 418.5
  - BD087_V30_FINAL_DELTA_HIT_RATE = -0.0645
  - BD087_V30_FINAL_DELTA_F1 = -0.0703
  - CANDIDATE_A_WEIGHTS 定义
  - V10_DEFAULT_WEIGHTS 定义
  - BD087_V30_FINAL_DECISION

Section 3 — _evaluate_weight_switch(4 测点):
  - 函数存在
  - source: compare_input / bd087_v30_final_default
  - recommendation: switch_to_candidate_a / keep_v1.0
  - significant 判定

Section 4 — VAPID 分离(5 测点):
  - 4 VAPID 环境变量名
  - 4 状态常量
  - _check_vapid_separator 函数
  - is_production_safe 判定
  - VAPID_DUAL warning

Section 5 — CLI + 25 测点总数(4 测点):
  - build_parser 函数
  - 2 子命令解析
  - main 函数
  - 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
SCRIPTS = ROOT / "backend" / "scripts"
M10T7_PY = SCRIPTS / "m10t7_p2_merge.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_m10t7_exists() -> bool:
    """t01: m10t7_p2_merge.py 存在。"""
    if not M10T7_PY.exists():
        print("    [FAIL] m10t7_p2_merge.py 缺失")
        return False
    print("    [PASS] m10t7_p2_merge.py 存在")
    return True


def t02_v152_marker() -> bool:
    """t02: V1.5.2 接力期 m10t7 标记。"""
    txt = _read(M10T7_PY)
    if "V1.5.2" not in txt:
        print("    [FAIL] 缺 V1.5.2")
        return False
    if "m10t7" not in txt:
        print("    [FAIL] 缺 m10t7")
        return False
    if "P2" not in txt:
        print("    [FAIL] 缺 P2 标识")
        return False
    print("    [PASS] V1.5.2 接力期 m10t7 P2 标记")
    return True


def t03_weight_switch_subcommand() -> bool:
    """t03: weight-switch-eval 子命令。"""
    txt = _read(M10T7_PY)
    if "weight-switch-eval" not in txt:
        print("    [FAIL] 缺 weight-switch-eval 子命令")
        return False
    if "def cmd_weight_switch_eval" not in txt:
        print("    [FAIL] 缺 cmd_weight_switch_eval 函数")
        return False
    print("    [PASS] weight-switch-eval 子命令齐全")
    return True


def t04_vapid_separator_subcommand() -> bool:
    """t04: vapid-separator 子命令。"""
    txt = _read(M10T7_PY)
    if "vapid-separator" not in txt:
        print("    [FAIL] 缺 vapid-separator 子命令")
        return False
    if "def cmd_vapid_separator" not in txt:
        print("    [FAIL] 缺 cmd_vapid_separator 函数")
        return False
    print("    [PASS] vapid-separator 子命令齐全")
    return True


def t05_p_threshold_default() -> bool:
    """t05: P_VALUE_THRESHOLD_DEFAULT = 0.05。"""
    txt = _read(M10T7_PY)
    m = re.search(r"P_VALUE_THRESHOLD_DEFAULT\s*=\s*([\d.]+)", txt)
    if not m:
        print("    [FAIL] 缺 P_VALUE_THRESHOLD_DEFAULT 常量")
        return False
    v = float(m.group(1))
    if abs(v - 0.05) > 1e-9:
        print(f"    [FAIL] P_VALUE_THRESHOLD_DEFAULT={v} != 0.05")
        return False
    print(f"    [PASS] P_VALUE_THRESHOLD_DEFAULT = {v}")
    return True


def t06_bd087_p_value() -> bool:
    """t06: BD087_V30_FINAL_P_VALUE = 0.3827。"""
    txt = _read(M10T7_PY)
    m = re.search(r"BD087_V30_FINAL_P_VALUE\s*=\s*([\d.]+)", txt)
    if not m:
        print("    [FAIL] 缺 BD087_V30_FINAL_P_VALUE")
        return False
    v = float(m.group(1))
    if abs(v - 0.3827) > 1e-9:
        print(f"    [FAIL] BD087_V30_FINAL_P_VALUE={v} != 0.3827")
        return False
    print(f"    [PASS] BD087_V30_FINAL_P_VALUE = {v}")
    return True


def t07_bd087_u_stat() -> bool:
    """t07: BD087_V30_FINAL_U_STAT = 418.5。"""
    txt = _read(M10T7_PY)
    m = re.search(r"BD087_V30_FINAL_U_STAT\s*=\s*([\d.]+)", txt)
    if not m:
        print("    [FAIL] 缺 BD087_V30_FINAL_U_STAT")
        return False
    v = float(m.group(1))
    if abs(v - 418.5) > 1e-9:
        print(f"    [FAIL] BD087_V30_FINAL_U_STAT={v} != 418.5")
        return False
    print(f"    [PASS] BD087_V30_FINAL_U_STAT = {v}")
    return True


def t08_bd087_delta_hit_rate() -> bool:
    """t08: BD087_V30_FINAL_DELTA_HIT_RATE = -0.0645。"""
    txt = _read(M10T7_PY)
    m = re.search(r"BD087_V30_FINAL_DELTA_HIT_RATE\s*=\s*(-?[\d.]+)", txt)
    if not m:
        print("    [FAIL] 缺 BD087_V30_FINAL_DELTA_HIT_RATE")
        return False
    v = float(m.group(1))
    if abs(v - (-0.0645)) > 1e-9:
        print(f"    [FAIL] BD087_V30_FINAL_DELTA_HIT_RATE={v} != -0.0645")
        return False
    print(f"    [PASS] BD087_V30_FINAL_DELTA_HIT_RATE = {v}")
    return True


def t09_bd087_delta_f1() -> bool:
    """t09: BD087_V30_FINAL_DELTA_F1 = -0.0703。"""
    txt = _read(M10T7_PY)
    m = re.search(r"BD087_V30_FINAL_DELTA_F1\s*=\s*(-?[\d.]+)", txt)
    if not m:
        print("    [FAIL] 缺 BD087_V30_FINAL_DELTA_F1")
        return False
    v = float(m.group(1))
    if abs(v - (-0.0703)) > 1e-9:
        print(f"    [FAIL] BD087_V30_FINAL_DELTA_F1={v} != -0.0703")
        return False
    print(f"    [PASS] BD087_V30_FINAL_DELTA_F1 = {v}")
    return True


def t10_candidate_a_weights() -> bool:
    """t10: CANDIDATE_A_WEIGHTS 定义。"""
    txt = _read(M10T7_PY)
    if "CANDIDATE_A_WEIGHTS" not in txt:
        print("    [FAIL] 缺 CANDIDATE_A_WEIGHTS")
        return False
    if '"options": 0.25' not in txt and "'options': 0.25" not in txt:
        print("    [FAIL] CANDIDATE_A_WEIGHTS 缺 options=0.25")
        return False
    print("    [PASS] CANDIDATE_A_WEIGHTS 定义")
    return True


def t11_v10_default_weights() -> bool:
    """t11: V10_DEFAULT_WEIGHTS 定义。"""
    txt = _read(M10T7_PY)
    if "V10_DEFAULT_WEIGHTS" not in txt:
        print("    [FAIL] 缺 V10_DEFAULT_WEIGHTS")
        return False
    if '"options": 0.30' not in txt and "'options': 0.30" not in txt:
        print("    [FAIL] V10_DEFAULT_WEIGHTS 缺 options=0.30")
        return False
    print("    [PASS] V10_DEFAULT_WEIGHTS 定义")
    return True


def t12_bd087_decision() -> bool:
    """t12: BD087_V30_FINAL_DECISION = keep_v1.0。"""
    txt = _read(M10T7_PY)
    m = re.search(r'BD087_V30_FINAL_DECISION\s*=\s*"(.*?)"', txt)
    if not m:
        print("    [FAIL] 缺 BD087_V30_FINAL_DECISION")
        return False
    v = m.group(1)
    if v != "keep_v1.0":
        print(f"    [FAIL] BD087_V30_FINAL_DECISION={v} != keep_v1.0")
        return False
    print(f"    [PASS] BD087_V30_FINAL_DECISION = {v}")
    return True


def t13_evaluate_weight_switch_exists() -> bool:
    """t13: _evaluate_weight_switch 函数存在。"""
    txt = _read(M10T7_PY)
    if "def _evaluate_weight_switch(" not in txt:
        print("    [FAIL] 缺 _evaluate_weight_switch")
        return False
    print("    [PASS] _evaluate_weight_switch 函数")
    return True


def t14_evaluate_source_two() -> bool:
    """t14: source: compare_input / bd087_v30_final_default。"""
    txt = _read(M10T7_PY)
    sources = ['"compare_input"', '"bd087_v30_final_default"']
    missing = [s for s in sources if s not in txt]
    if missing:
        print(f"    [FAIL] source 缺:{missing}")
        return False
    print("    [PASS] source 双态齐全")
    return True


def t15_recommendation_two() -> bool:
    """t15: recommendation: switch_to_candidate_a / keep_v1.0。"""
    txt = _read(M10T7_PY)
    recs = ['"switch_to_candidate_a"', '"keep_v1.0"']
    missing = [r for r in recs if r not in txt]
    if missing:
        print(f"    [FAIL] recommendation 缺:{missing}")
        return False
    print("    [PASS] recommendation 双值齐全")
    return True


def t16_significant_judgment() -> bool:
    """t16: significant = p < p_threshold 判定。"""
    txt = _read(M10T7_PY)
    if "significant = p_value < p_threshold" not in txt:
        print("    [FAIL] 缺 significant = p_value < p_threshold")
        return False
    print("    [PASS] significant 判定")
    return True


def t17_vapid_env_names() -> bool:
    """t17: 4 VAPID 环境变量名。"""
    txt = _read(M10T7_PY)
    names = [
        'VAPID_PROD_PUBLIC = "VAPID_PUBLIC_KEY"',
        'VAPID_PROD_PRIVATE = "VAPID_PRIVATE_KEY"',
        'VAPID_SANDBOX_PUBLIC = "HR_VAPID_PUBLIC_KEY"',
        'VAPID_SANDBOX_PRIVATE = "HR_VAPID_PRIVATE_KEY"',
    ]
    missing = [n for n in names if n not in txt]
    if missing:
        print(f"    [FAIL] 4 VAPID env 名缺:{missing}")
        return False
    print("    [PASS] 4 VAPID 环境变量名齐全")
    return True


def t18_vapid_state_constants() -> bool:
    """t18: 4 VAPID 状态常量。"""
    txt = _read(M10T7_PY)
    states = [
        'VAPID_PROD_ONLY = "VAPID_PROD_ONLY"',
        'VAPID_SANDBOX_ONLY = "VAPID_SANDBOX_ONLY"',
        'VAPID_DUAL = "VAPID_DUAL"',
        'VAPID_NONE = "VAPID_NONE"',
    ]
    missing = [s for s in states if s not in txt]
    if missing:
        print(f"    [FAIL] 4 VAPID state 常量缺:{missing}")
        return False
    print("    [PASS] 4 VAPID state 常量齐全")
    return True


def t19_check_vapid_separator_exists() -> bool:
    """t19: _check_vapid_separator 函数存在。"""
    txt = _read(M10T7_PY)
    if "def _check_vapid_separator(" not in txt:
        print("    [FAIL] 缺 _check_vapid_separator")
        return False
    print("    [PASS] _check_vapid_separator 函数")
    return True


def t20_is_production_safe() -> bool:
    """t20: is_production_safe 判定。"""
    txt = _read(M10T7_PY)
    if "is_production_safe" not in txt:
        print("    [FAIL] 缺 is_production_safe")
        return False
    if "(VAPID_PROD_ONLY, VAPID_NONE)" not in txt:
        print("    [FAIL] 缺 is_production_safe 集合判定")
        return False
    print("    [PASS] is_production_safe 判定")
    return True


def t21_vapid_dual_warning() -> bool:
    """t21: VAPID_DUAL warning 文案。"""
    txt = _read(M10T7_PY)
    if "VAPID_DUAL" not in txt:
        print("    [FAIL] 缺 VAPID_DUAL")
        return False
    if "严重配置错" not in txt:
        print("    [FAIL] 缺 DUAL 严重警告文案")
        return False
    print("    [PASS] VAPID_DUAL warning 完整")
    return True


def t22_build_parser() -> bool:
    """t22: build_parser 函数 + 2 子命令解析。

    V1.5.5 接力期 m13t6 修复:m10t7_p2_merge.py L258-259 add_parser 跨行写法
    `p_ws = sub.add_parser(\\n        "weight-switch-eval",` 实际不在一行,
    原测试期望 `add_parser("weight-switch-eval"` 在同一行 → 误报 FAIL。
    改用正则 `add_parser\\s*\\(\\s*[\\'"]name[\\'"]` 接受任意空白(含换行)。
    """
    txt = _read(M10T7_PY)
    if "def build_parser()" not in txt:
        print("    [FAIL] 缺 build_parser")
        return False
    # V1.5.5 m13t6:接受 add_parser 跨行/单行写法
    if not re.search(r'add_parser\s*\(\s*[\'"]weight-switch-eval[\'"]', txt):
        print("    [FAIL] 缺 weight-switch-eval add_parser")
        return False
    if not re.search(r'add_parser\s*\(\s*[\'"]vapid-separator[\'"]', txt):
        print("    [FAIL] 缺 vapid-separator add_parser")
        return False
    print("    [PASS] build_parser 2 子命令")
    return True


def t23_p_threshold_arg() -> bool:
    """t23: --p-threshold 参数(可调阈值)。"""
    txt = _read(M10T7_PY)
    if "--p-threshold" not in txt:
        print("    [FAIL] 缺 --p-threshold 参数")
        return False
    print("    [PASS] --p-threshold 参数")
    return True


def t24_input_arg_default() -> bool:
    """t24: --input 参数 + 默认 BD-087-calibration-run-m7t4.json。"""
    txt = _read(M10T7_PY)
    if "--input" not in txt:
        print("    [FAIL] 缺 --input 参数")
        return False
    if "BD-087-calibration-run-m7t4.json" not in txt:
        print("    [FAIL] 缺默认输入路径")
        return False
    print("    [PASS] --input + 默认路径")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_m10t7_exists,
        t02_v152_marker,
        t03_weight_switch_subcommand,
        t04_vapid_separator_subcommand,
        t05_p_threshold_default,
        t06_bd087_p_value,
        t07_bd087_u_stat,
        t08_bd087_delta_hit_rate,
        t09_bd087_delta_f1,
        t10_candidate_a_weights,
        t11_v10_default_weights,
        t12_bd087_decision,
        t13_evaluate_weight_switch_exists,
        t14_evaluate_source_two,
        t15_recommendation_two,
        t16_significant_judgment,
        t17_vapid_env_names,
        t18_vapid_state_constants,
        t19_check_vapid_separator_exists,
        t20_is_production_safe,
        t21_vapid_dual_warning,
        t22_build_parser,
        t23_p_threshold_arg,
        t24_input_arg_default,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_m10t7_exists", t01_m10t7_exists),
    ("t02_v152_marker", t02_v152_marker),
    ("t03_weight_switch_subcommand", t03_weight_switch_subcommand),
    ("t04_vapid_separator_subcommand", t04_vapid_separator_subcommand),
    ("t05_p_threshold_default", t05_p_threshold_default),
    ("t06_bd087_p_value", t06_bd087_p_value),
    ("t07_bd087_u_stat", t07_bd087_u_stat),
    ("t08_bd087_delta_hit_rate", t08_bd087_delta_hit_rate),
    ("t09_bd087_delta_f1", t09_bd087_delta_f1),
    ("t10_candidate_a_weights", t10_candidate_a_weights),
    ("t11_v10_default_weights", t11_v10_default_weights),
    ("t12_bd087_decision", t12_bd087_decision),
    ("t13_evaluate_weight_switch_exists", t13_evaluate_weight_switch_exists),
    ("t14_evaluate_source_two", t14_evaluate_source_two),
    ("t15_recommendation_two", t15_recommendation_two),
    ("t16_significant_judgment", t16_significant_judgment),
    ("t17_vapid_env_names", t17_vapid_env_names),
    ("t18_vapid_state_constants", t18_vapid_state_constants),
    ("t19_check_vapid_separator_exists", t19_check_vapid_separator_exists),
    ("t20_is_production_safe", t20_is_production_safe),
    ("t21_vapid_dual_warning", t21_vapid_dual_warning),
    ("t22_build_parser", t22_build_parser),
    ("t23_p_threshold_arg", t23_p_threshold_arg),
    ("t24_input_arg_default", t24_input_arg_default),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M10-t7 V1.5.2 P2 合并工具自测(25 测点)")
    print("=" * 72)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"    [FAIL] {name} 异常:{type(exc).__name__}: {exc}")
            ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if not ok:
            failures += 1
    print("=" * 72)
    if failures == 0:
        print("[m10t7] V1.5.2 P2 合并工具 25/25 ALL PASSED")
        return 0
    print(f"[m10t7] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
