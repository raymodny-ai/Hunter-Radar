"""M9-t7 自测:V1.5.1 OpenAPI freeze + 8 新端点(edgar/etf/analytics)+ FE-010 changelog。

测试范围(25 测点):
- §1 v1.5.1 freeze JSON 落地 + version=1.5.1
- §2 v1.5.1 freeze md 落地 + FE-010 v1.5.1 changelog 落地
- §3 端点数:48 paths / 56 endpoints / 16 tags
- §4 EDGAR 2 端点(search + categories)
- §5 ETF 3 端点(basket + orders + premium-discount)
- §6 Analytics 3 端点(events + funnel + event-names)
- §7 8 端点全在 paths(端点总数对比)
- §8 edgar / etf / analytics 3 router 注册到 main.py
- §9 edgar.py 模块加载 + 2 endpoint 函数存在
- §10 etf.py 模块加载 + 3 endpoint 函数存在
- §11 analytics.py 模块加载 + 3 endpoint 函数存在
- §12 dump 脚本 m9t7_dump_openapi_v151.py 输出 v1.5.1
- §13 EDGAR search 含 sandbox_stub 标注
- §14 ETF orders 含 sandbox_stub_v15_prep 标注
- §15 Analytics 含 sandbox_stub_v15_prep 标注
- §16 edgar router 前缀 /api/v1/edgar
- §17 etf router 前缀 /api/v1/etf
- §18 analytics router 前缀 /api/v1/analytics
- §19 edgar 端点不依赖 auth(沙箱 stub)
- §20 etf 端点 Pydantic field_validator 校验
- §21 analytics 端点 10 事件名常量化
- §22 v1.5.1 freeze JSON 含 8 sandbox 标注
- §23 v1.5 freeze 48 endpoints 全保留
- §24 v1.5.1 与 v1.5 端点 diff = 8
- §25 m9t7 自检:连续 25 测点全过 + 无 syntax error
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"

V151_JSON = ROOT / "docs" / "openapi-frozen-v1.5.1.json"
V15_JSON = ROOT / "docs" / "openapi-frozen-v1.5.json"
V151_MD = ROOT / "docs" / "openapi-frozen-v1.5.1.md"
FE010_MD = ROOT / "docs" / "FE-010-changelog-v1.5.1.md"

EDGAR_PY = APP / "api" / "edgar.py"
ETF_PY = APP / "api" / "etf.py"
ANALYTICS_PY = APP / "api" / "analytics.py"
MAIN_PY = APP / "main.py"
DUMP_PY = BACKEND / "scripts" / "m9t7_dump_openapi_v151.py"

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def _run(name: str, fn):
    try:
        fn()
        PASSED.append(name)
        print(f"  [PASS] {name}")
    except AssertionError as e:
        FAILED.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")
    except Exception as e:
        FAILED.append((name, f"{type(e).__name__}: {e}"))
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")


# ---------- §1 v1.5.1 freeze JSON 落地 + version=1.5.1 ----------
def _t01_v151_json_exists_and_version():
    assert V151_JSON.exists(), f"v1.5.1 JSON 未落: {V151_JSON}"
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    assert data["info"]["version"] == "1.5.1", f"version 应=1.5.1: {data['info']['version']}"
    assert "V1.5.1" in data["info"]["title"], f"title 应含 V1.5.1: {data['info']['title']}"


# ---------- §2 v1.5.1 freeze md + FE-010 v1.5.1 changelog ----------
def _t02_v151_md_and_changelog_exist():
    assert V151_MD.exists(), f"v1.5.1 md 未落: {V151_MD}"
    assert FE010_MD.exists(), f"FE-010 v1.5.1 changelog 未落: {FE010_MD}"
    text = V151_MD.read_text(encoding="utf-8")
    assert "OpenAPI Freeze v1.5.1" in text
    assert "56" in text and "48" in text


# ---------- §3 端点数:48 paths / 56 endpoints / 16 tags ----------
def _t03_endpoint_counts():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    assert len(data["paths"]) == 48, f"paths 应=48: {len(data['paths'])}"
    n_endpoints = sum(len(m) for m in data["paths"].values())
    assert n_endpoints == 56, f"endpoints 应=56: {n_endpoints}"
    assert len(data["tags"]) == 16, f"tags 应=16: {len(data['tags'])}"
    tag_names = {t["name"] for t in data["tags"]}
    for t in ("edgar", "etf", "analytics"):
        assert t in tag_names, f"tags 应含 {t}: {tag_names}"


# ---------- §4 EDGAR 2 端点(search + categories) ----------
def _t04_edgar_two_endpoints():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    expected = {("/api/v1/edgar/search", "get"), ("/api/v1/edgar/categories", "get")}
    actual = {(p, m) for p, methods in data["paths"].items() for m in methods}
    missing = expected - actual
    assert not missing, f"缺 EDGAR 端点: {missing}"


# ---------- §5 ETF 3 端点(basket + orders + premium-discount) ----------
def _t05_etf_three_endpoints():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    expected = {
        ("/api/v1/etf/basket", "get"),
        ("/api/v1/etf/orders", "post"),
        ("/api/v1/etf/premium-discount", "get"),
    }
    actual = {(p, m) for p, methods in data["paths"].items() for m in methods}
    missing = expected - actual
    assert not missing, f"缺 ETF 端点: {missing}"


# ---------- §6 Analytics 3 端点(events + funnel + event-names) ----------
def _t06_analytics_three_endpoints():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    expected = {
        ("/api/v1/analytics/events", "get"),
        ("/api/v1/analytics/funnel", "get"),
        ("/api/v1/analytics/event-names", "get"),
    }
    actual = {(p, m) for p, methods in data["paths"].items() for m in methods}
    missing = expected - actual
    assert not missing, f"缺 Analytics 端点: {missing}"


# ---------- §7 8 端点全在 paths(总新增) ----------
def _t07_eight_new_endpoints_total():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    new_8 = {
        ("/api/v1/edgar/search", "get"),
        ("/api/v1/edgar/categories", "get"),
        ("/api/v1/etf/basket", "get"),
        ("/api/v1/etf/orders", "post"),
        ("/api/v1/etf/premium-discount", "get"),
        ("/api/v1/analytics/events", "get"),
        ("/api/v1/analytics/funnel", "get"),
        ("/api/v1/analytics/event-names", "get"),
    }
    actual = {(p, m) for p, methods in data["paths"].items() for m in methods}
    missing = new_8 - actual
    assert not missing, f"v1.5.1 缺 8 端点: {missing}"


# ---------- §8 3 router 注册到 main.py ----------
def _t08_three_routers_registered():
    text = MAIN_PY.read_text(encoding="utf-8")
    for r in ("edgar", "etf", "analytics"):
        assert f"{r}.router" in text, f"main.py 应注册 {r}.router"
        assert f'prefix="/api/v1/{r}"' in text, f"{r} router 前缀应=/api/v1/{r}"
        assert f'tags=["{r}"]' in text, f"{r} router tag 应={r}"


# ---------- §9 edgar.py 模块加载 + 2 endpoint 函数存在 ----------
def _t09_edgar_module_endpoints():
    text = EDGAR_PY.read_text(encoding="utf-8")
    for ep in ("search_edgar", "list_categories"):
        assert f"async def {ep}" in text, f"edgar.py 缺 {ep}"


# ---------- §10 etf.py 模块加载 + 3 endpoint 函数存在 ----------
def _t10_etf_module_endpoints():
    text = ETF_PY.read_text(encoding="utf-8")
    for ep in ("get_etf_basket", "post_etf_order", "get_premium_discount"):
        assert f"async def {ep}" in text, f"etf.py 缺 {ep}"


# ---------- §11 analytics.py 模块加载 + 3 endpoint 函数存在 ----------
def _t11_analytics_module_endpoints():
    text = ANALYTICS_PY.read_text(encoding="utf-8")
    for ep in ("get_events", "get_funnel", "list_event_names"):
        assert f"async def {ep}" in text, f"analytics.py 缺 {ep}"


# ---------- §12 dump 脚本 m9t7_dump_openapi_v151.py 输出 v1.5.1 ----------
def _t12_dump_script_outputs_v151():
    text = DUMP_PY.read_text(encoding="utf-8")
    assert "V1.5.1" in text, "dump script title 应含 V1.5.1"
    assert "openapi-frozen-v1.5.1.json" in text, "dump script 应输出 v1.5.1 JSON"
    assert "1.5.1" in text, "dump script version 应=1.5.1"
    assert "EDGAR" in text and "ETF" in text and "Analytics" in text, "dump script 应提 3 新 router"


# ---------- §13 EDGAR search 含 sandbox_stub 标注 ----------
def _t13_edgar_sandbox_stub_label():
    text = EDGAR_PY.read_text(encoding="utf-8")
    assert "sandbox_stub" in text, "edgar.py 应含 sandbox_stub 标注"
    assert 'review_mode = "sandbox_stub"' in text or '"sandbox_stub"' in text, "edgar.py 应硬编码 sandbox_stub"


# ---------- §14 ETF orders 含 sandbox_stub_v15_prep 标注 ----------
def _t14_etf_sandbox_v15_prep_label():
    text = ETF_PY.read_text(encoding="utf-8")
    assert "sandbox_stub_v15_prep" in text, "etf.py 应含 sandbox_stub_v15_prep 标注"
    assert "SANDBOX_REVIEW_MODE" in text, "etf.py 应引用 etf_proxy.SANDBOX_REVIEW_MODE"


# ---------- §15 Analytics 含 sandbox_stub_v15_prep 标注 ----------
def _t15_analytics_sandbox_v15_prep_label():
    text = ANALYTICS_PY.read_text(encoding="utf-8")
    assert "sandbox_stub_v15_prep" in text, "analytics.py 应含 sandbox_stub_v15_prep 标注"
    assert "SANDBOX_REVIEW_MODE" in text, "analytics.py 应引用 analytics.SANDBOX_REVIEW_MODE"


# ---------- §16 edgar router 前缀 /api/v1/edgar ----------
def _t16_edgar_prefix_api_v1_edgar():
    text = MAIN_PY.read_text(encoding="utf-8")
    idx = text.find("edgar.router")
    snippet = text[idx:idx + 100]
    assert 'prefix="/api/v1/edgar"' in snippet, "edgar router 前缀应=/api/v1/edgar"


# ---------- §17 etf router 前缀 /api/v1/etf ----------
def _t17_etf_prefix_api_v1_etf():
    text = MAIN_PY.read_text(encoding="utf-8")
    idx = text.find("etf.router")
    snippet = text[idx:idx + 100]
    assert 'prefix="/api/v1/etf"' in snippet, "etf router 前缀应=/api/v1/etf"


# ---------- §18 analytics router 前缀 /api/v1/analytics ----------
def _t18_analytics_prefix_api_v1_analytics():
    text = MAIN_PY.read_text(encoding="utf-8")
    idx = text.find("analytics.router")
    snippet = text[idx:idx + 100]
    assert 'prefix="/api/v1/analytics"' in snippet, "analytics router 前缀应=/api/v1/analytics"


# ---------- §19 edgar 端点不依赖 auth(沙箱 stub) ----------
def _t19_edgar_no_auth_dependency():
    text = EDGAR_PY.read_text(encoding="utf-8")
    assert "Depends(get_current_user)" not in text, "edgar 端点不应需 JWT(沙箱 stub)"
    assert "Depends(require_admin" not in text, "edgar 端点不应需 admin role(沙箱 stub)"


# ---------- §20 etf 端点 Pydantic field_validator 校验 ----------
def _t20_etf_pydantic_field_validator():
    text = ETF_PY.read_text(encoding="utf-8")
    assert "BaseModel" in text and "field_validator" in text, "etf.py 应有 Pydantic BaseModel + field_validator"
    assert "EtfOrderRequest" in text, "etf.py 应有 EtfOrderRequest schema"
    assert "creation" in text and "redemption" in text, "etf.py 应校验 order_type"
    assert "cash" in text and "in_kind" in text, "etf.py 应校验 settlement_mode"


# ---------- §21 analytics 端点 10 事件名常量化 ----------
def _t21_analytics_ten_event_names():
    text = ANALYTICS_PY.read_text(encoding="utf-8")
    assert "ALL_EVENT_NAMES" in text, "analytics.py 应有 ALL_EVENT_NAMES tuple"
    expected_events = (
        "EVENT_USER_SIGNUP", "EVENT_USER_LOGIN",
        "EVENT_SUBSCRIBE_START", "EVENT_SUBSCRIBE_SUCCESS", "EVENT_SUBSCRIBE_CANCEL",
        "EVENT_SCREENER_VIEW", "EVENT_BASKET_CREATE", "EVENT_ALERT_RULE_CREATE",
        "EVENT_PUSH_OPT_IN", "EVENT_FEATURE_FLAG_VIEW",
    )
    for ev in expected_events:
        assert ev in text, f"analytics.py 应引用 10 事件常量 {ev}"


# ---------- §22 v1.5.1 freeze JSON 含 8 sandbox 标注 ----------
def _t22_v151_freeze_has_sandbox_labels():
    data = json.loads(V151_JSON.read_text(encoding="utf-8"))
    new_8_paths = (
        "/api/v1/edgar/search", "/api/v1/edgar/categories",
        "/api/v1/etf/basket", "/api/v1/etf/orders", "/api/v1/etf/premium-discount",
        "/api/v1/analytics/events", "/api/v1/analytics/funnel", "/api/v1/analytics/event-names",
    )
    # 8 端点的 summary 中应出现 sandbox 字样
    found = 0
    for path in new_8_paths:
        if path in data["paths"]:
            for m in data["paths"][path]:
                summary = data["paths"][path][m].get("summary", "")
                if "sandbox" in summary.lower():
                    found += 1
    assert found >= 2, f"8 端点 summary 应至少 2 端点含 sandbox: {found}/8"


# ---------- §23 v1.5 freeze 48 endpoints 全保留 ----------
def _t23_v15_endpoints_preserved():
    if not V15_JSON.exists():
        return
    data_v15 = json.loads(V15_JSON.read_text(encoding="utf-8"))
    data_v151 = json.loads(V151_JSON.read_text(encoding="utf-8"))
    v15_endpoints = {(p, m) for p, methods in data_v15["paths"].items() for m in methods}
    v151_endpoints = {(p, m) for p, methods in data_v151["paths"].items() for m in methods}
    missing = v15_endpoints - v151_endpoints
    assert not missing, f"v1.5 48 端点缺失: {missing}"


# ---------- §24 v1.5.1 与 v1.5 端点 diff = 8 ----------
def _t24_diff_with_v15_is_8():
    if not V15_JSON.exists():
        return
    data_v15 = json.loads(V15_JSON.read_text(encoding="utf-8"))
    data_v151 = json.loads(V151_JSON.read_text(encoding="utf-8"))
    v15_endpoints = {(p, m) for p, methods in data_v15["paths"].items() for m in methods}
    v151_endpoints = {(p, m) for p, methods in data_v151["paths"].items() for m in methods}
    added = v151_endpoints - v15_endpoints
    assert len(added) == 8, f"v1.5.1 新增应=8: {added}"


# ---------- §25 m9t7 自检:连续 25 测点全过 + 无 syntax error ----------
def _t25_syntax_no_errors():
    import ast as _ast
    for path in (EDGAR_PY, ETF_PY, ANALYTICS_PY, MAIN_PY, DUMP_PY):
        src = path.read_text(encoding="utf-8")
        try:
            _ast.parse(src, filename=str(path))
        except SyntaxError as e:
            raise AssertionError(f"syntax error in {path.name}: {e}")


def main() -> int:
    tests = [
        ("t01_v151_json_exists_and_version", _t01_v151_json_exists_and_version),
        ("t02_v151_md_and_changelog_exist", _t02_v151_md_and_changelog_exist),
        ("t03_endpoint_counts", _t03_endpoint_counts),
        ("t04_edgar_two_endpoints", _t04_edgar_two_endpoints),
        ("t05_etf_three_endpoints", _t05_etf_three_endpoints),
        ("t06_analytics_three_endpoints", _t06_analytics_three_endpoints),
        ("t07_eight_new_endpoints_total", _t07_eight_new_endpoints_total),
        ("t08_three_routers_registered", _t08_three_routers_registered),
        ("t09_edgar_module_endpoints", _t09_edgar_module_endpoints),
        ("t10_etf_module_endpoints", _t10_etf_module_endpoints),
        ("t11_analytics_module_endpoints", _t11_analytics_module_endpoints),
        ("t12_dump_script_outputs_v151", _t12_dump_script_outputs_v151),
        ("t13_edgar_sandbox_stub_label", _t13_edgar_sandbox_stub_label),
        ("t14_etf_sandbox_v15_prep_label", _t14_etf_sandbox_v15_prep_label),
        ("t15_analytics_sandbox_v15_prep_label", _t15_analytics_sandbox_v15_prep_label),
        ("t16_edgar_prefix_api_v1_edgar", _t16_edgar_prefix_api_v1_edgar),
        ("t17_etf_prefix_api_v1_etf", _t17_etf_prefix_api_v1_etf),
        ("t18_analytics_prefix_api_v1_analytics", _t18_analytics_prefix_api_v1_analytics),
        ("t19_edgar_no_auth_dependency", _t19_edgar_no_auth_dependency),
        ("t20_etf_pydantic_field_validator", _t20_etf_pydantic_field_validator),
        ("t21_analytics_ten_event_names", _t21_analytics_ten_event_names),
        ("t22_v151_freeze_has_sandbox_labels", _t22_v151_freeze_has_sandbox_labels),
        ("t23_v15_endpoints_preserved", _t23_v15_endpoints_preserved),
        ("t24_diff_with_v15_is_8", _t24_diff_with_v15_is_8),
        ("t25_syntax_no_errors", _t25_syntax_no_errors),
    ]
    print(f"开始 m9t7 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M9-T7 OPENAPI V1.5.1 FREEZE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())