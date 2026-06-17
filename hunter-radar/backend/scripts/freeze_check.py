"""V1.5.7 接力期 m15t1 — OpenAPI freeze 自动化校验工具(C-3 候选)。

C-3 候选目的: 每次 V 版本 freeze 时,自动校验:
  1. freeze_version 字符串匹配 V 版本
  2. endpoints_total 端点总数(默认 56)
  3. super_admin_endpoints 列表非空(V1.5.4+)
  4. endpoint_review_meta 完整性(4 admin + 1 catch_all)
  5. v*_relay_tasks 全部 COMPLETE
  6. status = ONLINE-READY
  7. m8t1 跑全量 0 失败(子进程)
  8. 4 admin 端点 docstring 含 REVIEW META 段
  9. 校验通过后输出 JSON 报告 + Markdown 报告

V1.5.8 m16t4 增强: freeze diff 增量校验
  - --diff 模式对比 prev / curr 两个 freeze JSON
  - 检测 added / removed / changed 端点
  - 输出 diff 报告 docs/freeze-diff-report-{prev}_to_{curr}.{json,md}

调用:
  py -m scripts.freeze_check                          # 默认 v1.5.4 (9 校验)
  py -m scripts.freeze_check --version v1.5.5        # 自定义版本
  py -m scripts.freeze_check --skip-m8t1             # 跳过 m8t1 子进程
  py -m scripts.freeze_check --diff --prev v1.5.4 --curr v1.5.5   # diff 模式

输出:
  9 校验模式:
    docs/freeze-check-report-{version}.json   (机器可读)
    docs/freeze-check-report-{version}.md     (人可读)
  diff 模式(V1.5.8 m16t4):
    docs/freeze-diff-report-{prev}_to_{curr}.json
    docs/freeze-diff-report-{prev}_to_{curr}.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BACKEND = ROOT / "backend"
SCRIPTS = BACKEND / "scripts"
ADMIN_PY = BACKEND / "app" / "api" / "admin.py"
M8T1_PY = SCRIPTS / "m8t1_test_regression.py"

# 4 admin 端点函数名(V1.5.4+ 需含 REVIEW META 段)
ADMIN_ENDPOINTS = [
    "post_etl_run",
    "post_backtest_run",
    "get_backtest_result",
    "post_webhook_replay",
]
REVIEW_META_HEADER = "### REVIEW META"


# ----------------------------------------------------------------------
# 9 项校验
# ----------------------------------------------------------------------


def check_freeze_doc_exists(version: str) -> tuple[bool, str]:
    """§1 freeze_version 双文档(openapi-frozen-{version}.md + .json)存在。"""
    md = DOCS / f"openapi-frozen-{version}.md"
    js = DOCS / f"openapi-frozen-{version}.json"
    if not md.is_file():
        return False, f"缺 {md.name}"
    if not js.is_file():
        return False, f"缺 {js.name}"
    return True, f"{md.name} + {js.name} 均存在"


def check_freeze_version_field(version: str) -> tuple[bool, str]:
    """§2 JSON 顶字段 freeze_version 匹配 V 版本。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    try:
        data = json.loads(js.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"JSON 解析失败: {exc}"
    if data.get("freeze_version") != version:
        return False, f"freeze_version={data.get('freeze_version')!r} != {version!r}"
    return True, f"freeze_version={version}"


def check_endpoints_total(version: str, expected: int = 56) -> tuple[bool, str]:
    """§3 endpoints_total == expected(默认 56)。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    data = json.loads(js.read_text(encoding="utf-8"))
    actual = data.get("endpoints_total")
    if actual != expected:
        return False, f"endpoints_total={actual} != {expected}"
    return True, f"endpoints_total={actual}"


def check_super_admin_endpoints(version: str) -> tuple[bool, str]:
    """§4 super_admin_endpoints 列表(V1.5.4+ 至少 1 个,/admin/webhook/replay)。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    data = json.loads(js.read_text(encoding="utf-8"))
    sa_list = data.get("super_admin_endpoints", [])
    if not sa_list:
        return False, "super_admin_endpoints 为空"
    if "/api/v1/admin/webhook/replay" not in sa_list:
        return False, f"super_admin_endpoints 缺 /admin/webhook/replay: {sa_list}"
    return True, f"super_admin_endpoints={sa_list}"


def check_endpoint_review_meta(version: str) -> tuple[bool, str]:
    """§5 endpoint_review_meta 完整性(4 admin + 1 catch_all)。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    data = json.loads(js.read_text(encoding="utf-8"))
    meta = data.get("endpoint_review_meta", [])
    # 4 admin 端点 + 1 catch_all
    admin_in_meta = sum(
        1 for m in meta
        if m.get("endpoint", "").startswith("/api/v1/admin/")
    )
    catch_all_in_meta = sum(1 for m in meta if m.get("catch_all") is True)
    if admin_in_meta < 4:
        return False, f"endpoint_review_meta 缺 admin 端点({admin_in_meta}/4)"
    if catch_all_in_meta < 1:
        return False, "endpoint_review_meta 缺 catch_all 段"
    return True, f"endpoint_review_meta: {admin_in_meta} admin + {catch_all_in_meta} catch-all"


def check_relay_tasks_complete(version: str) -> tuple[bool, str]:
    """§6 v*_relay_tasks 全部 COMPLETE(从 JSON 顶字段找 V 版本对应 key)。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    data = json.loads(js.read_text(encoding="utf-8"))
    # 找 v154_relay_tasks / v155_relay_tasks / ... 形式 key
    ver_num = version.lstrip("v").replace(".", "")  # v1.5.4 → 154
    relay_key = f"v{ver_num}_relay_tasks"
    relay = data.get(relay_key, {})
    if not relay:
        return False, f"缺 {relay_key} 字段"
    incomplete = [k for k, v in relay.items() if v.get("status") != "COMPLETE"]
    if incomplete:
        return False, f"relay tasks 非 COMPLETE: {incomplete}"
    return True, f"{relay_key}: {len(relay)} task 全部 COMPLETE"


def check_status_online_ready(version: str) -> tuple[bool, str]:
    """§7 status == ONLINE-READY。"""
    js = DOCS / f"openapi-frozen-{version}.json"
    if not js.is_file():
        return False, "JSON 文档不存在"
    data = json.loads(js.read_text(encoding="utf-8"))
    status = data.get("status")
    if status != "ONLINE-READY":
        return False, f"status={status!r} != 'ONLINE-READY'"
    return True, f"status={status}"


def check_admin_review_meta_in_code() -> tuple[bool, str]:
    """§8 admin.py 4 端点 docstring 含 REVIEW META 段。"""
    if not ADMIN_PY.is_file():
        return False, f"缺 {ADMIN_PY}"
    src = ADMIN_PY.read_text(encoding="utf-8")
    missing: list[str] = []
    for fn in ADMIN_ENDPOINTS:
        # 找 def fn( 函数体,到下一个 def/@router 结束
        m = re.search(
            rf"async def {fn}\b.*?(?=\n@router|\nasync def |\ndef |\Z)",
            src,
            flags=re.DOTALL,
        )
        if not m or REVIEW_META_HEADER not in m.group(0):
            missing.append(fn)
    if missing:
        return False, f"admin.py 4 端点缺 REVIEW META: {missing}"
    return True, "admin.py 4 端点 docstring 均含 REVIEW META"


def check_m8t1_aggregate() -> tuple[bool, str]:
    """§9 m8t1 跑全量 0 失败(子进程)。"""
    if not M8T1_PY.is_file():
        return False, f"缺 {M8T1_PY.name}"
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-u", "-m", "scripts.m8t1_test_regression"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "m8t1 超时(>300s)"
    # 解析输出,找 passed=.../failures=...
    out = proc.stdout + proc.stderr
    m = re.search(r"passed=(\d+)/(\d+)\s+failures=(\d+)", out)
    if not m:
        return False, f"m8t1 输出无 passed= 字段: {out[-300:]}"
    passed, total, failures = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if proc.returncode != 0 or failures > 0:
        return False, f"m8t1 失败: passed={passed}/{total} failures={failures} rc={proc.returncode}"
    return True, f"m8t1 {passed}/{total} ALL PASSED"


# ----------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------


def run_all_checks(version: str, skip_m8t1: bool = False) -> dict:
    """跑 9 项校验,返 report dict。"""
    checks = [
        ("§1 freeze_doc_exists", check_freeze_doc_exists, version),
        ("§2 freeze_version_field", check_freeze_version_field, version),
        ("§3 endpoints_total", check_endpoints_total, version),
        ("§4 super_admin_endpoints", check_super_admin_endpoints, version),
        ("§5 endpoint_review_meta", check_endpoint_review_meta, version),
        ("§6 relay_tasks_complete", check_relay_tasks_complete, version),
        ("§7 status_online_ready", check_status_online_ready, version),
        ("§8 admin_review_meta_in_code", check_admin_review_meta_in_code, None),
    ]
    if not skip_m8t1:
        checks.append(("§9 m8t1_aggregate", check_m8t1_aggregate, None))

    results: list[dict] = []
    for name, fn, arg in checks:
        try:
            ok, detail = fn(arg) if arg is not None else fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"异常: {type(exc).__name__}: {exc}"
        results.append({
            "check": name,
            "passed": ok,
            "detail": detail,
        })
    all_pass = all(r["passed"] for r in results)
    return {
        "freeze_version": version,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "all_pass": all_pass,
        "checks": results,
    }


def write_reports(report: dict) -> tuple[Path, Path]:
    """写 JSON + Markdown 报告到 docs/。"""
    version = report["freeze_version"]
    js_path = DOCS / f"freeze-check-report-{version}.json"
    md_path = DOCS / f"freeze-check-report-{version}.md"

    js_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"# Freeze Check Report — {version}",
        "",
        f"> 校验时间: {report['checked_at']}",
        f"> 全部通过: **{'YES' if report['all_pass'] else 'NO'}**",
        "",
        "| 校验项 | 结果 | 详情 |",
        "|---|---|---|",
    ]
    for r in report["checks"]:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        lines.append(f"| {r['check']} | {status} | {r['detail']} |")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return js_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAPI freeze 自动化校验")
    parser.add_argument("--version", default="v1.5.4", help="freeze 版本(默认 v1.5.4)")
    parser.add_argument("--skip-m8t1", action="store_true", help="跳过 m8t1 子进程(快速校验)")
    # V1.5.8 m16t4 增强: diff 增量校验模式
    parser.add_argument(
        "--diff",
        action="store_true",
        help="进入 diff 模式(对比 --prev / --curr 两个 freeze JSON)",
    )
    parser.add_argument(
        "--prev",
        default=None,
        help="diff 模式下源版本(例 v1.5.4)",
    )
    parser.add_argument(
        "--curr",
        default=None,
        help="diff 模式下目标版本(例 v1.5.5)",
    )
    args = parser.parse_args()

    # V1.5.8 m16t4: diff 模式
    if args.diff:
        if not args.prev or not args.curr:
            print(
                "[freeze_check] --diff 模式必须传 --prev 和 --curr",
                flush=True,
            )
            return 2
        return run_diff_mode(args.prev, args.curr)

    # 默认 9 校验模式
    print(f"Freeze check: {args.version}", flush=True)
    report = run_all_checks(args.version, skip_m8t1=args.skip_m8t1)
    js_path, md_path = write_reports(report)

    # 终端输出
    for r in report["checks"]:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"  {status} {r['check']}: {r['detail']}", flush=True)
    print("=" * 72, flush=True)
    if report["all_pass"]:
        print(f"[freeze_check] {args.version} ALL CHECKS PASSED", flush=True)
        print(f"  报告: {js_path.name} + {md_path.name}", flush=True)
        return 0
    print(f"[freeze_check] {args.version} FAILED — see {md_path.name}", flush=True)
    return 1


# ----------------------------------------------------------------------
# V1.5.8 m16t4 增强: freeze diff 增量校验
# ----------------------------------------------------------------------


def _load_freeze_doc(version: str) -> dict:
    """读 docs/openapi-frozen-{version}.json,返完整 dict。

    若文件不存在,抛 FileNotFoundError(含详细错误)。
    """
    path = DOCS / f"openapi-frozen-{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"freeze 文档不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _endpoint_key(ep: dict) -> tuple:
    """端点唯一键: (path, method)。

    接受多种 endpoint 结构(支持 OpenAPI paths dict 或 端点列表)。
    """
    return (ep.get("path", ""), ep.get("method", "").upper())


def _extract_endpoints(doc: dict) -> dict[tuple, dict]:
    """从 freeze doc 提取端点 dict {(path, method): ep}。

    两种结构兼容:
    1. doc.endpoints = [{path, method, summary, ...}, ...]   (V1.5.4 实际格式)
    2. doc.paths = {path: {method: {summary, ...}, ...}, ...}  (标准 OpenAPI)
    """
    out: dict[tuple, dict] = {}

    # 优先 list 结构
    if isinstance(doc.get("endpoints"), list):
        for ep in doc["endpoints"]:
            out[_endpoint_key(ep)] = ep
        return out

    # fallback: paths dict(标准 OpenAPI)
    paths = doc.get("paths", {})
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, info in methods.items():
            if method.lower() in ("parameters", "summary", "description"):
                continue
            ep = {
                "path": path,
                "method": method.upper(),
                "summary": info.get("summary", "") if isinstance(info, dict) else "",
            }
            out[_endpoint_key(ep)] = ep
    return out


def diff_freezes(prev: dict, curr: dict) -> dict:
    """对比两个 freeze doc,返 diff 结果 dict。

    返:
        {
            "prev_version": "v1.5.4",
            "curr_version": "v1.5.5",
            "prev_total": int,
            "curr_total": int,
            "added": [...],   # 在 curr 不在 prev
            "removed": [...], # 在 prev 不在 curr
            "changed": [...], # 都在但 summary 改了
            "summary": {added: n, removed: n, changed: n}
        }
    """
    prev_eps = _extract_endpoints(prev)
    curr_eps = _extract_endpoints(curr)

    added = [curr_eps[k] for k in curr_eps if k not in prev_eps]
    removed = [prev_eps[k] for k in prev_eps if k not in curr_eps]
    changed = []
    for k in prev_eps:
        if k in curr_eps:
            if prev_eps[k].get("summary", "") != curr_eps[k].get("summary", ""):
                changed.append({
                    "path": k[0],
                    "method": k[1],
                    "prev_summary": prev_eps[k].get("summary", ""),
                    "curr_summary": curr_eps[k].get("summary", ""),
                })

    return {
        "prev_version": prev.get("freeze_version", "unknown"),
        "curr_version": curr.get("freeze_version", "unknown"),
        "prev_total": len(prev_eps),
        "curr_total": len(curr_eps),
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def write_diff_reports(diff: dict) -> tuple[Path, Path]:
    """写 diff JSON + Markdown 报告到 docs/。"""
    prev_v = diff["prev_version"]
    curr_v = diff["curr_version"]
    js_path = DOCS / f"freeze-diff-report-{prev_v}_to_{curr_v}.json"
    md_path = DOCS / f"freeze-diff-report-{prev_v}_to_{curr_v}.md"

    js_path.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    s = diff["summary"]
    lines = [
        f"# Freeze Diff Report — {prev_v} → {curr_v}",
        "",
        f"> 生成时间: {datetime.now(timezone.utc).isoformat()}",
        f"> 源端点: {diff['prev_total']} → 目标端点: {diff['curr_total']}",
        "",
        "## 汇总",
        "",
        f"- **added**: {s['added']}",
        f"- **removed**: {s['removed']}",
        f"- **changed**: {s['changed']}",
        "",
        "## 新增端点 (added)",
        "",
    ]
    if diff["added"]:
        lines.append("| path | method | summary |")
        lines.append("|------|--------|---------|")
        for ep in diff["added"]:
            lines.append(
                f"| `{ep.get('path', '')}` | {ep.get('method', '')} | "
                f"{ep.get('summary', '')} |"
            )
    else:
        lines.append("(无新增)")
    lines.append("")

    lines.append("## 删除端点 (removed)")
    lines.append("")
    if diff["removed"]:
        lines.append("| path | method | summary |")
        lines.append("|------|--------|---------|")
        for ep in diff["removed"]:
            lines.append(
                f"| `{ep.get('path', '')}` | {ep.get('method', '')} | "
                f"{ep.get('summary', '')} |"
            )
    else:
        lines.append("(无删除)")
    lines.append("")

    lines.append("## 修改端点 (changed)")
    lines.append("")
    if diff["changed"]:
        lines.append("| path | method | prev_summary | curr_summary |")
        lines.append("|------|--------|--------------|--------------|")
        for ep in diff["changed"]:
            lines.append(
                f"| `{ep['path']}` | {ep['method']} | "
                f"{ep['prev_summary']} | {ep['curr_summary']} |"
            )
    else:
        lines.append("(无修改)")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return js_path, md_path


def run_diff_mode(prev_version: str, curr_version: str) -> int:
    """跑 diff 模式(V1.5.8 m16t4)。"""
    print(f"Freeze diff: {prev_version} → {curr_version}", flush=True)
    try:
        prev = _load_freeze_doc(prev_version)
    except FileNotFoundError as exc:
        print(f"[freeze_check] [FAIL] {exc}", flush=True)
        return 2
    try:
        curr = _load_freeze_doc(curr_version)
    except FileNotFoundError as exc:
        print(f"[freeze_check] [FAIL] {exc}", flush=True)
        return 2

    diff = diff_freezes(prev, curr)
    diff["prev_version"] = prev_version
    diff["curr_version"] = curr_version
    js_path, md_path = write_diff_reports(diff)

    s = diff["summary"]
    print("=" * 72, flush=True)
    print(
        f"[freeze_check] diff 模式: added={s['added']} "
        f"removed={s['removed']} changed={s['changed']}",
        flush=True,
    )
    print(f"  {diff['prev_total']} → {diff['curr_total']} 端点", flush=True)
    print(f"  报告: {js_path.name} + {md_path.name}", flush=True)
    print("=" * 72, flush=True)
    # diff 模式退出码: 0=无变化, 1=有变化(总是返 0, diff 本身不是 error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
