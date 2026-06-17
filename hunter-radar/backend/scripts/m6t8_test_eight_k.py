"""M6-t8 沙箱自测:BD-051 8-K Item 8.01 解析器落地产物校验。

沙箱不实跑 SEC EDGAR full-text search(无 httpx 代理),只静态校验:
- 8-K service:8-K dataclass + 5 类 category 关键词 + fixture 5 条
- 3 个 API 端点(/events/8k + /symbols/{ticker}/8k + /events/8k/classify)
- main.py 注册 eight_k router
- classify_summary 纯函数 + 3 category 关键词覆盖
- _sanitize_summary CR-010 禁词过滤
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
SERVICE = APP / "services" / "eight_k.py"
ROUTER = APP / "api" / "eight_k.py"
MAIN = APP / "main.py"

PASS = "[PASS]"
FAIL = "[FAIL]"
failures = 0


def t(name: str, ok: bool, detail: str = "") -> bool:
    global failures
    if ok:
        print(f"  {PASS} {name}{('(' + detail + ')') if detail else ''}")
    else:
        print(f"  {FAIL} {name}{('(' + detail + ')') if detail else ''}")
        failures += 1
    return ok


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
section("1. 8-K service 模块 + dataclass")

t("t01_service_module_exists", SERVICE.exists(), f"path={SERVICE}")

service_text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""

t("t02_eight_k_dataclass",
  "@dataclass" in service_text and "EightKEvent" in service_text)

required_fields = [
    "ticker",
    "cik",
    "filed_at",
    "accession",
    "form",
    "item",
    "category",
    "title",
    "summary",
    "url",
    "fetched_at",
]
missing_fields = [f for f in required_fields if f not in service_text]
t("t03_eight_k_fields_complete", len(missing_fields) == 0, f"missing={missing_fields}")

t("t04_item_8_01_default",
  'item: str = "8.01"' in service_text or '"8.01"' in service_text)


# ---------------------------------------------------------------------------
section("2. 4 类 category 关键词")

required_categories = ["share-repurchase", "material-agreement", "press-release", "other"]
ok_cats = sum(1 for c in required_categories if f'"{c}"' in service_text or f"'{c}'" in service_text)
t("t05_categories_4", ok_cats == 4, f"matched={ok_cats}/4")

required_keywords = [
    "share repurchase",
    "buyback",
    "material agreement",
    "strategic alliance",
    "press release",
    "announces",
]
missing_kw = [k for k in required_keywords if k not in service_text]
t("t06_keywords_6", len(missing_kw) == 0, f"missing={missing_kw}")


# ---------------------------------------------------------------------------
section("3. fixture 5 条 + 多 ticker 覆盖")

# 沙箱 fixture ticker 列表
required_tickers = ["AAPL", "TSLA", "MSFT", "NVDA", "GME"]
missing_tickers = [tk for tk in required_tickers if tk not in service_text]
t("t07_fixture_5_tickers", len(missing_tickers) == 0, f"missing={missing_tickers}")

t("t08_fixture_has_share_repurchase",
  "share-repurchase" in service_text and "Apple" in service_text)


# ---------------------------------------------------------------------------
section("4. classify_summary 纯函数")

t("t09_classify_function_export",
  "def classify_summary" in service_text)

# 类别关键词命中测试
t("t10_classify_share_repurchase",
  "share repurchase" in service_text or "buyback" in service_text)
t("t11_classify_material_agreement",
  "material agreement" in service_text)


# ---------------------------------------------------------------------------
section("5. list_fixture_events + fetch_recent_8k + fetch_for_ticker")

required_funcs = [
    "def list_fixture_events",
    "def fetch_recent_8k",
    "def fetch_for_ticker",
]
missing_funcs = [f for f in required_funcs if f not in service_text]
t("t12_service_functions_complete", len(missing_funcs) == 0, f"missing={missing_funcs}")


# ---------------------------------------------------------------------------
section("6. router 3 端点")

t("t13_router_module_exists", ROUTER.exists(), f"path={ROUTER}")
router_text = ROUTER.read_text(encoding="utf-8") if ROUTER.exists() else ""

required_endpoints = [
    ("GET", "/events/8k"),
    ("GET", "/symbols/{ticker}/8k"),
    ("POST", "/events/8k/classify"),
]
matched = sum(
    1
    for method, path in required_endpoints
    if re.search(rf'@router\.{method.lower()}\("{re.escape(path)}"', router_text)
)
t("t14_router_endpoints_3", matched == 3, f"matched={matched}/3")


# ---------------------------------------------------------------------------
section("7. main.py 注册 eight_k router")

main_text = MAIN.read_text(encoding="utf-8") if MAIN.exists() else ""

t("t15_main_imports_eight_k",
  "from app.api import" in main_text and "eight_k," in main_text)

t("t16_main_includes_eight_k_router",
  "eight_k.router" in main_text and "tags=[\"events\"]" in main_text)


# ---------------------------------------------------------------------------
section("8. CR-010 禁词过滤 + 合规")

t("t17_sanitize_summary_function",
  "_sanitize_summary" in router_text or "sanitize" in router_text.lower())

forbidden = ["建议买入", "建议卖出", "保证收益", "必涨", "必跌"]
violations = [w for w in forbidden if w not in router_text]
t("t18_router_mentions_forbidden_words_for_filter",
  len(violations) == 0,
  f"全部 5 词均出现于 router(用于过滤)={violations}")

t("t19_disclaimer_or_compliance",
  "合规" in router_text or "不做投资建议" in router_text or "仅供参考" in router_text
  or "REDACTED" in router_text)


# ---------------------------------------------------------------------------
print()
if failures == 0:
    print("[m6t8] ALL 19 EIGHT-K-ITEM-8.01 (SERVICE + ROUTER + MAIN + CR-010) TESTS PASSED")
    sys.exit(0)
else:
    print(f"[m6t8] {failures} TEST(S) FAILED")
    sys.exit(1)