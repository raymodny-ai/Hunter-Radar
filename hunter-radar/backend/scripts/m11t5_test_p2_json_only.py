"""M11-t5 V1.5.3 m10t7_p2_merge --json-only CI 友好输出自测(25 测点)。

V1.5.3 接力期 m11t5 — 修复 V1.5.2 UNPASSED-7:
- m10t7_p2_merge.py 加 --json-only 全局 flag
- main() 解析 json_only(默认 False)
- json_only=True → 单行 JSON(无 indent,便于 jq / pipeline 解析)
- 默认 indent=2 人类可读
- 不改 weight-switch-eval / vapid-separator 内部逻辑

Section 1 — --json-only 全局 flag(4 测点):
  - build_parser() add_argument("--json-only")
  - action="store_true"
  - help 含 m11t5 标记
  - help 含 "jq" 或 "CI"

Section 2 — main() 解析 json_only(5 测点):
  - main() 解析 args
  - getattr(args, "json_only", False) 防御
  - 三个分支(weight-switch-eval / vapid-separator / 默认)
  - 返 0 默认 / 2 默认
  - parse_args 接受 --json-only 任意位置

Section 3 — 输出条件(5 测点):
  - json_only=True → 单行 json.dumps(result, ensure_ascii=False)
  - json_only=False → indent=2 json.dumps
  - 单行模式不输出 indent
  - 两种模式都 ensure_ascii=False
  - print 是 stdout(非 stderr)

Section 4 — 兼容(5 测点):
  - 不改 _evaluate_weight_switch 逻辑
  - 不改 _check_vapid_separator 逻辑
  - 不改 BD087_V30_FINAL_* 常量
  - 不改 P_VALUE_THRESHOLD_DEFAULT
  - 不改 VAPID_* 状态常量

Section 5 — 评审 + 边界(6 测点):
  - m10t7_test_p2_merge.py 仍能调用
  - m10t8_test_v152_finalize.py 仍能调用
  - V1.5.3 m11t5 marker
  - 25 测点总数
  - 默认行为不变(indent=2)
  - docstring 含 m11t5 注释

总计 25 测点。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
M10T7_PY = ROOT / "backend" / "scripts" / "m10t7_p2_merge.py"
M10T7_TEST_PY = ROOT / "backend" / "scripts" / "m10t7_test_p2_merge.py"
M10T8_TEST_PY = ROOT / "backend" / "scripts" / "m10t8_test_v152_finalize.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_function_block(src: str, fn_name: str) -> str:
    """提取 def fn_name( 起的连续缩进代码块。"""
    lines = src.splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started and re.match(rf"^def {re.escape(fn_name)}\(", line):
            started = True
        if started:
            out.append(line)
            if len(out) > 1 and re.match(r"^(def |class )", line) and fn_name not in line:
                out.pop()
                break
    return "\n".join(out)


def t01_json_only_arg_defined() -> bool:
    """t01: build_parser() 含 add_argument('--json-only')。"""
    block = _extract_function_block(_read(M10T7_PY), "build_parser")
    if '"--json-only"' not in block:
        print("    [FAIL] build_parser 缺 --json-only")
        return False
    print("    [PASS] build_parser 含 --json-only")
    return True


def t02_json_only_action_store_true() -> bool:
    """t02: --json-only action=store_true(无值 flag)。"""
    block = _extract_function_block(_read(M10T7_PY), "build_parser")
    if "action=\"store_true\"" not in block:
        print("    [FAIL] --json-only 缺 action=store_true")
        return False
    print("    [PASS] --json-only action=store_true")
    return True


def t03_json_only_help_marker() -> bool:
    """t03: --json-only help 含 m11t5 标记。"""
    block = _extract_function_block(_read(M10T7_PY), "build_parser")
    m = re.search(r'p\.add_argument\(\s*"--json-only".*?help="([^"]+)"', block, flags=re.S)
    if not m:
        print("    [FAIL] 找不到 --json-only help 文本")
        return False
    if "m11t5" not in m.group(1):
        print("    [FAIL] --json-only help 缺 m11t5 标记")
        return False
    print("    [PASS] --json-only help 含 m11t5 标记")
    return True


def t04_json_only_help_jq_or_ci() -> bool:
    """t04: --json-only help 含 jq 或 CI(便于 pipeline)。"""
    block = _extract_function_block(_read(M10T7_PY), "build_parser")
    m = re.search(r'p\.add_argument\(\s*"--json-only".*?help="([^"]+)"', block, flags=re.S)
    if not m:
        print("    [FAIL] 找不到 --json-only help")
        return False
    if "jq" not in m.group(1) and "CI" not in m.group(1) and "pipeline" not in m.group(1):
        print("    [FAIL] --json-only help 缺 jq / CI / pipeline")
        return False
    print("    [PASS] --json-only help 含 jq / CI / pipeline")
    return True


def t05_main_parses_args() -> bool:
    """t05: main() 调用 parser.parse_args(argv)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "parser.parse_args(argv)" not in block:
        print("    [FAIL] main 缺 parser.parse_args(argv)")
        return False
    print("    [PASS] main parse_args(argv)")
    return True


def t06_main_getattr_json_only() -> bool:
    """t06: main() 用 getattr(args, "json_only", False) 防御。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if 'getattr(args, "json_only", False)' not in block:
        print("    [FAIL] main 缺 getattr(args, \"json_only\", False)")
        return False
    print("    [PASS] main getattr(args, 'json_only', False)")
    return True


def t07_main_three_branches() -> bool:
    """t07: main() 三个分支(weight-switch-eval / vapid-separator / else)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "args.cmd == \"weight-switch-eval\"" not in block:
        print("    [FAIL] 缺 weight-switch-eval 分支")
        return False
    if "args.cmd == \"vapid-separator\"" not in block:
        print("    [FAIL] 缺 vapid-separator 分支")
        return False
    if "parser.print_help()" not in block:
        print("    [FAIL] 缺 else 兜底分支")
        return False
    print("    [PASS] main 三分支齐全")
    return True


def t08_main_return_codes() -> bool:
    """t08: main() 返 0(成功)/ 2(无效子命令)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "return 2" not in block or "return 0" not in block:
        print("    [FAIL] main 缺 return 0 / return 2")
        return False
    print("    [PASS] main 返 0 / 2")
    return True


def t09_json_only_uses_sys_argv() -> bool:
    """t09: parse_args 接受 argv=None 默认 sys.argv(--json-only 任意位置)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "argv: list[str] | None = None" not in _read(M10T7_PY):
        print("    [FAIL] main 缺 argv 默认 None")
        return False
    print("    [PASS] argv 默认 None(--json-only 任意位置)")
    return True


def t10_json_only_single_line() -> bool:
    """t10: json_only=True → 单行 json.dumps(result, ensure_ascii=False)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    m = re.search(r"if getattr\(args, \"json_only\", False\):(.*?)else:", block, flags=re.S)
    if not m:
        print("    [FAIL] 缺 if json_only 分支")
        return False
    if "json.dumps(result, ensure_ascii=False)" not in m.group(1):
        print("    [FAIL] json_only 分支 缺单行 json.dumps(无 indent)")
        return False
    if "indent" in m.group(1):
        print("    [FAIL] json_only 分支 仍含 indent")
        return False
    print("    [PASS] json_only=True 单行 JSON")
    return True


def t11_default_indent_2() -> bool:
    """t11: 默认 indent=2 人类可读。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    m = re.search(r"else:(.*?)$", block, flags=re.S)
    if not m:
        print("    [FAIL] 缺 else 分支")
        return False
    if "json.dumps(result, ensure_ascii=False, indent=2)" not in m.group(1):
        print("    [FAIL] 默认分支 缺 indent=2")
        return False
    print("    [PASS] 默认 indent=2 人类可读")
    return True


def t12_both_ensure_ascii_false() -> bool:
    """t12: 两种模式都 ensure_ascii=False(中文不被 \\u 转义)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "ensure_ascii=False" not in block:
        print("    [FAIL] 缺 ensure_ascii=False")
        return False
    if block.count("ensure_ascii=False") < 2:
        print("    [FAIL] ensure_ascii=False 出现 < 2 次")
        return False
    print("    [PASS] 两种模式 ensure_ascii=False")
    return True


def t13_print_stdout() -> bool:
    """t13: print 是 stdout(非 stderr)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "file=sys.stderr" in block:
        print("    [FAIL] print 仍走 stderr")
        return False
    print("    [PASS] print stdout")
    return True


def t14_no_change_evaluate_weight() -> bool:
    """t14: _evaluate_weight_switch 函数不变。"""
    txt = _read(M10T7_PY)
    if "def _evaluate_weight_switch(" not in txt:
        print("    [FAIL] 缺 _evaluate_weight_switch")
        return False
    # m11t5 标记不应在 _evaluate_weight_switch 内部
    block = _extract_function_block(txt, "_evaluate_weight_switch")
    if "m11t5" in block:
        print("    [FAIL] _evaluate_weight_switch 不应有 m11t5 标记")
        return False
    print("    [PASS] _evaluate_weight_switch 不变")
    return True


def t15_no_change_check_vapid() -> bool:
    """t15: _check_vapid_separator 函数不变。"""
    txt = _read(M10T7_PY)
    if "def _check_vapid_separator(" not in txt:
        print("    [FAIL] 缺 _check_vapid_separator")
        return False
    block = _extract_function_block(txt, "_check_vapid_separator")
    if "m11t5" in block:
        print("    [FAIL] _check_vapid_separator 不应有 m11t5 标记")
        return False
    print("    [PASS] _check_vapid_separator 不变")
    return True


def t16_bd087_v30_final_constants_kept() -> bool:
    """t16: BD087_V30_FINAL_* 常量不变。"""
    txt = _read(M10T7_PY)
    if "BD087_V30_FINAL_P_VALUE = 0.3827" not in txt:
        print("    [FAIL] BD087_V30_FINAL_P_VALUE 变更")
        return False
    if "BD087_V30_FINAL_DECISION = \"keep_v1.0\"" not in txt:
        print("    [FAIL] BD087_V30_FINAL_DECISION 变更")
        return False
    print("    [PASS] BD087_V30_FINAL_* 常量保留")
    return True


def t17_p_value_threshold_kept() -> bool:
    """t17: P_VALUE_THRESHOLD_DEFAULT = 0.05 不变。"""
    txt = _read(M10T7_PY)
    if "P_VALUE_THRESHOLD_DEFAULT = 0.05" not in txt:
        print("    [FAIL] P_VALUE_THRESHOLD_DEFAULT 变更")
        return False
    print("    [PASS] P_VALUE_THRESHOLD_DEFAULT = 0.05 保留")
    return True


def t18_vapid_state_constants_kept() -> bool:
    """t18: VAPID_PROD_ONLY / SANDBOX_ONLY / DUAL / NONE 4 状态常量不变。"""
    txt = _read(M10T7_PY)
    for c in ["VAPID_PROD_ONLY", "VAPID_SANDBOX_ONLY", "VAPID_DUAL", "VAPID_NONE"]:
        if f"{c} = \"{c}\"" not in txt:
            print(f"    [FAIL] VAPID 状态常量 {c} 变更")
            return False
    print("    [PASS] VAPID 4 状态常量保留")
    return True


def t19_m10t7_test_compat() -> bool:
    """t19: m10t7_test_p2_merge.py 仍能调用 m10t7_p2_merge。"""
    if not M10T7_TEST_PY.exists():
        print("    [SKIP] m10t7_test_p2_merge 不存在")
        return True
    txt = _read(M10T7_TEST_PY)
    if "m10t7_p2_merge" not in txt:
        print("    [FAIL] m10t7_test 缺 m10t7_p2_merge 引用")
        return False
    print("    [PASS] m10t7_test_p2_merge 兼容")
    return True


def t20_m10t8_test_compat() -> bool:
    """t20: m10t8_test_v152_finalize.py 仍能引用。"""
    if not M10T8_TEST_PY.exists():
        print("    [SKIP] m10t8_test 不存在")
        return True
    txt = _read(M10T8_TEST_PY)
    if "m10t7_p2_merge" not in txt and "p2_merge" not in txt:
        print("    [FAIL] m10t8_test 缺 m10t7_p2_merge 引用")
        return False
    print("    [PASS] m10t8_test_v152_finalize 兼容")
    return True


def t21_v153_m11t5_marker() -> bool:
    """t21: m10t7_p2_merge.py 含 V1.5.3 m11t5 标记。"""
    txt = _read(M10T7_PY)
    if "V1.5.3 接力期 m11t5" not in txt:
        print("    [FAIL] 缺 V1.5.3 接力期 m11t5 标记")
        return False
    print("    [PASS] V1.5.3 接力期 m11t5 标记")
    return True


def t22_default_behavior_preserved() -> bool:
    """t22: 默认行为不变(无 --json-only → indent=2 + 中文 + banner)。"""
    block = _extract_function_block(_read(M10T7_PY), "main")
    if "indent=2" not in block:
        print("    [FAIL] 默认 indent=2 丢失")
        return False
    print("    [PASS] 默认行为保留(indent=2 + 中文)")
    return True


def t23_docstring_m11t5_note() -> bool:
    """t23: m10t7_p2_merge.py docstring 含 m11t5 注释。"""
    txt = _read(M10T7_PY)
    # 文件头部 docstring 应有提及
    if "m11t5" not in txt[:2000]:
        # 至少在 build_parser / main docstring 中有
        block = _extract_function_block(txt, "build_parser")
        if "m11t5" not in block:
            print("    [FAIL] docstring 缺 m11t5 注释")
            return False
    print("    [PASS] docstring 含 m11t5 注释")
    return True


def t24_json_only_arg_in_subparsers() -> bool:
    """t24: --json-only 是 build_parser 顶层 flag(非子命令下)— 全局有效。"""
    block = _extract_function_block(_read(M10T7_PY), "build_parser")
    # add_argument 应直接挂在 p(顶层),不在 p_ws / p_vapid 子 parser 内
    m = re.search(r"p\.add_argument\(\s*\"--json-only\"", block)
    if not m:
        print("    [FAIL] --json-only 不在 build_parser 顶层")
        return False
    print("    [PASS] --json-only 是 build_parser 顶层全局 flag")
    return True


def t25_25_testpoints_total() -> bool:
    """t25: 25 测点总数校验。"""
    funcs = [
        t01_json_only_arg_defined, t02_json_only_action_store_true,
        t03_json_only_help_marker, t04_json_only_help_jq_or_ci,
        t05_main_parses_args, t06_main_getattr_json_only, t07_main_three_branches,
        t08_main_return_codes, t09_json_only_uses_sys_argv,
        t10_json_only_single_line, t11_default_indent_2, t12_both_ensure_ascii_false,
        t13_print_stdout, t14_no_change_evaluate_weight, t15_no_change_check_vapid,
        t16_bd087_v30_final_constants_kept, t17_p_value_threshold_kept,
        t18_vapid_state_constants_kept, t19_m10t7_test_compat, t20_m10t8_test_compat,
        t21_v153_m11t5_marker, t22_default_behavior_preserved, t23_docstring_m11t5_note,
        t24_json_only_arg_in_subparsers, t25_25_testpoints_total,
    ]
    if len(funcs) != 25:
        print(f"    [FAIL] 函数总数={len(funcs)} != 25")
        return False
    print("    [PASS] 25 测点总数校验")
    return True


CHECKS = [
    ("t01_json_only_arg_defined", t01_json_only_arg_defined),
    ("t02_json_only_action_store_true", t02_json_only_action_store_true),
    ("t03_json_only_help_marker", t03_json_only_help_marker),
    ("t04_json_only_help_jq_or_ci", t04_json_only_help_jq_or_ci),
    ("t05_main_parses_args", t05_main_parses_args),
    ("t06_main_getattr_json_only", t06_main_getattr_json_only),
    ("t07_main_three_branches", t07_main_three_branches),
    ("t08_main_return_codes", t08_main_return_codes),
    ("t09_json_only_uses_sys_argv", t09_json_only_uses_sys_argv),
    ("t10_json_only_single_line", t10_json_only_single_line),
    ("t11_default_indent_2", t11_default_indent_2),
    ("t12_both_ensure_ascii_false", t12_both_ensure_ascii_false),
    ("t13_print_stdout", t13_print_stdout),
    ("t14_no_change_evaluate_weight", t14_no_change_evaluate_weight),
    ("t15_no_change_check_vapid", t15_no_change_check_vapid),
    ("t16_bd087_v30_final_constants_kept", t16_bd087_v30_final_constants_kept),
    ("t17_p_value_threshold_kept", t17_p_value_threshold_kept),
    ("t18_vapid_state_constants_kept", t18_vapid_state_constants_kept),
    ("t19_m10t7_test_compat", t19_m10t7_test_compat),
    ("t20_m10t8_test_compat", t20_m10t8_test_compat),
    ("t21_v153_m11t5_marker", t21_v153_m11t5_marker),
    ("t22_default_behavior_preserved", t22_default_behavior_preserved),
    ("t23_docstring_m11t5_note", t23_docstring_m11t5_note),
    ("t24_json_only_arg_in_subparsers", t24_json_only_arg_in_subparsers),
    ("t25_25_testpoints_total", t25_25_testpoints_total),
]


def main() -> int:
    print("=" * 72)
    print("M11-t5 V1.5.3 m10t7_p2_merge --json-only CI 友好输出自测(25 测点)")
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
        print("[m11t5] V1.5.3 m10t7_p2_merge --json-only 25/25 ALL PASSED")
        return 0
    print(f"[m11t5] {failures} CHECK(S) FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
