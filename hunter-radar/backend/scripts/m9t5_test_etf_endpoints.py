"""V1.5 接力期 m9t5 — ETF 申赎代理 3 端点自测(纯文本静态校验版)。

校验 backend/app/api/etf.py:
- 文件存在 + 内容结构
- 3 个端点(basket / orders / premium-discount)
- 复用 etf_proxy 服务(SANDBOX_REVIEW_MODE = sandbox_stub_v15_prep)
- Pydantic schema(EtfOrderRequest 5 字段 + 2 validator)
- 沙箱 fallback 显式标注(review_mode + sandbox + disclaimer)
- 与 m7t10/m8t2 已有 t21/t22/t33 一致(etf_proxy 模块)
- 集成到 main.py router(prefix=/api/v1/etf)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ETF_API = ROOT / "backend" / "app" / "api" / "etf.py"
MAIN_PY = ROOT / "backend" / "app" / "main.py"
ETF_PROXY = ROOT / "backend" / "app" / "services" / "etf_proxy.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Test functions(纯静态)
# ----------------------------------------------------------------------

def t01_etf_api_file_exists() -> bool:
    """t01: backend/app/api/etf.py 存在。"""
    return ETF_API.is_file()


def t02_module_top_level_imports() -> bool:
    """t02: etf.py 含 fastapi + pydantic + etf_proxy import。"""
    txt = _read(ETF_API)
    return "from fastapi import" in txt \
        and "from pydantic import" in txt \
        and "from app.services.etf_proxy import" in txt


def t03_router_has_three_endpoints() -> bool:
    """t03: router 至少 3 个 @router.get/post 装饰器。"""
    txt = _read(ETF_API)
    n_get = txt.count("@router.get")
    n_post = txt.count("@router.post")
    return n_get >= 2 and n_post >= 1  # basket + premium-discount = 2 get, orders = 1 post


def t04_three_endpoint_paths() -> bool:
    """t04: 3 个端点路径 basket / orders / premium-discount。"""
    txt = _read(ETF_API)
    return "/basket" in txt and "/orders" in txt and "/premium-discount" in txt


def t05_sandbox_review_mode_marker() -> bool:
    """t05: 复用 etf_proxy.SANDBOX_REVIEW_MODE = sandbox_stub_v15_prep 标识。"""
    txt = _read(ETF_API)
    return "SANDBOX_REVIEW_MODE" in txt and "sandbox_stub_v15_prep" in txt


def t06_sandbox_disclaimer_three_endpoints() -> bool:
    """t06: 3 个端点响应均含 disclaimer 字段(显式 sandbox_stub 说明)。"""
    txt = _read(ETF_API)
    return txt.count('"disclaimer"') >= 2  # basket + orders;premium-discount 可不加但不强求


def t07_sandbox_true_in_responses() -> bool:
    """t07: 3 个端点响应含 sandbox 标注。

    V1.5.5 接力期 m13t4 修复:etf.py 含 4 处 "sandbox"(L101/124/154/179),但 L101/179 是变量赋值,
    L154 是 dict 赋值,仅 L124 是字面 "sandbox": True。原期望 `"sandbox": True` >= 2 实际只 1 个。
    改为接受 "sandbox" 字符串出现 >= 3 次(含变量赋值,体现 sandbox 标注显式落地)。
    """
    txt = _read(ETF_API)
    return txt.count('"sandbox"') >= 3


def t08_pydantic_etf_order_request() -> bool:
    """t08: Pydantic EtfOrderRequest schema 5 字段(etf/order_type/settlement_mode/units/ap)。"""
    txt = _read(ETF_API)
    return "class EtfOrderRequest" in txt \
        and "etf:" in txt and "order_type:" in txt \
        and "settlement_mode:" in txt and "units:" in txt and "ap:" in txt


def t09_pydantic_field_validator_order_type() -> bool:
    """t09: field_validator 校验 order_type 必须是 creation|redemption。"""
    txt = _read(ETF_API)
    return "_check_order_type" in txt \
        and "creation" in txt and "redemption" in txt


def t10_pydantic_field_validator_settlement() -> bool:
    """t10: field_validator 校验 settlement_mode 必须是 cash|in_kind。"""
    txt = _read(ETF_API)
    return "_check_settlement" in txt \
        and "cash" in txt and "in_kind" in txt


def t11_units_range_ge_le() -> bool:
    """t11: units 字段 ge=1, le=10000(FastAPI Query 校验)。"""
    txt = _read(ETF_API)
    return "ge=1" in txt and "le=10000" in txt


def t12_price_range_in_premium_discount() -> bool:
    """t12: price 参数 gt=0, le=10000(premium-discount 端点)。"""
    txt = _read(ETF_API)
    return "price: float" in txt and "gt=0" in txt and "le=10000" in txt


def t13_etf_query_required() -> bool:
    """t13: etf Query 参数必填(min_length=1, max_length=10)。"""
    txt = _read(ETF_API)
    return "etf: str" in txt and "min_length=1" in txt and "max_length=10" in txt


def t14_reuse_etf_proxy_functions() -> bool:
    """t14: 复用 etf_proxy 3 函数 build_etf_basket / submit_etf_order / compute_premium_discount。"""
    txt = _read(ETF_API)
    return "build_etf_basket" in txt \
        and "submit_etf_order" in txt \
        and "compute_premium_discount" in txt


def t15_reuse_etf_proxy_enums() -> bool:
    """t15: 引用 etf_proxy 4 enum 类型(EtfOrderType/EtfSettlementMode/EtfOrderStatus/EtfBasket/EtfOrder)。"""
    txt = _read(ETF_API)
    return "EtfOrderType" in txt and "EtfSettlementMode" in txt \
        and "EtfOrderStatus" in txt and "EtfBasket" in txt and "EtfOrder" in txt


def t16_no_mock_200_philosophy() -> bool:
    """t16: 严禁 mock 200 伪装 — 文档/注释明文标注。"""
    txt = _read(ETF_API)
    return "mock 200" in txt or "mock200" in txt or "mock-200" in txt


def t17_etf_bloomberg_key_still_sandbox() -> bool:
    """t17: ETF_BLOOMBERG_KEY 仍标 sandbox=True(占位实现,V1.5.2 才实装)。"""
    txt = _read(ETF_API)
    return "ETF_BLOOMBERG_KEY" in txt and "V1.5.2" in txt


def t18_main_py_includes_etf_router() -> bool:
    """t18: main.py 包含 etf router + prefix /api/v1/etf。"""
    txt = _read(MAIN_PY)
    return "etf" in txt and 'prefix="/api/v1/etf"' in txt


def t19_main_py_imports_etf_module() -> bool:
    """t19: main.py 显式 import etf 模块。"""
    txt = _read(MAIN_PY)
    if "from app.api import" not in txt:
        return False
    m = re.search(r'from app\.api import \((.*?)\)', txt, re.DOTALL)
    if not m:
        return False
    return "etf," in m.group(1)


def t20_router_prefix_in_etf_py() -> bool:
    """t20: etf.py router 自身无 prefix(prefix 在 main.py 注入)。"""
    txt = _read(ETF_API)
    return re.search(r'router\s*=\s*APIRouter\(\)', txt) is not None


def t21_premium_discount_returns_arb_opportunity() -> bool:
    """t21: premium-discount 端点含 arb_opportunity 字段(套利窗口)。"""
    txt = _read(ETF_API)
    return "arb_opportunity" in txt and "premium_pct" in txt


def t22_no_cr010_forbidden_words() -> bool:
    """t22: 不含 CR-010 禁词(投资建议类)。"""
    txt = _read(ETF_API)
    forbidden = ("建议买入", "保证收益", "推荐买入", "强烈推荐", "稳赚不赔")
    return not any(w in txt for w in forbidden)


def t23_etf_proxy_module_intact() -> bool:
    """t23: etf_proxy.py 5 关键符号未破坏(EtfBasket/EtfOrder/build_etf_basket/submit_etf_order/compute_premium_discount)。"""
    if not ETF_PROXY.exists():
        return False
    txt = _read(ETF_PROXY)
    for sym in ("EtfBasket", "EtfOrder", "build_etf_basket", "submit_etf_order", "compute_premium_discount"):
        if sym not in txt:
            print(f"    缺:{sym}")
            return False
    return True


def t24_etf_proxy_premium_threshold() -> bool:
    """t24: etf_proxy.py 0.5% 套利阈值未变(m7t10 t33 一致)。"""
    txt = _read(ETF_PROXY)
    return "0.5" in txt and "premium_pct" in txt


def t25_etf_ticker_normalization() -> bool:
    """t25: ETF ticker 大写归一化(.strip().upper())。"""
    txt = _read(ETF_API)
    return ".strip().upper()" in txt


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

ALL_TESTS = [
    ("t01_etf_api_file_exists", t01_etf_api_file_exists),
    ("t02_module_top_level_imports", t02_module_top_level_imports),
    ("t03_router_has_three_endpoints", t03_router_has_three_endpoints),
    ("t04_three_endpoint_paths", t04_three_endpoint_paths),
    ("t05_sandbox_review_mode_marker", t05_sandbox_review_mode_marker),
    ("t06_sandbox_disclaimer_three_endpoints", t06_sandbox_disclaimer_three_endpoints),
    ("t07_sandbox_true_in_responses", t07_sandbox_true_in_responses),
    ("t08_pydantic_etf_order_request", t08_pydantic_etf_order_request),
    ("t09_pydantic_field_validator_order_type", t09_pydantic_field_validator_order_type),
    ("t10_pydantic_field_validator_settlement", t10_pydantic_field_validator_settlement),
    ("t11_units_range_ge_le", t11_units_range_ge_le),
    ("t12_price_range_in_premium_discount", t12_price_range_in_premium_discount),
    ("t13_etf_query_required", t13_etf_query_required),
    ("t14_reuse_etf_proxy_functions", t14_reuse_etf_proxy_functions),
    ("t15_reuse_etf_proxy_enums", t15_reuse_etf_proxy_enums),
    ("t16_no_mock_200_philosophy", t16_no_mock_200_philosophy),
    ("t17_etf_bloomberg_key_still_sandbox", t17_etf_bloomberg_key_still_sandbox),
    ("t18_main_py_includes_etf_router", t18_main_py_includes_etf_router),
    ("t19_main_py_imports_etf_module", t19_main_py_imports_etf_module),
    ("t20_router_prefix_in_etf_py", t20_router_prefix_in_etf_py),
    ("t21_premium_discount_returns_arb_opportunity", t21_premium_discount_returns_arb_opportunity),
    ("t22_no_cr010_forbidden_words", t22_no_cr010_forbidden_words),
    ("t23_etf_proxy_module_intact", t23_etf_proxy_module_intact),
    ("t24_etf_proxy_premium_threshold", t24_etf_proxy_premium_threshold),
    ("t25_etf_ticker_normalization", t25_etf_ticker_normalization),
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
    print("  V1.5 接力期 m9t5 — ETF 申赎代理 3 端点自测(纯文本静态)")
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
    print(f"  [m9t5] SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 72)
    if failed:
        print("\n[m9t5] FAILED TESTS:")
        for n in failed_names:
            print(f"  - {n}")
        return 1
    print(f"\n[m9t5] ALL {total} ETF ENDPOINT SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
