"""§6 m5t6 FE-061 数据未到位门控自测(沙箱静态结构校验)。

沙箱无前端工具链;校验:
- DataStatusBanner 组件结构(导出 / 4 状态 / role=“status” / a11y)
- useDataStatus hook 调 /data-status + 30s 轮询
- lib/api.ts 加 getDataStatus + DataStatusDTO
- __root.tsx 全局挂载
- backend app/api/data_status.py 存在 + 4 status 分支 + 沙箱降级返 warming

测点(10):
01  DataStatusBanner.tsx 导出 DataStatusBanner + DataStatusBannerFor + DataStatus
02  DataStatusBanner 4 状态 ready / warming / stale / error 都有 palette
03  DataStatusBanner 含 role="status" + aria-live="polite"
04  DataStatusBanner error 状态有 retry / close 按钮 + aria-label
05  DataStatusBanner 严禁出现 mock / 伪造字样(只能是显式说明)
06  useDataStatus.ts 调 api.getDataStatus() + refetchInterval 30s
07  lib/api.ts 含 getDataStatus + DataStatusDTO 4 状态字面量
08  __root.tsx 全局挂载 DataStatusBanner
09  backend app/api/data_status.py 存在 + /data-status 端点 + 4 status 分支
10  backend data_status.py 沙箱无 db_ok 时返 warming + reason 含 "sandbox"
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(r"d:\Financial Project\Hunter Radar\hunter-radar")
_FRONT = _REPO / "frontend"
_SRC = _FRONT / "src"
_BANNER = _SRC / "components" / "common" / "DataStatusBanner.tsx"
_HOOK = _SRC / "features" / "useDataStatus.ts"
_API = _SRC / "lib" / "api.ts"
_ROOT = _SRC / "routes" / "__root.tsx"
_BACK = _REPO / "backend" / "app" / "api" / "data_status.py"
_MAIN = _REPO / "backend" / "app" / "main.py"

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


def t01_banner_exports() -> None:
    src = _BANNER.read_text(encoding="utf-8")
    assert "export function DataStatusBanner(" in src
    assert "export function DataStatusBannerFor(" in src
    assert 'export type DataStatus' in src
    assert '"ready"' in src and '"warming"' in src and '"stale"' in src and '"error"' in src


def t02_banner_palettes() -> None:
    src = _BANNER.read_text(encoding="utf-8")
    for s in ("warming", "stale", "error"):
        assert f'case "{s}":' in src, f"palette 缺 {s}"
    assert "Data Warming" in src
    assert "Data Stale" in src
    assert "Data Unavailable" in src


def t03_banner_a11y() -> None:
    src = _BANNER.read_text(encoding="utf-8")
    assert 'role="status"' in src
    assert 'aria-live="polite"' in src
    assert "data-status=" in src  # 便于 e2e 验证


def t04_banner_buttons() -> None:
    src = _BANNER.read_text(encoding="utf-8")
    assert "重试" in src
    assert "关闭" in src
    assert 'aria-label="retry data status"' in src
    assert 'aria-label="dismiss data status banner"' in src


def t05_banner_no_mock_words() -> None:
    """硬规则:严禁在数据缺失时捏造数字 / 隐藏 banner。
    代码中不能出现模拟伪造 / 假装 ready 等字样。"""
    src = _BANNER.read_text(encoding="utf-8")
    forbidden_patterns = [
        r"\bmock\b",
        r"伪造",
        r"假装 ready",
        r"force.?ready",
    ]
    for pat in forbidden_patterns:
        if re.search(pat, src, re.IGNORECASE):
            raise AssertionError(f"banner 源码含禁用模式 {pat!r}")


def t06_use_data_status() -> None:
    src = _HOOK.read_text(encoding="utf-8")
    assert "api.getDataStatus()" in src
    # 30s 轮询
    assert "refetchInterval" in src
    assert "1000 * 30" in src or "30000" in src


def t07_api_method_and_dto() -> None:
    src = _API.read_text(encoding="utf-8")
    assert "getDataStatus" in src
    assert "/data-status" in src
    assert "DataStatusDTO" in src
    for s in ('"ready"', '"warming"', '"stale"', '"error"'):
        assert s in src, f"DataStatusDTO 缺 status {s}"


def t08_root_layout_mounts_banner() -> None:
    src = _ROOT.read_text(encoding="utf-8")
    # 必须在 import 中且在 JSX 中使用
    assert "import { DataStatusBanner }" in src
    assert "<DataStatusBanner" in src
    # 必须在 <RegimeBanner /> 之后挂载
    regime_pos = src.find("<RegimeBanner")
    banner_pos = src.find("<DataStatusBanner")
    assert regime_pos >= 0 and banner_pos >= 0
    assert regime_pos < banner_pos, (
        f"DataStatusBanner 必须在 RegimeBanner 之后挂载,got regime={regime_pos} banner={banner_pos}"
    )


def t09_backend_data_status_endpoint() -> None:
    src = _BACK.read_text(encoding="utf-8")
    assert "/data-status" in src
    # 4 状态
    for s in ('"ready"', '"warming"', '"stale"', '"error"'):
        assert s in src
    # main.py 注册
    main_src = _MAIN.read_text(encoding="utf-8")
    assert "data_status" in main_src
    assert "include_router(data_status.router" in main_src


def t10_backend_sandbox_degrade() -> None:
    src = _BACK.read_text(encoding="utf-8")
    assert "sandbox" in src
    assert "warming" in src
    # reason 字段要写明 sandbox + no PG
    assert "sandbox: no PG" in src
    # 显式返 data_warmup=True
    assert '"data_warmup": True' in src
    # db_ok=False
    assert '"db_ok": False' in src
    # 4 状态返回
    for s in ('"ready"', '"warming"', '"stale"', '"error"'):
        assert s in src, f"backend data_status 返 {s}"


# ---- 汇总 ------------------------------------------------------------------


def main() -> int:
    for fp in (_BANNER, _HOOK, _API, _ROOT, _BACK, _MAIN):
        assert fp.exists(), f"missing: {fp}"

    tests = [
        ("01_banner_exports", t01_banner_exports),
        ("02_banner_palettes", t02_banner_palettes),
        ("03_banner_a11y", t03_banner_a11y),
        ("04_banner_buttons", t04_banner_buttons),
        ("05_banner_no_mock_words", t05_banner_no_mock_words),
        ("06_use_data_status", t06_use_data_status),
        ("07_api_method_and_dto", t07_api_method_and_dto),
        ("08_root_layout_mounts_banner", t08_root_layout_mounts_banner),
        ("09_backend_data_status_endpoint", t09_backend_data_status_endpoint),
        ("10_backend_sandbox_degrade", t10_backend_sandbox_degrade),
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
        print(f"[m5t6] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t6] ALL {len(_RESULTS)} DATA STATUS TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
