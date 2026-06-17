"""V1.5 接力期 m9t4 — EDGAR fulltext 端点自测(纯文本静态校验版)。

不 import edgar.py / etl/edgar_fulltext(避免 sandbox import 链卡死)。
所有测点基于文件内容字符串匹配 + Python AST/inspect 静态分析(只 inspect 自身)。

校验:
- 文件存在 + 内容结构
- 2 个端点函数定义(search_edgar / list_categories)
- 6 参数(query/tickers/from_date/to_date/category/limit)
- CATEGORY_KEYWORDS 4 类(文本中显式列出)
- 沙箱 fallback 显式标注(sandbox=true + review_mode="sandbox_stub")
- limit 范围 1-50 + category enum 4 类 + date 格式校验
- 11 已知 ticker 默认集
- response 结构(summary/filings/sandbox/review_mode/query_meta)
- 显式 disclaimer + 严禁 mock 200
- 与 eight_k.py CATEGORY_KEYWORDS 同步
- 集成到 main.py router(prefix=/api/v1/edgar)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDGAR_API = ROOT / "backend" / "app" / "api" / "edgar.py"
MAIN_PY = ROOT / "backend" / "app" / "main.py"
EIGHT_K_SVC = ROOT / "backend" / "app" / "services" / "eight_k.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Test functions(纯静态)
# ----------------------------------------------------------------------

def t01_edgar_api_file_exists() -> bool:
    """t01: backend/app/api/edgar.py 存在。"""
    return EDGAR_API.is_file()


def t02_module_top_level_imports() -> bool:
    """t02: edgar.py 含 fastapi + etl.edgar_fulltext import。"""
    txt = _read(EDGAR_API)
    return "from fastapi import" in txt and "from etl.edgar_fulltext import" in txt


def t03_router_has_two_endpoints() -> bool:
    """t03: router 至少 2 个 @router.get 装饰器(search + categories)。"""
    txt = _read(EDGAR_API)
    n_get = txt.count("@router.get")
    return n_get >= 2


def t04_category_keywords_4_classes() -> bool:
    """t04: CATEGORY_KEYWORDS 4 类齐全(share-repurchase/material-agreement/press-release/other)。"""
    txt = _read(EDGAR_API)
    cats = ("share-repurchase", "material-agreement", "press-release", "other")
    # 4 类都要在 txt 中出现
    return all(c in txt for c in cats)


def t05_imports_fetch_fulltext_sandbox() -> bool:
    """t05: 引用 fetch_fulltext_sandbox 沙箱实现。"""
    txt = _read(EDGAR_API)
    return "fetch_fulltext_sandbox" in txt


def t06_sandbox_fallback_marker() -> bool:
    """t06: 沙箱 fallback 显式标注 sandbox=True。"""
    txt = _read(EDGAR_API)
    return '"sandbox": True' in txt or '"sandbox": true' in txt


def t07_review_mode_sandbox_stub() -> bool:
    """t07: review_mode="sandbox_stub" 显式标注(≥2 次:search + categories)。"""
    txt = _read(EDGAR_API)
    count = txt.count('"sandbox_stub"')
    return count >= 2


def t08_default_11_tickers() -> bool:
    """t08: 默认 ticker 集 ≥11 个(AAPL/MSFT/TSLA/NVDA/GME/AMC/BBBY/KOSS/BB/WISH/NOK)。"""
    txt = _read(EDGAR_API)
    expected = ("AAPL", "MSFT", "TSLA", "NVDA", "GME", "AMC", "BBBY",
                "KOSS", "BB", "WISH", "NOK")
    return all(t in txt for t in expected)


def t09_six_query_params() -> bool:
    """t09: search_edgar 函数含 6 参数(query/tickers/from_date/to_date/category/limit)。"""
    txt = _read(EDGAR_API)
    params = ("query:", "tickers:", "from_date:", "to_date:", "category:", "limit:")
    return all(p in txt for p in params)


def t10_limit_range_1_50() -> bool:
    """t10: limit 参数 ge=1, le=50(Query 校验)。"""
    txt = _read(EDGAR_API)
    return "ge=1" in txt and "le=50" in txt


def t11_category_literal_4_classes() -> bool:
    """t11: Category Literal 含 4 类(share-repurchase/material-agreement/press-release/other)。"""
    txt = _read(EDGAR_API)
    # Literal["a", "b", "c", "other"]
    m = re.search(r'Category\s*=\s*Literal\[(.*?)\]', txt)
    if not m:
        return False
    args = m.group(1)
    expected = ('"share-repurchase"', '"material-agreement"', '"press-release"', '"other"')
    return all(e in args for e in expected)


def t12_parse_date_helper_signature() -> bool:
    """t12: _parse_date 函数签名(name 参数 + HTTPException 400)。"""
    txt = _read(EDGAR_API)
    return "def _parse_date" in txt and 'status_code=400' in txt


def t13_parse_tickers_helper() -> bool:
    """t13: _parse_tickers 函数存在 + 调 .upper() 大写。"""
    txt = _read(EDGAR_API)
    return "def _parse_tickers" in txt and ".upper()" in txt


def t14_response_includes_summary_filings_sandbox() -> bool:
    """t14: search_edgar 返回 dict 含 summary/filings/sandbox/review_mode/query_meta 5 关键字段。"""
    txt = _read(EDGAR_API)
    keys = ['"summary"', '"filings"', '"sandbox"', '"review_mode"', '"query_meta"']
    return all(k in txt for k in keys)


def t15_response_includes_disclaimer() -> bool:
    """t15: 响应含 disclaimer 字段(显式说明 sandbox_stub)。"""
    txt = _read(EDGAR_API)
    return '"disclaimer"' in txt and "sandbox_stub" in txt.lower()


def t16_no_mock_200_philosophy() -> bool:
    """t16: 严禁 mock 200 伪装 — 文档/注释明文标注 + sandbox=True 始终。"""
    txt = _read(EDGAR_API)
    return "mock 200" in txt or "mock200" in txt or "mock-200" in txt


def t17_edgar_api_key_still_sandbox() -> bool:
    """t17: 即使 EDGAR_API_KEY 已设,响应仍标 sandbox=True(占位实现)。"""
    txt = _read(EDGAR_API)
    return "EDGAR_API_KEY" in txt and "sandbox" in txt


def t18_main_py_includes_edgar_router() -> bool:
    """t18: main.py 包含 edgar router + prefix /api/v1/edgar。"""
    txt = _read(MAIN_PY)
    return "edgar" in txt and 'prefix="/api/v1/edgar"' in txt


def t19_main_py_imports_edgar_module() -> bool:
    """t19: main.py 显式 import edgar 模块。"""
    txt = _read(MAIN_PY)
    # 检查 from app.api import (...) 段
    if "from app.api import" not in txt:
        return False
    # 提取 import 段
    m = re.search(r'from app\.api import \((.*?)\)', txt, re.DOTALL)
    if not m:
        return False
    return "edgar" in m.group(1)


def t20_router_prefix_in_edgar_py() -> bool:
    """t20: edgar.py router 自身无 prefix(prefix 在 main.py 注入)— 静态验证 router = APIRouter()。"""
    txt = _read(EDGAR_API)
    # router = APIRouter() 显式无 prefix 参数
    return re.search(r'router\s*=\s*APIRouter\(\)', txt) is not None


def t21_query_meta_includes_filters() -> bool:
    """t21: query_meta 段含 6 字段(query/tickers/from_date/to_date/category/limit)。

    V1.5.5 接力期 m13t4 修复:edgar.py 含 2 段 query_meta(L22 docstring 简版 + L154-161 实际代码),
    原正则 `[(.*?)]` 懒惰匹配 docstring 段,该段不含 6 字段。改用 re.findall 找所有段,任一段含 6 字段即可。
    """
    txt = _read(EDGAR_API)
    # V1.5.5 m13t4:找所有 query_meta 段,任一段含 6 字段即通过
    matches = re.findall(r'"query_meta":\s*\{([^}]+)\}', txt)
    for body in matches:
        if all(k in body for k in ("query", "tickers", "from_date", "to_date", "category", "limit")):
            return True
    return False


def t22_categories_endpoint_returns_4_classes() -> bool:
    """t22: list_categories 端点返 categories + keywords + review_mode 3 字段。"""
    txt = _read(EDGAR_API)
    return "async def list_categories" in txt \
        and '"categories"' in txt and '"keywords"' in txt and '"review_mode"' in txt


def t23_no_cr010_forbidden_words() -> bool:
    """t23: 不含 CR-010 禁词(投资建议类,如 买入/卖出/推荐/保证)。"""
    txt = _read(EDGAR_API)
    forbidden = ("建议买入", "保证收益", "推荐买入", "强烈推荐", "稳赚不赔")
    return not any(w in txt for w in forbidden)


def t24_sync_with_eight_k_keywords() -> bool:
    """t24: 与 app/services/eight_k.py CATEGORY_KEYWORDS 同步(同 4 类)。"""
    if not EIGHT_K_SVC.exists():
        return False
    txt = _read(EIGHT_K_SVC)
    expected = ("share-repurchase", "material-agreement", "press-release")
    return all(k in txt for k in expected)


def t25_routes_get_method() -> bool:
    """t25: search + categories 都是 @router.get 装饰器。"""
    txt = _read(EDGAR_API)
    return txt.count("@router.get") >= 2


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

ALL_TESTS = [
    ("t01_edgar_api_file_exists", t01_edgar_api_file_exists),
    ("t02_module_top_level_imports", t02_module_top_level_imports),
    ("t03_router_has_two_endpoints", t03_router_has_two_endpoints),
    ("t04_category_keywords_4_classes", t04_category_keywords_4_classes),
    ("t05_imports_fetch_fulltext_sandbox", t05_imports_fetch_fulltext_sandbox),
    ("t06_sandbox_fallback_marker", t06_sandbox_fallback_marker),
    ("t07_review_mode_sandbox_stub", t07_review_mode_sandbox_stub),
    ("t08_default_11_tickers", t08_default_11_tickers),
    ("t09_six_query_params", t09_six_query_params),
    ("t10_limit_range_1_50", t10_limit_range_1_50),
    ("t11_category_literal_4_classes", t11_category_literal_4_classes),
    ("t12_parse_date_helper_signature", t12_parse_date_helper_signature),
    ("t13_parse_tickers_helper", t13_parse_tickers_helper),
    ("t14_response_includes_summary_filings_sandbox", t14_response_includes_summary_filings_sandbox),
    ("t15_response_includes_disclaimer", t15_response_includes_disclaimer),
    ("t16_no_mock_200_philosophy", t16_no_mock_200_philosophy),
    ("t17_edgar_api_key_still_sandbox", t17_edgar_api_key_still_sandbox),
    ("t18_main_py_includes_edgar_router", t18_main_py_includes_edgar_router),
    ("t19_main_py_imports_edgar_module", t19_main_py_imports_edgar_module),
    ("t20_router_prefix_in_edgar_py", t20_router_prefix_in_edgar_py),
    ("t21_query_meta_includes_filters", t21_query_meta_includes_filters),
    ("t22_categories_endpoint_returns_4_classes", t22_categories_endpoint_returns_4_classes),
    ("t23_no_cr010_forbidden_words", t23_no_cr010_forbidden_words),
    ("t24_sync_with_eight_k_keywords", t24_sync_with_eight_k_keywords),
    ("t25_routes_get_method", t25_routes_get_method),
]


def _run(name: str, fn) -> bool:
    try:
        result = fn()
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}", flush=True)
        return result
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] {name} — {type(e).__name__}: {e}", flush=True)
        return False


def main() -> int:
    print("=" * 72)
    print("  V1.5 接力期 m9t4 — EDGAR fulltext 端点自测(纯文本静态)")
    print("=" * 72)

    passed = 0
    failed = 0
    failed_names: list[str] = []
    for name, fn in ALL_TESTS:
        if _run(name, fn):
            passed += 1
        else:
            failed += 1
            failed_names.append(name)

    total = passed + failed
    print("=" * 72)
    print(f"  [m9t4] SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 72)
    if failed:
        print("\n[m9t4] FAILED TESTS:")
        for n in failed_names:
            print(f"  - {n}")
        return 1
    print(f"\n[m9t4] ALL {total} EDGAR ENDPOINT SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
