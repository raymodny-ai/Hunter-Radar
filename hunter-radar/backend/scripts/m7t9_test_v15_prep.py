"""M7-t9 自测:V1.5 准备(BD-088 ETF 申赎 + 用户增长埋点)。

测试范围(22 测点):
- §1 etf_proxy.py 模块存在 + EtfBasket / EtfOrder dataclass
- §2 EtfOrderType 含 CREATION / REDEMPTION
- §3 EtfSettlementMode 含 CASH / IN_KIND
- §4 EtfOrderStatus 5 态(pending / submitted / confirmed / settled / failed / cancelled)
- §5 build_etf_basket 返 EtfBasket + nav/inav/components
- §6 submit_etf_order 返 EtfOrder + status=PENDING
- §7 compute_premium_discount 算 premium + arb_opportunity
- §8 analytics.py 模块存在 + AnalyticsEvent dataclass
- §9 hash_user_id SHA256 64 hex
- §10 track_event ring buffer 累积 + 返 AnalyticsEvent
- §11 get_recent_events 返 list[dict]
- §12 get_funnel_summary 算 signup → subscribe_success
- §13 reset_for_tests 清空 ring buffer
- §14 docs/bd-088-etf-proxy-design.md 存在 + 8 章节
- §15 docs/analytics-events-spec.md 存在 + 8 章节
- §16 docs/V1.5-eval-checklist.md 存在 + 13 章节
- §17 v1.5 freeze JSON 仍 48 endpoints(未含 etf/analytics 端点)
- §18 etf_proxy 与 analytics 同 sandbox_stub_v15_prep review_mode
- §19 analytics 10 事件名(EVENT_USER_SIGNUP 等)
- §20 V1.5.1 freeze 候选清单含 ETF 3 端点 + analytics events 端点
- §21 R-37~43 风险登记
- §22 不破坏 v1.5 freeze:openapi-frozen-v1.5.json 端点不变
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
ETF_PY = APP / "services" / "etf_proxy.py"
ANALYTICS_PY = APP / "services" / "analytics.py"
BD088_MD = ROOT / "docs" / "bd-088-etf-proxy-design.md"
ANALYTICS_MD = ROOT / "docs" / "analytics-events-spec.md"
V15_EVAL_MD = ROOT / "docs" / "V1.5-eval-checklist.md"
V15_JSON = ROOT / "docs" / "openapi-frozen-v1.5.json"

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


def _load_mod(name: str, path: Path):
    """Python 3.14 dataclass 兼容:注册到 sys.modules。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------- §1 etf_proxy 模块 + dataclass ----------
def _t01_etf_proxy_module():
    mod = _load_mod("etf_proxy", ETF_PY)
    assert hasattr(mod, "EtfBasket"), "缺 EtfBasket"
    assert hasattr(mod, "EtfOrder"), "缺 EtfOrder"


# ---------- §2 EtfOrderType 含 CREATION / REDEMPTION ----------
def _t02_etf_order_type():
    mod = _load_mod("etf_proxy", ETF_PY)
    types = {t.value for t in mod.EtfOrderType}
    assert "creation" in types, f"缺 CREATION: {types}"
    assert "redemption" in types, f"缺 REDEMPTION: {types}"


# ---------- §3 EtfSettlementMode 含 CASH / IN_KIND ----------
def _t03_etf_settlement_mode():
    mod = _load_mod("etf_proxy", ETF_PY)
    modes = {m.value for m in mod.EtfSettlementMode}
    assert "cash" in modes, f"缺 CASH: {modes}"
    assert "in_kind" in modes, f"缺 IN_KIND: {modes}"


# ---------- §4 EtfOrderStatus 6 态 ----------
def _t04_etf_order_status():
    mod = _load_mod("etf_proxy", ETF_PY)
    statuses = {s.value for s in mod.EtfOrderStatus}
    for s in ("pending", "submitted", "confirmed", "settled", "failed", "cancelled"):
        assert s in statuses, f"缺 {s}: {statuses}"


# ---------- §5 build_etf_basket 返 EtfBasket ----------
def _t05_build_etf_basket():
    mod = _load_mod("etf_proxy", ETF_PY)
    b = mod.build_etf_basket("SPY")
    assert b.etf_ticker == "SPY"
    assert b.nav > 0 and b.inav > 0
    assert isinstance(b.components, list) and len(b.components) > 0


# ---------- §6 submit_etf_order 返 EtfOrder ----------
def _t06_submit_etf_order():
    mod = _load_mod("etf_proxy", ETF_PY)
    order = mod.submit_etf_order(
        "SPY", mod.EtfOrderType.CREATION, mod.EtfSettlementMode.IN_KIND, units=2
    )
    assert order.status == mod.EtfOrderStatus.PENDING
    assert order.units == 2
    assert order.review_mode == "sandbox_stub_v15_prep"


# ---------- §7 compute_premium_discount ----------
def _t07_compute_premium_discount():
    mod = _load_mod("etf_proxy", ETF_PY)
    b = mod.build_etf_basket("SPY")
    r = mod.compute_premium_discount(b, market_price=101.0)
    assert r["market_price"] == 101.0
    assert r["premium"] == 1.0
    assert r["premium_pct"] == 1.0  # (101 - 100) / 100 * 100 = 1.0
    assert r["arb_opportunity"] is True  # |1.0| > 0.5
    # discount 场景
    r2 = mod.compute_premium_discount(b, market_price=99.0)
    assert r2["premium_pct"] == -1.0
    assert r2["arb_opportunity"] is True


# ---------- §8 analytics 模块 + AnalyticsEvent ----------
def _t08_analytics_module():
    mod = _load_mod("analytics", ANALYTICS_PY)
    assert hasattr(mod, "AnalyticsEvent"), "缺 AnalyticsEvent"


# ---------- §9 hash_user_id SHA256 64 hex ----------
def _t09_hash_user_id():
    mod = _load_mod("analytics", ANALYTICS_PY)
    h = mod.hash_user_id("user-123")
    assert len(h) == 64, f"SHA256 应 64 hex: {len(h)}"
    assert all(c in "0123456789abcdef" for c in h), "应全 hex 字符"


# ---------- §10 track_event 累积 ring buffer ----------
def _t10_track_event():
    mod = _load_mod("analytics", ANALYTICS_PY)
    mod.reset_for_tests()
    ev = mod.track_event(
        mod.EVENT_USER_SIGNUP, "user-1", {"method": "email"}
    )
    assert ev.event_name == mod.EVENT_USER_SIGNUP
    assert ev.properties["method"] == "email"
    assert len(mod.get_recent_events(10)) == 1


# ---------- §11 get_recent_events 返 list ----------
def _t11_get_recent_events():
    mod = _load_mod("analytics", ANALYTICS_PY)
    mod.reset_for_tests()
    for i in range(5):
        mod.track_event(mod.EVENT_USER_LOGIN, f"user-{i}")
    events = mod.get_recent_events(10)
    assert len(events) == 5
    assert all(isinstance(e, dict) for e in events)


# ---------- §12 get_funnel_summary 算转化率 ----------
def _t12_get_funnel_summary():
    mod = _load_mod("analytics", ANALYTICS_PY)
    mod.reset_for_tests()
    # 模拟漏斗:10 signup → 5 subscribe_start → 2 subscribe_success
    for i in range(10):
        mod.track_event(mod.EVENT_USER_SIGNUP, f"user-{i}")
    for i in range(5):
        mod.track_event(mod.EVENT_SUBSCRIBE_START, f"user-{i}")
    for i in range(2):
        mod.track_event(mod.EVENT_SUBSCRIBE_SUCCESS, f"user-{i}")
    events = mod.get_recent_events(100)
    s = mod.get_funnel_summary(events)
    assert s["unique_users_signup"] == 10
    assert s["unique_users_subscribe_start"] == 5
    assert s["unique_users_subscribe_success"] == 2
    assert s["signup_to_subscribe_start"] == 0.5
    assert s["subscribe_start_to_success"] == 0.4


# ---------- §13 reset_for_tests 清空 ----------
def _t13_reset_for_tests():
    mod = _load_mod("analytics", ANALYTICS_PY)
    mod.track_event(mod.EVENT_USER_LOGIN, "u1")
    assert len(mod.get_recent_events(10)) >= 1
    mod.reset_for_tests()
    assert len(mod.get_recent_events(10)) == 0


# ---------- §14 BD-088 设计 doc ----------
def _t14_bd088_design_doc():
    assert BD088_MD.exists(), f"BD-088 设计 doc 缺失: {BD088_MD}"
    text = BD088_MD.read_text(encoding="utf-8")
    # 检查 8 个章节标题
    sections = ["## 一、背景", "## 二、V1.5 范围", "## 三、数据模型",
                "## 四、状态机", "## 五、套利机会检测", "## 六、V1.5+ 真实落地步骤",
                "## 七、风险与遗留", "## 八、本日记忆"]
    for s in sections:
        assert s in text, f"BD-088 设计 doc 缺章节 {s}"


# ---------- §15 analytics spec doc ----------
def _t15_analytics_spec_doc():
    assert ANALYTICS_MD.exists(), f"analytics spec doc 缺失: {ANALYTICS_MD}"
    text = ANALYTICS_MD.read_text(encoding="utf-8")
    sections = ["## 一、目标", "## 二、事件 Schema", "## 三、事件清单(V1.5 spec)",
                "## 四、漏斗计算", "## 五、技术架构(V1.5+)",
                "## 六、与 V1.4 既有逻辑的对接", "## 七、风险与遗留", "## 八、本日记忆"]
    for s in sections:
        assert s in text, f"analytics spec doc 缺章节 {s}"


# ---------- §16 V1.5 eval checklist doc ----------
def _t16_v15_eval_doc():
    assert V15_EVAL_MD.exists(), f"V1.5 eval checklist 缺失: {V15_EVAL_MD}"
    text = V15_EVAL_MD.read_text(encoding="utf-8")
    # 13 章节(主标题)
    for sec in ("## 一、背景", "## 二、候选 A 权重(M7-t4 落地)",
                "## 三、BD-086 双签(M7-t2 落地)",
                "## 四、BD-085 真实数据集(M7-t3 落地)",
                "## 五、BD-087 v3.0-final 校准(M7-t4 落地)",
                "## 六、EDGAR fulltext search(M7-t5 落地)",
                "## 七、Stripe webhook 签名校验(M7-t6 落地)",
                "## 八、OpenAPI v1.5 freeze(M7-t7 落地)",
                "## 九、PWA + CI(M7-t8 落地)",
                "## 十、BD-088 ETF 申赎代理(M7-t9 落地 stub)",
                "## 十一、用户增长埋点(M7-t9 落地 stub)",
                "## 十二、V1.5.1 freeze 候选清单", "## 十三、本日记忆(M7-t9)"):
        assert sec in text, f"V1.5 eval 缺章节 {sec}"


# ---------- §17 v1.5 freeze 仍 48 endpoints ----------
def _t17_v15_freeze_unchanged():
    data = json.loads(V15_JSON.read_text(encoding="utf-8"))
    n = sum(len(m) for m in data["paths"].values())
    assert n == 48, f"v1.5 freeze 应仍=48(etf/analytics 未加): {n}"
    # 校验无 etf/analytics 端点
    for p in data["paths"]:
        assert "/etf/" not in p, f"v1.5 freeze 不应有 etf 端点: {p}"
        assert "/analytics/" not in p, f"v1.5 freeze 不应有 analytics 端点: {p}"


# ---------- §18 etf + analytics 同 review_mode ----------
def _t18_sandbox_review_mode_shared():
    etf = _load_mod("etf_proxy", ETF_PY)
    analytics = _load_mod("analytics", ANALYTICS_PY)
    assert etf.SANDBOX_REVIEW_MODE == "sandbox_stub_v15_prep"
    assert analytics.SANDBOX_REVIEW_MODE == "sandbox_stub_v15_prep"


# ---------- §19 analytics 10 事件名 ----------
def _t19_analytics_10_events():
    mod = _load_mod("analytics", ANALYTICS_PY)
    expected = (
        mod.EVENT_USER_SIGNUP, mod.EVENT_USER_LOGIN,
        mod.EVENT_SUBSCRIBE_START, mod.EVENT_SUBSCRIBE_SUCCESS, mod.EVENT_SUBSCRIBE_CANCEL,
        mod.EVENT_SCREENER_VIEW, mod.EVENT_BASKET_CREATE, mod.EVENT_ALERT_RULE_CREATE,
        mod.EVENT_PUSH_OPT_IN, mod.EVENT_FEATURE_FLAG_VIEW
    )
    assert len(expected) == 10, f"应有 10 事件: {len(expected)}"
    assert len(set(expected)) == 10, "事件名应唯一"


# ---------- §20 V1.5.1 freeze 候选清单含 ETF + analytics ----------
def _t20_v15_1_freeze_candidates():
    text = V15_EVAL_MD.read_text(encoding="utf-8")
    assert "/api/v1/etf/" in text, "V1.5 eval 应提 etf 端点"
    assert "/api/v1/analytics/" in text, "V1.5 eval 应提 analytics 端点"
    assert "V1.5.1" in text, "V1.5 eval 应提 V1.5.1 freeze"


# ---------- §21 R-37~43 风险登记 ----------
def _t21_r37_risks_registered():
    bd088 = BD088_MD.read_text(encoding="utf-8")
    analytics = ANALYTICS_MD.read_text(encoding="utf-8")
    eval_md = V15_EVAL_MD.read_text(encoding="utf-8")
    for r in ("R-37", "R-38", "R-39", "R-40", "R-41", "R-42", "R-43"):
        # R-37~39 在 BD-088 / R-40~43 在 analytics spec
        # 至少在 eval checklist 中也应提
        assert r in bd088 or r in analytics or r in eval_md, f"风险 {r} 未登记"


# ---------- §22 不破坏 v1.5 freeze(openapi 端点不变)----------
def _t22_no_openapi_drift():
    if not V15_JSON.exists():
        return  # 没生成过 v1.5 freeze 时跳过
    data = json.loads(V15_JSON.read_text(encoding="utf-8"))
    # 校验 admin 端点(上次 m7t7 落的)仍在
    assert "/api/v1/admin/etl/run" in data["paths"], "v1.5 admin 应保留"
    assert "/api/v1/admin/backtest/result" in data["paths"], "v1.5 admin 应保留"


def main() -> int:
    tests = [
        ("t01_etf_proxy_module", _t01_etf_proxy_module),
        ("t02_etf_order_type", _t02_etf_order_type),
        ("t03_etf_settlement_mode", _t03_etf_settlement_mode),
        ("t04_etf_order_status", _t04_etf_order_status),
        ("t05_build_etf_basket", _t05_build_etf_basket),
        ("t06_submit_etf_order", _t06_submit_etf_order),
        ("t07_compute_premium_discount", _t07_compute_premium_discount),
        ("t08_analytics_module", _t08_analytics_module),
        ("t09_hash_user_id", _t09_hash_user_id),
        ("t10_track_event", _t10_track_event),
        ("t11_get_recent_events", _t11_get_recent_events),
        ("t12_get_funnel_summary", _t12_get_funnel_summary),
        ("t13_reset_for_tests", _t13_reset_for_tests),
        ("t14_bd088_design_doc", _t14_bd088_design_doc),
        ("t15_analytics_spec_doc", _t15_analytics_spec_doc),
        ("t16_v15_eval_doc", _t16_v15_eval_doc),
        ("t17_v15_freeze_unchanged", _t17_v15_freeze_unchanged),
        ("t18_sandbox_review_mode_shared", _t18_sandbox_review_mode_shared),
        ("t19_analytics_10_events", _t19_analytics_10_events),
        ("t20_v15_1_freeze_candidates", _t20_v15_1_freeze_candidates),
        ("t21_r37_risks_registered", _t21_r37_risks_registered),
        ("t22_no_openapi_drift", _t22_no_openapi_drift),
    ]
    print(f"开始 m7t9 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M7-T9 V1.5 PREP TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())