"""V1.5.7 接力期 m15t2 — 静态分析 self_test_harness 工具(C-6 候选)。

C-6 候选目的: 把 m9/m10/m11/m12/m15 各接力期静态自测脚本聚合到一个统一 harness 入口,
  - 自动发现 m*t*_test_*.py 脚本(glob 模式)
  - 配置化脚本列表(YAML/JSON/默认)
  - 串行/并行跑(默认串行,避免子进程污染 + 嵌套死锁)
  - V1.5.8 m16t3: --workers N 启用 ThreadPoolExecutor 并行(默认 1 串行,向后兼容)
  - V1.5.8 m16t3: --fail-fast 模式(第一个失败立即停止)
  - V1.5.8 m16t3: --output-format {json,html,csv} 多格式报告
  - 生成聚合报告(console + JSON)
  - 支持 filter(--pattern m11* 过滤)
  - 支持 verbose / quiet 模式
  - 支持 --skip-self 跳过 harness 自身测试(避免 m8t1 跑 m15t2 → m15t2 跑 m8t1 死锁)

调用:
  py -m scripts.self_test_harness                          # 默认全量
  py -m scripts.self_test_harness --pattern m15*          # 只跑 m15 接力期
  py -m scripts.self_test_harness --pattern m11t1 m11t3   # 只跑 m11t1 + m11t3
  py -m scripts.self_test_harness --report-json out.json  # JSON 报告(默认)
  py -m scripts.self_test_harness --report-format html --report-html out.html  # HTML 报告
  py -m scripts.self_test_harness --report-format csv --report-csv out.csv    # CSV 报告
  py -m scripts.self_test_harness --workers 4            # V1.5.8 m16t3: 4 worker 并行
  py -m scripts.self_test_harness --fail-fast            # V1.5.8 m16t3: 第一个失败立即停止
  py -m scripts.self_test_harness --quiet                 # 静默模式
  py -m scripts.self_test_harness --dry-run               # 只列出要跑的脚本

输出:
  stdout: 实时进度 + 汇总
  exit: 0 = 全部 pass / 1 = 有失败
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import io
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SCRIPTS = BACKEND / "scripts"

# 排除列表:聚合型脚本(自身是 runner,被 harness 调会嵌套)
AGGREGATOR_PATTERNS = {
    "m7t1_*",       # M5/M6/M7 聚合
    "m8t1_*",       # M8-t1 聚合 runner(核心)
    "m9t1_*",       # M9-t1 聚合
    "self_test_*",  # harness 自身
}

# 默认测试脚本列表(显式枚举,避免 glob 不可控)
DEFAULT_SCRIPTS: list[str] = [
    "m9t2_test_reviewer_signoff.py",
    "m9t3_test_reviewer_cli.py",
    "m9t4_test_edgar_endpoint.py",
    "m9t5_test_etf_endpoints.py",
    "m9t6_test_analytics_endpoints.py",
    "m9t7_test_openapi_v151.py",
    "m10t1_test_edgar_real.py",
    "m10t2_test_etf_real.py",
    "m10t3_test_openapi_v152.py",
    "m10t4_test_admin_role_audit.py",
    "m10t5_test_reviewer_cli_replace.py",
    "m10t6_test_p2_merge.py",
    "m10t7_test_p2_merge.py",
    "m10t8_test_v152_finalize.py",
    "m11t1_test_auth_all_export.py",
    "m11t2_test_admin_role_ip_integration.py",
    "m11t3_test_role_extension.py",
    "m11t4_test_reviewer_cli_toolchain.py",
    "m11t5_test_admin_endpoint_audit.py",
    "m11t6_test_v153_finalize.py",
    "m12t1_test_super_admin_role.py",
    "m12t2_test_m7t2_deletion.py",
    "m12t3_test_openapi_endpoint_review.py",
    "m15t1_test_freeze_automation.py",
    "m15t2_test_self_test_harness.py",  # harness 自身测试(可选)
]


@dataclass
class ScriptResult:
    """单个脚本的运行结果。"""

    script: str
    returncode: int = -1
    passed: bool = False
    elapsed_seconds: float = 0.0
    tail: str = ""
    error: str = ""


@dataclass
class HarnessReport:
    """harness 汇总报告。"""

    started_at_iso: str
    finished_at_iso: str
    total_scripts: int = 0
    passed_scripts: int = 0
    failed_scripts: int = 0
    total_elapsed_seconds: float = 0.0
    results: list[ScriptResult] = field(default_factory=list)
    pattern_filter: list[str] = field(default_factory=list)
    skipped_aggregators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "started_at_iso": self.started_at_iso,
            "finished_at_iso": self.finished_at_iso,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 3),
            "total_scripts": self.total_scripts,
            "passed_scripts": self.passed_scripts,
            "failed_scripts": self.failed_scripts,
            "pattern_filter": self.pattern_filter,
            "skipped_aggregators": self.skipped_aggregators,
            "results": [
                {
                    "script": r.script,
                    "returncode": r.returncode,
                    "passed": r.passed,
                    "elapsed_seconds": round(r.elapsed_seconds, 3),
                    "tail": r.tail,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def is_aggregator(script: str) -> bool:
    """判断是否为聚合型脚本(harness 会自动跳过)。"""
    for pat in AGGREGATOR_PATTERNS:
        if fnmatch.fnmatch(script, pat):
            return True
    return False


def _normalize_pattern(pat: str) -> str:
    """归一化 glob pattern:如果不含通配符,自动加 * 后缀(允许用户写 m12t1 而不是 m12t1*)。"""
    if any(c in pat for c in "*?["):
        return pat
    return pat + "*"


def filter_scripts(
    scripts: Iterable[str],
    patterns: list[str],
) -> tuple[list[str], list[str]]:
    """按 pattern 列表过滤脚本(支持 glob,如 m11* / m9t3)。

    返 (matched, skipped_aggregators)。
    V1.5.7 m15t2:pattern 不含通配符时自动加 * 后缀(用户友好)。
    """
    matched: list[str] = []
    skipped: list[str] = []
    normalized = [_normalize_pattern(p) for p in patterns]
    for s in scripts:
        if is_aggregator(s):
            skipped.append(s)
            continue
        if not normalized:
            matched.append(s)
            continue
        # 任一 pattern 匹配即选中
        if any(fnmatch.fnmatch(s, p) for p in normalized):
            matched.append(s)
    return matched, skipped


def run_one_script(script: str, timeout: int = 180) -> ScriptResult:
    """串行跑一个 m*t*_test_*.py 脚本,返 ScriptResult。"""
    path = SCRIPTS / script
    result = ScriptResult(script=script)
    if not path.exists():
        result.returncode = 2
        result.error = f"script missing: {path}"
        return result

    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-u", str(path)],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start
        result.elapsed_seconds = elapsed
        result.returncode = proc.returncode
        out_lines = (proc.stdout + proc.stderr).splitlines()
        result.tail = "\n".join(out_lines[-3:]) if out_lines else "(no output)"
        result.passed = proc.returncode == 0
    except subprocess.TimeoutExpired:
        result.elapsed_seconds = time.monotonic() - start
        result.returncode = 3
        result.tail = f"(timeout after {timeout}s)"
        result.error = "timeout"
    except Exception as exc:  # noqa: BLE001
        result.elapsed_seconds = time.monotonic() - start
        result.returncode = 4
        result.tail = f"(exception: {exc})"
        result.error = str(exc)
    return result


def run_harness(
    patterns: list[str],
    quiet: bool = False,
    dry_run: bool = False,
    skip_self: bool = False,
    workers: int = 1,
    fail_fast: bool = False,
    timeout: int = 180,
) -> HarnessReport:
    """harness 主流程: 过滤脚本 + 串行/并行跑 + 汇总报告。

    V1.5.8 m16t3 增强:
    - workers: > 1 时启用 ThreadPoolExecutor 并行(默认 1 串行)
    - fail_fast: True 时第一个失败后立即停止,不再跑后续脚本
    """
    started = datetime.now(timezone.utc)
    report = HarnessReport(
        started_at_iso=started.isoformat(),
        finished_at_iso="",
        pattern_filter=list(patterns),
    )

    # 1. 过滤
    candidates = list(DEFAULT_SCRIPTS)
    if skip_self:
        candidates = [s for s in candidates if s != "m15t2_test_self_test_harness.py"]
    matched, skipped = filter_scripts(candidates, patterns)
    report.skipped_aggregators = skipped
    report.total_scripts = len(matched)

    if not quiet:
        print("=" * 72, flush=True)
        print(
            f"self_test_harness — {len(matched)} 脚本 (skipped {len(skipped)} 聚合型, "
            f"workers={workers}, fail_fast={fail_fast})",
            flush=True,
        )
        print("=" * 72, flush=True)
        for s in matched:
            print(f"  [queued] {s}", flush=True)

    # V1.5.7 m15t2d 修复:dry-run return 必须在 `if not quiet:` 块外
    # 避免 quiet=True 时 dry-run 不 return 而继续跑子进程循环
    if dry_run:
        if not quiet:
            print(f"\n[dry-run] 不真跑,只列出 {len(matched)} 脚本", flush=True)
        report.finished_at_iso = datetime.now(timezone.utc).isoformat()
        return report

    # 2. 串行/并行跑
    if workers <= 1:
        # 串行(原 m15t2 行为, 向后兼容)
        for script in matched:
            if not quiet:
                print(f"\n--- {script} ---", flush=True)
            result = run_one_script(script, timeout=timeout)
            report.results.append(result)
            if result.passed:
                report.passed_scripts += 1
            else:
                report.failed_scripts += 1
            if not quiet:
                tag = "PASS" if result.passed else "FAIL"
                print(
                    f"  [{tag}] {script} rc={result.returncode} "
                    f"elapsed={result.elapsed_seconds:.2f}s",
                    flush=True,
                )
                if not result.passed:
                    print(f"    tail: {result.tail[:160]!r}", flush=True)
            # V1.5.8 m16t3: fail-fast 模式下,第一个失败后立即停
            if fail_fast and not result.passed:
                if not quiet:
                    print(f"\n[fail-fast] 第一个失败 {script},停止后续", flush=True)
                break
    else:
        # 并行(V1.5.8 m16t3)
        if not quiet:
            print(f"\n[parallel] {workers} workers, {len(matched)} 脚本", flush=True)
        results = _run_harness_parallel(matched, timeout=timeout, workers=workers)
        # 按输入顺序累加
        for result in results:
            report.results.append(result)
            if result.passed:
                report.passed_scripts += 1
            else:
                report.failed_scripts += 1
                if fail_fast:
                    if not quiet:
                        print(
                            f"\n[fail-fast] 检测到失败 {result.script},"
                            f"已完成的脚本将不再处理",
                            flush=True,
                        )
                    break

    finished = datetime.now(timezone.utc)
    report.finished_at_iso = finished.isoformat()
    report.total_elapsed_seconds = (finished - started).total_seconds()
    return report


def format_console_summary(report: HarnessReport) -> str:
    """格式化 console 输出汇总(单行 ONELINE-READY 字符串)。"""
    return (
        f"[harness] {report.passed_scripts}/{report.total_scripts} pass "
        f"({report.failed_scripts} fail) "
        f"elapsed={report.total_elapsed_seconds:.1f}s"
    )


# ----------------------------------------------------------------------
# V1.5.8 m16t3 增强:多格式报告(html / csv)
# ----------------------------------------------------------------------


def format_html_report(report: HarnessReport) -> str:
    """渲染 harness 报告为 HTML(V1.5.8 m16t3)。

    返回完整 HTML 文档(含 DOCTYPE / head / table)。
    """
    rows: list[str] = []
    for r in report.results:
        cls = "pass" if r.passed else "fail"
        rows.append(
            f"<tr class='{cls}'>"
            f"<td>{html_escape(r.script)}</td>"
            f"<td>{r.returncode}</td>"
            f"<td>{r.elapsed_seconds:.2f}</td>"
            f"<td>{'PASS' if r.passed else 'FAIL'}</td>"
            f"<td>{html_escape(r.tail[:120])}</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows) if rows else "<tr><td colspan='5'>(no results)</td></tr>"
    return (
        "<!DOCTYPE html>\n"
        "<html><head><meta charset='utf-8'>"
        "<title>self_test_harness report</title>"
        "<style>"
        "body{font-family:sans-serif;margin:24px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ccc;padding:6px 10px;text-align:left;}"
        "th{background:#f0f0f0;}"
        "tr.pass td{background:#e8f5e9;}"
        "tr.fail td{background:#ffebee;}"
        "</style></head><body>\n"
        f"<h1>self_test_harness report</h1>\n"
        f"<p>started: {report.started_at_iso}<br>finished: {report.finished_at_iso}<br>"
        f"total: {report.total_scripts} | pass: {report.passed_scripts} | "
        f"fail: {report.failed_scripts} | "
        f"elapsed: {report.total_elapsed_seconds:.2f}s</p>\n"
        "<table><thead><tr><th>script</th><th>rc</th><th>elapsed(s)</th>"
        "<th>status</th><th>tail</th></tr></thead><tbody>\n"
        f"{rows_html}\n"
        "</tbody></table>\n"
        "</body></html>\n"
    )


def format_csv_report(report: HarnessReport) -> str:
    """渲染 harness 报告为 CSV(V1.5.8 m16t3)。

    返回 CSV 文本(含 BOM 头, 以便 Excel 正确识别 UTF-8)。
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["script", "returncode", "elapsed_seconds", "passed", "tail", "error"])
    for r in report.results:
        writer.writerow([
            r.script,
            r.returncode,
            f"{r.elapsed_seconds:.3f}",
            "1" if r.passed else "0",
            r.tail,
            r.error,
        ])
    return buf.getvalue()


# ----------------------------------------------------------------------
# V1.5.8 m16t3 增强:ThreadPoolExecutor 并行
# ----------------------------------------------------------------------


def _run_harness_parallel(
    scripts: list[str],
    timeout: int,
    workers: int,
) -> list[ScriptResult]:
    """用 ThreadPoolExecutor 并行跑多个脚本(V1.5.8 m16t3)。

    返回按输入顺序排序的 ScriptResult 列表。
    workers=1 走串行路径(避免 ThreadPoolExecutor 开销)。
    """
    results: dict[str, ScriptResult] = {}

    if workers <= 1:
        for s in scripts:
            results[s] = run_one_script(s, timeout=timeout)
        return [results[s] for s in scripts]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_script = {
            ex.submit(run_one_script, s, timeout): s for s in scripts
        }
        for fut in as_completed(future_to_script):
            s = future_to_script[fut]
            try:
                results[s] = fut.result()
            except Exception as exc:  # noqa: BLE001
                # 线程内异常(理论上 run_one_script 内部已 catch,这里是双保险)
                sr = ScriptResult(script=s, returncode=4, passed=False, error=str(exc))
                results[s] = sr

    return [results[s] for s in scripts]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="self_test_harness",
        description="V1.5.7 静态分析 harness(C-6 候选): 统一聚合 m*t*_test_*.py",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        nargs="*",
        default=[],
        help="glob 过滤模式(可多次指定, 如 --pattern m11* m15t1)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="静默模式(只输出最终汇总 + JSON)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出要跑的脚本,不真跑",
    )
    parser.add_argument(
        "--skip-self",
        action="store_true",
        help="跳过 harness 自身测试(m15t2)避免嵌套死锁",
    )
    parser.add_argument(
        "--report-json",
        type=str,
        default=None,
        help="写 JSON 报告到指定路径(默认, 向后兼容)",
    )
    # V1.5.8 m16t3 增强 CLI
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=1,
        help="并行 worker 数(默认 1 串行, >1 启用 ThreadPoolExecutor)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="第一个失败后立即停止(串行/并行均生效)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="单脚本超时秒(默认 180s)",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "html", "csv"],
        default="json",
        help="报告输出格式(json/html/csv, 默认 json)",
    )
    parser.add_argument(
        "--report-html",
        type=str,
        default=None,
        help="HTML 报告输出路径(与 --output-format html 配合)",
    )
    parser.add_argument(
        "--report-csv",
        type=str,
        default=None,
        help="CSV 报告输出路径(与 --output-format csv 配合)",
    )
    args = parser.parse_args(argv)

    report = run_harness(
        patterns=args.pattern,
        quiet=args.quiet,
        dry_run=args.dry_run,
        skip_self=args.skip_self,
        workers=args.workers,
        fail_fast=args.fail_fast,
        timeout=args.timeout,
    )

    if not args.quiet:
        print("\n" + "=" * 72, flush=True)
        print(format_console_summary(report), flush=True)
        print("=" * 72, flush=True)

    # V1.5.8 m16t3:多格式报告落地
    fmt = args.output_format
    if fmt == "json":
        out_path = args.report_json
        if out_path:
            report_path = Path(out_path)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if not args.quiet:
                print(f"[harness] JSON 报告已写入 {report_path}", flush=True)
    elif fmt == "html":
        out_path = args.report_html
        if out_path:
            report_path = Path(out_path)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(format_html_report(report), encoding="utf-8")
            if not args.quiet:
                print(f"[harness] HTML 报告已写入 {report_path}", flush=True)
    elif fmt == "csv":
        out_path = args.report_csv
        if out_path:
            report_path = Path(out_path)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(format_csv_report(report), encoding="utf-8")
            if not args.quiet:
                print(f"[harness] CSV 报告已写入 {report_path}", flush=True)

    return 0 if report.failed_scripts == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
