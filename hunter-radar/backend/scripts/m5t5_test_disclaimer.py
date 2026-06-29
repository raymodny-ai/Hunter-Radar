"""§6 m5t5 FE-062 + FE-063 合规文案收口自测(沙箱静态结构校验)。

沙箱无 pnpm install / TS 编译器,不做运行时编译,改为:
- 静态读 TSX 源码,校验关键结构(导出 / props / 文案 / 滚动类名)
- CR-010 禁用词:扫 i18n/zh-CN.json + Disclaimer.tsx + UltimateAlertOverlay.tsx,
  不能出现(否则合规 CI 会爆)

测点(9):
01  Disclaimer.tsx 导出 Disclaimer + DisclaimerProps + DisclaimerVariant
02  Disclaimer.tsx 支持 3 个 variant(footer / banner / modal)
03  Disclaimer.tsx scrollable=true 时生成 overflow-y-auto 类名
04  Disclaimer.tsx scrollable=true + maxHeightPx 时生成 max-h-[Npx] 类名
05  Disclaimer.tsx 含 role="note" / aria-label="disclaimer"(键盘可达)
06  UltimateAlertOverlay.tsx 引入 Disclaimer + 用 variant="modal" + scrollable
07  UltimateAlertOverlay.tsx 删除旧的静态 disclaimer 段(避免重复出现)
08  i18n/zh-CN.json 含 ultimateAlert.disclaimer(给 modal 变体用)
09  CR-010 禁用词扫描:三文件中均不含「建议买入/建议卖出/建仓时机/清仓/必涨/必跌/100%/保证收益/无风险」
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# 沙箱无前端工具链,纯静态文本/文件扫描

_REPO = Path(__file__).resolve().parents[2]
_FRONT = _REPO / "frontend"
_SRC = _FRONT / "src"
_I18N = _SRC / "i18n" / "zh-CN.json"
_DISCLAIMER = _SRC / "components" / "common" / "Disclaimer.tsx"
_OVERLAY = _SRC / "components" / "radar" / "UltimateAlertOverlay.tsx"

# CR-010 禁用词(与 backend config.py forbidden_recommendation_words 对齐)
CR010_FORBIDDEN = [
    "建议买入",
    "建议卖出",
    "建仓时机",
    "清仓",
    "必涨",
    "必跌",
    "100%",
    "保证收益",
    "无风险",
]

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


def t01_disclaimer_exports() -> None:
    src = _DISCLAIMER.read_text(encoding="utf-8")
    assert "export type DisclaimerVariant" in src
    assert "export interface DisclaimerProps" in src
    assert "export function Disclaimer(" in src


def t02_disclaimer_variants() -> None:
    src = _DISCLAIMER.read_text(encoding="utf-8")
    assert '"footer"' in src
    assert '"banner"' in src
    assert '"modal"' in src
    # variantMap 三键全在
    assert "footer:" in src and "banner:" in src and "modal:" in src


def t03_disclaimer_scrollable_overflow() -> None:
    src = _DISCLAIMER.read_text(encoding="utf-8")
    # scrollable 时加 overflow-y-auto
    assert "overflow-y-auto" in src
    assert "pr-2" in src


def t04_disclaimer_max_height() -> None:
    src = _DISCLAIMER.read_text(encoding="utf-8")
    # maxHeightPx 时生成 max-h-[Npx];缺省 max-h-32
    assert "max-h-[" in src
    assert "max-h-32" in src


def t05_disclaimer_a11y() -> None:
    src = _DISCLAIMER.read_text(encoding="utf-8")
    assert 'role="note"' in src
    assert 'aria-label="disclaimer"' in src
    assert "data-disclaimer-variant=" in src  # 便于 e2e / devtools 验证


def t06_overlay_uses_disclaimer() -> None:
    src = _OVERLAY.read_text(encoding="utf-8")
    assert 'import { Disclaimer }' in src
    assert "@/components/common/Disclaimer" in src
    assert 'variant="modal"' in src
    assert "scrollable" in src
    # maxHeightPx 显式传
    assert "maxHeightPx={120}" in src


def t07_overlay_removed_legacy() -> None:
    src = _OVERLAY.read_text(encoding="utf-8")
    # 老的静态 disclaimer 段已删除(避免出现两遍)
    assert "本警报基于 FINRA / SEC EDGAR / Yahoo Finance 公开延时数据" not in src
    # 但 i18n ultimateAlert.disclaimer 文案仍保留(供 Disclaimer modal 变体用)
    i18n_src = _I18N.read_text(encoding="utf-8")
    assert "FINRA / SEC EDGAR / Yahoo Finance" in i18n_src


def t08_i18n_disclaimer_key() -> None:
    blob = _I18N.read_text(encoding="utf-8")
    data = json.loads(blob)
    assert "ultimateAlert" in data
    assert "disclaimer" in data["ultimateAlert"]
    assert "不构成投资建议" in data["ultimateAlert"]["disclaimer"]


def t09_cr010_forbidden_words() -> None:
    files = [_DISCLAIMER, _OVERLAY, _I18N]
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        for w in CR010_FORBIDDEN:
            # 注意:UltimateAlertOverlay 中 "FINRA / SEC EDGAR / Yahoo Finance" 包含
            # "Yahoo" 不会命中禁用词(禁用词是建议类,非数据源名)
            if w in text:
                raise AssertionError(
                    f"CR-010 禁用词 {w!r} 出现在 {fp.relative_to(_REPO)}"
                )


# ---- 汇总 ------------------------------------------------------------------


def main() -> int:
    # 前置检查:文件存在
    for fp in (_DISCLAIMER, _OVERLAY, _I18N):
        assert fp.exists(), f"missing: {fp}"

    tests = [
        ("01_disclaimer_exports", t01_disclaimer_exports),
        ("02_disclaimer_variants", t02_disclaimer_variants),
        ("03_disclaimer_scrollable_overflow", t03_disclaimer_scrollable_overflow),
        ("04_disclaimer_max_height", t04_disclaimer_max_height),
        ("05_disclaimer_a11y", t05_disclaimer_a11y),
        ("06_overlay_uses_disclaimer", t06_overlay_uses_disclaimer),
        ("07_overlay_removed_legacy", t07_overlay_removed_legacy),
        ("08_i18n_disclaimer_key", t08_i18n_disclaimer_key),
        ("09_cr010_forbidden_words", t09_cr010_forbidden_words),
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
        print(f"[m5t5] FAILED {len(fail)} / {len(_RESULTS)}")
        return 1
    print(f"[m5t5] ALL {len(_RESULTS)} DISCLAIMER TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
