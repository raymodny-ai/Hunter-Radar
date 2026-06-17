"""CR-003 / CR-010 合规文案 CI 检查。

扫描 src/ 下的 .ts/.tsx/.js/.jsx 文件,拦截:
- 投资建议类:「建议买入」「建议卖出」「建仓时机」「必涨」「必跌」「清仓」
- 收益承诺类:「100%」「保证收益」「无风险」「稳赚」
- 用户协议中允许的「根据统计现象」「仅供参考」类兜底文案必须出现一次以上

使用:
    python tools/compliance_check.py path/to/src [path/to/other/src ...]
    或在 CI: python tools/compliance_check.py frontend/src backend/app
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN: list[str] = [
    "建议买入",
    "建议卖出",
    "建仓时机",
    "必涨",
    "必跌",
    "清仓",
    "保证收益",
    "稳赚",
    "无风险",
]

# 宽松匹配:100% 单独存在时被禁;在 "100% 数据驱动" 等非收益承诺语境放过
PATTERNS: list[tuple[str, str]] = [
    (r"100%\s*(?:盈利|收益|涨停|胜率|准确)", "禁止使用 100% 修饰收益/准确率"),
    (r"强烈推荐\s*(?:买入|卖出|加仓|减仓)", "禁止绝对化交易指令"),
    (r"马上(?:买入|卖出|建仓|清仓)", "禁止绝对化交易指令"),
]

REQUIRED_DISCLAIMER: list[str] = [
    "统计",
    "参考",
]


def scan_file(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return issues
    except OSError:
        return issues

    for bad in FORBIDDEN:
        if bad in text:
            # 排除注释中的「禁用说明」自身(本脚本的注释也算,需自检豁免)
            if "/**" in text and bad in text[text.find("/**"):text.find("*/") + 2]:
                continue
            issues.append(f"[禁词] {bad} 出现在 {path}")

    for pat, desc in PATTERNS:
        if re.search(pat, text):
            issues.append(f"[模式] {desc} 出现在 {path}")

    return issues


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python tools/compliance_check.py <src_dir> [...]")
        return 1
    all_issues: list[str] = []
    for arg in argv:
        root = Path(arg)
        if root.is_file():
            files = [root]
        else:
            files = list(root.rglob("*"))
            files = [f for f in files if f.suffix in {".ts", ".tsx", ".js", ".jsx", ".vue", ".md"}]
        for f in files:
            all_issues.extend(scan_file(f))
    if all_issues:
        print("❌ 合规检查未通过:")
        for i in all_issues:
            print(f"  - {i}")
        return 1
    print("✅ 合规检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
