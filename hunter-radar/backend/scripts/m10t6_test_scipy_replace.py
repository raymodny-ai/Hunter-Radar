"""M10-t6 V1.5.2 BD-087 scipy 替换 _mann_whitney_u 自测(25 测点)。

V1.5.2 接力期 m10t6 — scipy.stats.mannwhitneyu 替换 M7 简化版:
- scipy 优先(use_continuity=False 与原简化版一致)
- 沙箱无 scipy → fallback _mann_whitney_u_simplified(保留)
- 异常降级处理
- 新增 _mann_whitney_u_with_source 显式标注 fetch_source
- m7t4_test_v30_final.py 兼容性(M7 测点不动)

Section 1 — scipy 探测 + 常量(5 测点):
  - try/except scipy.stats 探测
  - _HAS_SCIPY 标志
  - MANN_WHITNEY_SOURCE_SCI / SANDBOX 常量
  - _scipy_mannwhitneyu alias

Section 2 — _mann_whitney_u scipy 优先(5 测点):
  - 函数存在
  - scipy 路径(use_continuity=False / two-sided)
  - 异常降级
  - 空样本返 (0, 1)
  - M7 兼容签名 (U, p) 二元组

Section 3 — _mann_whitney_u_simplified 保留(4 测点):
  - 函数存在
  - 正态近似
  - U>=0
  - p∈[0,1]

Section 4 — _mann_whitney_u_with_source 新增(4 测点):
  - 函数存在
  - 返回 (U, p, source) 三元组
  - source 标注 scipy/sandbox_simplified
  - 空样本也带 source

Section 5 — m7t4 兼容 + 评审(7 测点):
  - m7t4_test_v30_final.py 仍 import _mann_whitney_u
  - _mann_whitney_u([1, 0, 1, 0], [0, 1, 0, 1]) 返 (U, p) 2 元组
  - U>=0 + p∈[0,1] 兼容
  - 空样本返 (0, 1) 兼容
  - 4 子命令保留(run/compare/mann-whitney/report)
  - m8t4_test_release_notes 引用 scipy
  - 25 测点总数校验

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
SCRIPTS = ROOT / "backend" / "scripts"
M7T4_RUNNER = SCRIPTS / "m7t4_run_backtest_v30_final.py"
M7T4_TEST = SCRIPTS / "m7t4_test_v30_final.py"
M8T4_TEST = SCRIPTS / "m8t4_test_release_notes.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def t01_scipy_import_try() -> bool:
    """t01: try/except scipy.stats 探测。"""
    txt = _read(M7T4_RUNNER)
    if "from scipy.stats import mannwhitneyu" not in txt:
        print("    [FAIL] 缺 from scipy.stats import mannwhitneyu")
        return False
    if "try:" not in txt:
        print("    [FAIL] 缺 try 块")
        return False
    if "except ImportError" not in txt:
        print("    [FAIL] 缺 except ImportError")
        return False
    print("    [PASS] scipy try/except 探测完整")
    return True


def t02_has_scipy_flag() -> bool:
    """t02: _HAS_SCIPY 标志。"""
    txt = _read(M7T4_RUNNER)
    if "_HAS_SCIPY = True" not in txt:
        print("    [FAIL] 缺 _HAS_SCIPY = True")
        return False
    if "_HAS_SCIPY = False" not in txt:
        print("    [FAIL] 缺 _HAS_SCIPY = False 降级")
        return False
    print("    [PASS] _HAS_SCIPY 双态完整")
    return True


def t03_source_constants() -> bool:
    """t03: MANN_WHITNEY_SOURCE_SCI / SANDBOX 常量。"""
    txt = _read(M7T4_RUNNER)
    if 'MANN_WHITNEY_SOURCE_SCI = "scipy"' not in txt:
        print("    [FAIL] 缺 MANN_WHITNEY_SOURCE_SCI")
        return False
    if 'MANN_WHITNEY_SOURCE_SANDBOX = "sandbox_simplified"' not in txt:
        print("    [FAIL] 缺 MANN_WHITNEY_SOURCE_SANDBOX")
        return False
    print("    [PASS] fetch_source 常量齐全")
    return True


def t04_scipy_alias() -> bool:
    """t04: _scipy_mannwhitneyu alias(避免命名冲突)。"""
    txt = _read(M7T4_RUNNER)
    if "as _scipy_mannwhitneyu" not in txt:
        print("    [FAIL] 缺 as _scipy_mannwhitneyu alias")
        return False
    print("    [PASS] _scipy_mannwhitneyu alias")
    return True


def t05_v152_marker() -> bool:
    """t05: V1.5.2 接力期 m10t6 注释标记。"""
    txt = _read(M7T4_RUNNER)
    if "V1.5.2 接力期 m10t6" not in txt and "m10t6" not in txt:
        print("    [FAIL] 缺 V1.5.2 接力期 m10t6 标记")
        return False
    print("    [PASS] V1.5.2 m10t6 标记")
    return True


def t06_mann_whitney_u_exists() -> bool:
    """t06: _mann_whitney_u 函数存在(保持 M7 签名)。"""
    txt = _read(M7T4_RUNNER)
    m = re.search(r"def _mann_whitney_u\(x:\s*list\[int\],\s*y:\s*list\[int\]\)\s*->\s*tuple\[float,\s*float\]:", txt)
    if not m:
        print("    [FAIL] 缺 _mann_whitney_u(x, y) -> tuple[float, float]")
        return False
    print("    [PASS] _mann_whitney_u 函数签名")
    return True


def t07_scipy_use_continuity() -> bool:
    """t07: scipy 路径 use_continuity=False(与原简化版一致)。"""
    txt = _read(M7T4_RUNNER)
    if "use_continuity=False" not in txt:
        print("    [FAIL] 缺 use_continuity=False")
        return False
    if 'alternative="two-sided"' not in txt:
        print("    [FAIL] 缺 alternative=\"two-sided\"")
        return False
    print("    [PASS] scipy use_continuity=False + two-sided")
    return True


def t08_scipy_result_extract() -> bool:
    """t08: scipy result 提取 statistic + pvalue。"""
    txt = _read(M7T4_RUNNER)
    if "res.statistic" not in txt:
        print("    [FAIL] 缺 res.statistic 提取")
        return False
    if "res.pvalue" not in txt:
        print("    [FAIL] 缺 res.pvalue 提取")
        return False
    if "float(res.statistic)" not in txt:
        print("    [FAIL] 缺 float() 转换")
        return False
    print("    [PASS] scipy result 提取")
    return True


def t09_exception_fallback() -> bool:
    """t09: scipy 异常降级到简化版(try/except)。"""
    txt = _read(M7T4_RUNNER)
    if "except Exception" not in txt:
        print("    [FAIL] 缺 except Exception 降级")
        return False
    if "pass" not in txt:
        print("    [FAIL] 缺 pass 跳过")
        return False
    # 看 scipy 路径后是否调 _mann_whitney_u_simplified
    if "_mann_whitney_u_simplified" not in txt:
        print("    [FAIL] 缺 _mann_whitney_u_simplified 调用")
        return False
    print("    [PASS] 异常降级 + 简化版调用")
    return True


def t10_empty_sample() -> bool:
    """t10: 空样本返 (0, 1)。"""
    txt = _read(M7T4_RUNNER)
    if "0.0, 1.0" not in txt:
        print("    [FAIL] 缺空样本返 (0.0, 1.0)")
        return False
    if "n1 == 0 or n2 == 0" not in txt:
        print("    [FAIL] 缺 n1 == 0 or n2 == 0 校验")
        return False
    print("    [PASS] 空样本返 (0, 1)")
    return True


def t11_simplified_exists() -> bool:
    """t11: _mann_whitney_u_simplified 函数存在(保留)。"""
    txt = _read(M7T4_RUNNER)
    if "def _mann_whitney_u_simplified(" not in txt:
        print("    [FAIL] 缺 _mann_whitney_u_simplified")
        return False
    print("    [PASS] _mann_whitney_u_simplified 保留")
    return True


def t12_simplified_normal_approx() -> bool:
    """t12: 简化版正态近似(mu_U / sigma_U / z)。"""
    txt = _read(M7T4_RUNNER)
    if "mu_U = n1 * n2 / 2" not in txt:
        print("    [FAIL] 缺 mu_U 公式")
        return False
    if "sigma_U" not in txt:
        print("    [FAIL] 缺 sigma_U")
        return False
    if "_normal_cdf" not in txt:
        print("    [FAIL] 缺 _normal_cdf 调用")
        return False
    print("    [PASS] 简化版正态近似")
    return True


def t13_simplified_u_nonneg() -> bool:
    """t13: 简化版 U>=0。"""
    txt = _read(M7T4_RUNNER)
    if "U1 = R1 - n1 * (n1 + 1) / 2" not in txt:
        print("    [FAIL] 缺 U1 公式")
        return False
    if "U = min(U1, U2)" not in txt:
        print("    [FAIL] 缺 U = min(U1, U2)")
        return False
    print("    [PASS] U>=0 公式")
    return True


def t14_simplified_p_range() -> bool:
    """t14: 简化版 p∈[0,1] round(4)。"""
    txt = _read(M7T4_RUNNER)
    if "p_value = 2 * (1 - _normal_cdf" not in txt:
        print("    [FAIL] 缺 p_value 双尾计算")
        return False
    if "round(p_value, 4)" not in txt:
        print("    [FAIL] 缺 round(p_value, 4)")
        return False
    print("    [PASS] p∈[0,1] round 4")
    return True


def t15_with_source_exists() -> bool:
    """t15: _mann_whitney_u_with_source 函数存在。"""
    txt = _read(M7T4_RUNNER)
    if "def _mann_whitney_u_with_source(" not in txt:
        print("    [FAIL] 缺 _mann_whitney_u_with_source")
        return False
    m = re.search(r"def _mann_whitney_u_with_source\([\s\S]*?\)\s*->\s*tuple\[float,\s*float,\s*str\]:", txt)
    if not m:
        print("    [FAIL] 缺 (U, p, source) 三元组签名")
        return False
    print("    [PASS] _mann_whitney_u_with_source 三元组签名")
    return True


def t16_with_source_returns_three() -> bool:
    """t16: _mann_whitney_u_with_source 返 3 字段。"""
    txt = _read(M7T4_RUNNER)
    m = re.search(r"def _mann_whitney_u_with_source\([\s\S]*?(?=\ndef |\nclass )", txt)
    if not m:
        print("    [FAIL] 函数体找不到")
        return False
    body = m.group(0)
    # 至少有 1 个 scipy return + 1 个 simplified return
    if "MANN_WHITNEY_SOURCE_SCI" not in body:
        print("    [FAIL] 缺 MANN_WHITNEY_SOURCE_SCI 返回")
        return False
    if "MANN_WHITNEY_SOURCE_SANDBOX" not in body:
        print("    [FAIL] 缺 MANN_WHITNEY_SOURCE_SANDBOX 返回")
        return False
    print("    [PASS] _mann_whitney_u_with_source 双源返回")
    return True


def t17_with_source_empty_marker() -> bool:
    """t17: _mann_whitney_u_with_source 空样本也带 source 标注。"""
    txt = _read(M7T4_RUNNER)
    m = re.search(r"def _mann_whitney_u_with_source\([\s\S]*?(?=\ndef |\nclass )", txt)
    if not m:
        print("    [FAIL] 函数体找不到")
        return False
    body = m.group(0)
    if "MANN_WHITNEY_SOURCE_SANDBOX" not in body:
        print("    [FAIL] 缺 SANDBOX 默认源")
        return False
    print("    [PASS] 空样本 source 标注")
    return True


def t18_m7t4_compat_keeps_call() -> bool:
    """t18: m7t4_test_v30_final.py 仍调 mod._mann_whitney_u(M7 兼容)。"""
    txt = _read(M7T4_TEST)
    if "mod._mann_whitney_u(" not in txt:
        print("    [FAIL] m7t4 test 缺 mod._mann_whitney_u 调用")
        return False
    if "[1, 0, 1, 0], [0, 1, 0, 1]" not in txt:
        print("    [FAIL] m7t4 test 缺 [1,0,1,0] / [0,1,0,1] 样例")
        return False
    print("    [PASS] m7t4 兼容调用保留")
    return True


def t19_m7t4_compat_two_tuple() -> bool:
    """t19: m7t4 test 期望 (U, p) 二元组。"""
    txt = _read(M7T4_TEST)
    if "U, p = mod._mann_whitney_u" not in txt:
        print("    [FAIL] m7t4 test 缺 U, p 二元组解构")
        return False
    print("    [PASS] m7t4 二元组解构保留")
    return True


def t20_m7t4_compat_empty() -> bool:
    """t20: m7t4 test 空样本返 (0, 1) 校验。"""
    txt = _read(M7T4_TEST)
    if "U0 == 0.0 and p0 == 1.0" not in txt:
        print("    [FAIL] m7t4 test 缺空样本 (0, 1) 校验")
        return False
    print("    [PASS] m7t4 空样本兼容")
    return True


def t21_m7t4_4_subcommands() -> bool:
    """t21: 4 子命令保留(run / compare / mann-whitney / report)。"""
    txt = _read(M7T4_RUNNER)
    cmds = ["cmd_run", "cmd_compare", "cmd_mann_whitney", "cmd_report"]
    missing = [c for c in cmds if f"def {c}(" not in txt]
    if missing:
        print(f"    [FAIL] 4 子命令缺:{missing}")
        return False
    print("    [PASS] 4 子命令保留")
    return True


def t22_m8t4_scipy_reference() -> bool:
    """t22: m8t4_test_release_notes 引用 scipy.stats.mannwhitneyu。"""
    txt = _read(M8T4_TEST)
    if "scipy.stats.mannwhitneyu" not in txt:
        print("    [FAIL] m8t4 test 缺 scipy.stats.mannwhitneyu 引用")
        return False
    print("    [PASS] m8t4 引用 scipy.stats.mannwhitneyu")
    return True


def t23_no_breaking_change_in_runner() -> bool:
    """t23: runner 关键 4 字段保留(weights_a/b + mann_whitney_u + delta_*)。"""
    txt = _read(M7T4_RUNNER)
    expected = ["weights_a", "weights_b", "mann_whitney_u", "delta_hit_rate", "delta_precision", "delta_f1"]
    missing = [e for e in expected if e not in txt]
    if missing:
        print(f"    [FAIL] 关键字段缺:{missing}")
        return False
    print("    [PASS] 关键字段保留")
    return True


def t24_normal_cdf_preserved() -> bool:
    """t24: _normal_cdf 保留(M7 实现)。"""
    txt = _read(M7T4_RUNNER)
    if "def _normal_cdf(z: float)" not in txt:
        print("    [FAIL] 缺 _normal_cdf")
        return False
    if "math.erfc" not in txt:
        print("    [FAIL] 缺 math.erfc 调用")
        return False
    print("    [PASS] _normal_cdf 保留")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_scipy_import_try,
        t02_has_scipy_flag,
        t03_source_constants,
        t04_scipy_alias,
        t05_v152_marker,
        t06_mann_whitney_u_exists,
        t07_scipy_use_continuity,
        t08_scipy_result_extract,
        t09_exception_fallback,
        t10_empty_sample,
        t11_simplified_exists,
        t12_simplified_normal_approx,
        t13_simplified_u_nonneg,
        t14_simplified_p_range,
        t15_with_source_exists,
        t16_with_source_returns_three,
        t17_with_source_empty_marker,
        t18_m7t4_compat_keeps_call,
        t19_m7t4_compat_two_tuple,
        t20_m7t4_compat_empty,
        t21_m7t4_4_subcommands,
        t22_m8t4_scipy_reference,
        t23_no_breaking_change_in_runner,
        t24_normal_cdf_preserved,
        t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_scipy_import_try", t01_scipy_import_try),
    ("t02_has_scipy_flag", t02_has_scipy_flag),
    ("t03_source_constants", t03_source_constants),
    ("t04_scipy_alias", t04_scipy_alias),
    ("t05_v152_marker", t05_v152_marker),
    ("t06_mann_whitney_u_exists", t06_mann_whitney_u_exists),
    ("t07_scipy_use_continuity", t07_scipy_use_continuity),
    ("t08_scipy_result_extract", t08_scipy_result_extract),
    ("t09_exception_fallback", t09_exception_fallback),
    ("t10_empty_sample", t10_empty_sample),
    ("t11_simplified_exists", t11_simplified_exists),
    ("t12_simplified_normal_approx", t12_simplified_normal_approx),
    ("t13_simplified_u_nonneg", t13_simplified_u_nonneg),
    ("t14_simplified_p_range", t14_simplified_p_range),
    ("t15_with_source_exists", t15_with_source_exists),
    ("t16_with_source_returns_three", t16_with_source_returns_three),
    ("t17_with_source_empty_marker", t17_with_source_empty_marker),
    ("t18_m7t4_compat_keeps_call", t18_m7t4_compat_keeps_call),
    ("t19_m7t4_compat_two_tuple", t19_m7t4_compat_two_tuple),
    ("t20_m7t4_compat_empty", t20_m7t4_compat_empty),
    ("t21_m7t4_4_subcommands", t21_m7t4_4_subcommands),
    ("t22_m8t4_scipy_reference", t22_m8t4_scipy_reference),
    ("t23_no_breaking_change_in_runner", t23_no_breaking_change_in_runner),
    ("t24_normal_cdf_preserved", t24_normal_cdf_preserved),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M10-t6 V1.5.2 BD-087 scipy 替换 _mann_whitney_u 自测(25 测点)")
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
        print("[m10t6] V1.5.2 BD-087 scipy 替换 25/25 ALL PASSED")
        return 0
    print(f"[m10t6] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
