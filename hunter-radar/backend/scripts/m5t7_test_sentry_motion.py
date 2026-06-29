"""§6 m5t7 FE-069 Sentry + FE-070 prefers-reduced-motion 自测(沙箱静态结构校验)。

测点(10):
01  lib/sentry.ts 存在 + 导出 initSentry / captureException / addBreadcrumb / isSentryEnabled
02  lib/sentry.ts 沙箱无 DSN 时 init no-op(不抛)
03  lib/sentry.ts 动态 import @sentry/react(沙箱缺时静默降级)
04  lib/sentry.ts sendDefaultPii:false(PII 防护)
05  features/usePrefersReducedMotion.ts 导出 hook + readPrefersReducedMotion + reduceMotionClasses
06  usePrefersReducedMotion matchMedia query 字符串含 "prefers-reduced-motion: reduce"
07  usePrefersReducedMotion listen 'change' 事件(用户切换立即生效)
08  reduceMotionClasses 过滤 animate-* / transition-*
09  main.tsx 在 ReactDOM.render 之前调 initSentry()
10  src/vite-env.d.ts 存在且含 VITE_SENTRY_DSN / VITE_APP_VERSION 类型
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_FRONT = _REPO / "frontend"
_SRC = _FRONT / "src"
_SENTRY = _SRC / "lib" / "sentry.ts"
_REDUCED = _SRC / "features" / "usePrefersReducedMotion.ts"
_MAIN = _SRC / "main.tsx"
_VITE_ENV = _SRC / "vite-env.d.ts"

_RESULTS: list[tuple[str, str, str | None]] = []


def _run(name: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        _RESULTS.append((name, "FAIL", f"assert: {e}"))
    except Exception as e:  # noqa: BLE001
        _RESULTS.append((name, "ERROR", f"{type(e).__name__}: {e}"))
    else:
        _RESULTS.append((name, "PASS", None))


# ---- 测点 ------------------------------------------------------------------


def t01_sentry_exports() -> None:
    src = _SENTRY.read_text(encoding="utf-8")
    assert "export function initSentry" in src
    assert "export function captureException" in src
    assert "export function addBreadcrumb" in src
    assert "export function isSentryEnabled" in src
    # getSentryDsn 便于诊断
    assert "export function getSentryDsn" in src


def t02_sentry_sandbox_noop() -> None:
    src = _SENTRY.read_text(encoding="utf-8")
    # 无 DSN 时:init 不抛,且 no-op
    assert "if (!DSN)" in src
    # 关闭 dev/preview:print to console 不真发
    assert "console.warn" in src or "console" in src


def t03_sentry_dynamic_import() -> None:
    src = _SENTRY.read_text(encoding="utf-8")
    # 动态 import 让沙箱缺 @sentry/react 时 init 仍 no-op
    assert 'import("@sentry/react")' in src
    # 静默降级:catch
    assert ".catch(" in src


def t04_sentry_pii_protection() -> None:
    src = _SENTRY.read_text(encoding="utf-8")
    assert "sendDefaultPii: false" in src
    # denyUrls 防止自家域名上报
    assert "denyUrls" in src


def t05_reduced_motion_exports() -> None:
    src = _REDUCED.read_text(encoding="utf-8")
    assert "export function usePrefersReducedMotion" in src
    assert "export function readPrefersReducedMotion" in src
    assert "export function reduceMotionClasses" in src


def t06_reduced_motion_query() -> None:
    src = _REDUCED.read_text(encoding="utf-8")
    # matchMedia 字符串
    assert '"(prefers-reduced-motion: reduce)"' in src


def t07_reduced_motion_listen_change() -> None:
    src = _REDUCED.read_text(encoding="utf-8")
    # 监听 change 事件
    assert "addEventListener" in src
    assert '"change"' in src
    # 清理函数
    assert "removeEventListener" in src


def t08_reduced_motion_filter() -> None:
    src = _REDUCED.read_text(encoding="utf-8")
    # reduceMotionClasses 过滤 animate-* / transition-*
    assert "animate-" in src
    assert "transition-" in src
    # 正则过滤
    assert re.search(r"animate-\|transition-", src) is not None


def t09_main_calls_init_sentry() -> None:
    src = _MAIN.read_text(encoding="utf-8")
    # 必须在 ReactDOM.createRoot 之前调
    init_pos = src.find("initSentry()")
    render_pos = src.find("ReactDOM.createRoot")
    assert init_pos >= 0 and render_pos >= 0
    assert init_pos < render_pos, "initSentry 必须在 ReactDOM.createRoot 之前"


def t10_vite_env_types() -> None:
    src = _VITE_ENV.read_text(encoding="utf-8")
    assert "VITE_SENTRY_DSN" in src
    assert "VITE_APP_VERSION" in src
    # 标准 vite/client reference
    assert "vite/client" in src


# ---- 汇总 ------------------------------------------------------------------


def main() -> int:
    for fp in (_SENTRY, _REDUCED, _MAIN, _VITE_ENV):
        assert fp.exists(), f"missing: {fp}"

    tests = [
        ("01_sentry_exports", t01_sentry_exports),
        ("02_sentry_sandbox_noop", t02_sentry_sandbox_noop),
        ("03_sentry_dynamic_import", t03_sentry_dynamic_import),
        ("04_sentry_pii_protection", t04_sentry_pii_protection),
        ("05_reduced_motion_exports", t05_reduced_motion_exports),
        ("06_reduced_motion_query", t06_reduced_motion_query),
        ("07_reduced_motion_listen_change", t07_reduced_motion_listen_change),
        ("08_reduced_motion_filter", t08_reduced_motion_filter),
        ("09_main_calls_init_sentry", t09_main_calls_init_sentry),
        ("10_vite_env_types", t10_vite_env_types),
    ]
    for name, fn in tests:
        _run(name, fn)
    print()
    for name, status, err in _RESULTS:
        line = f"  [{status}] {name}"
        if err:
            line += f"  -- {err}"
        print(line)
    fail = [r for r in _RESULTS if r[1] != "PASS"]
    print()
    if fail:
        print(f"[m5t7] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t7] ALL {len(_RESULTS)} SENTRY + REDUCED-MOTION TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
