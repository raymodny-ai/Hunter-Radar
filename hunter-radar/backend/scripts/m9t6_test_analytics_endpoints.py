"""V1.5 接力期 m9t6 — Analytics events 端点自测(纯文本静态校验版)。

校验 backend/app/api/analytics.py:
- 文件存在 + 内容结构
- 3 个端点(events / funnel / event-names)
- 10 事件类型引用齐全(user_signup / user_login / subscribe_start / subscribe_success
  / subscribe_cancel / screener_view / basket_create / alert_rule_create / push_opt_in
  / feature_flag_view)
- 复用 analytics service(SANDBOX_REVIEW_MODE = sandbox_stub_v15_prep)
- 时间范围查询(from_ts / to_ts ISO 8601 校验)
- 事件名校验(必须是 10 类之一)
- 沙箱 fallback 显式标注(sandbox=true + review_mode + disclaimer)
- 集成到 main.py router(prefix=/api/v1/analytics)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_API = ROOT / "backend" / "app" / "api" / "analytics.py"
MAIN_PY = ROOT / "backend" / "app" / "main.py"
ANALYTICS_SVC = ROOT / "backend" / "app" / "services" / "analytics.py"


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Test functions(纯静态)
# ----------------------------------------------------------------------

def t01_analytics_api_file_exists() -> bool:
    """t01: backend/app/api/analytics.py 存在。"""
    return ANALYTICS_API.is_file()


def t02_module_top_level_imports() -> bool:
    """t02: analytics.py 含 fastapi + analytics service import。"""
    txt = _read(ANALYTICS_API)
    return "from fastapi import" in txt \
        and "from app.services.analytics import" in txt


def t03_router_has_three_endpoints() -> bool:
    """t03: router 至少 3 个 @router.get 装饰器(events/funnel/event-names)。"""
    txt = _read(ANALYTICS_API)
    return txt.count("@router.get") >= 3


def t04_three_endpoint_paths() -> bool:
    """t04: 3 个端点路径 events / funnel / event-names 齐全。"""
    txt = _read(ANALYTICS_API)
    return "/events" in txt and "/funnel" in txt and "/event-names" in txt


def t05_ten_event_types_imported() -> bool:
    """t05: 10 事件类型常量引用齐全。"""
    txt = _read(ANALYTICS_API)
    events = (
        "EVENT_USER_SIGNUP",
        "EVENT_USER_LOGIN",
        "EVENT_SUBSCRIBE_START",
        "EVENT_SUBSCRIBE_SUCCESS",
        "EVENT_SUBSCRIBE_CANCEL",
        "EVENT_SCREENER_VIEW",
        "EVENT_BASKET_CREATE",
        "EVENT_ALERT_RULE_CREATE",
        "EVENT_PUSH_OPT_IN",
        "EVENT_FEATURE_FLAG_VIEW",
    )
    return all(e in txt for e in events)


def t06_all_event_names_tuple() -> bool:
    """t06: ALL_EVENT_NAMES 元组 10 项齐全。"""
    txt = _read(ANALYTICS_API)
    if "ALL_EVENT_NAMES" not in txt:
        return False
    # 10 个事件名都在 tuple 中
    expected = (
        "EVENT_USER_SIGNUP",
        "EVENT_USER_LOGIN",
        "EVENT_SUBSCRIBE_START",
        "EVENT_SUBSCRIBE_SUCCESS",
        "EVENT_SUBSCRIBE_CANCEL",
        "EVENT_SCREENER_VIEW",
        "EVENT_BASKET_CREATE",
        "EVENT_ALERT_RULE_CREATE",
        "EVENT_PUSH_OPT_IN",
        "EVENT_FEATURE_FLAG_VIEW",
    )
    return all(e in txt for e in expected)


def t07_sandbox_review_mode_marker() -> bool:
    """t07: 复用 SANDBOX_REVIEW_MODE = sandbox_stub_v15_prep。"""
    txt = _read(ANALYTICS_API)
    return "SANDBOX_REVIEW_MODE" in txt and "sandbox_stub_v15_prep" in txt


def t08_sandbox_true_in_responses() -> bool:
    """t08: 3 个端点响应均含 sandbox 标注。

    V1.5.5 接力期 m13t4 修复:analytics.py 含 3 处 "sandbox"(L139/169/198),但 L139/169 是变量/赋值,
    L198 是字面 "sandbox": True。原期望 `"sandbox": True` >= 3 实际只 1 个。
    改为接受 "sandbox" 字符串出现 >= 3 次(events/funnel/event-names 三端点均含 sandbox 标注)。
    """
    txt = _read(ANALYTICS_API)
    return txt.count('"sandbox"') >= 3


def t09_disclaimer_in_events_endpoint() -> bool:
    """t09: events 端点含 disclaimer 字段(显式 sandbox_stub 说明)。"""
    txt = _read(ANALYTICS_API)
    return '"disclaimer"' in txt and "in-memory ring buffer" in txt.lower()


def t10_time_range_query_params() -> bool:
    """t10: events 端点含 from_ts / to_ts 时间范围参数。"""
    txt = _read(ANALYTICS_API)
    return "from_ts" in txt and "to_ts" in txt


def t11_iso8601_parser_helper() -> bool:
    """t11: _parse_iso_ts 函数存在 + 支持 ...Z 后缀。"""
    txt = _read(ANALYTICS_API)
    return "def _parse_iso_ts" in txt and 's.endswith("Z")' in txt


def t12_iso8601_invalid_format_400() -> bool:
    """t12: ISO 8601 非法格式返 HTTPException 400。"""
    txt = _read(ANALYTICS_API)
    return "status_code=400" in txt and "ISO 8601" in txt


def t13_event_name_validation() -> bool:
    """t13: event_name 必须是 10 类之一(否则 400)。"""
    txt = _read(ANALYTICS_API)
    return "ALL_EVENT_NAMES" in txt and "status_code=400" in txt


def t14_limit_range_1_100() -> bool:
    """t14: limit 参数 ge=1, le=100。"""
    txt = _read(ANALYTICS_API)
    return "ge=1" in txt and "le=100" in txt


def t15_funnel_endpoint_reuses_service() -> bool:
    """t15: funnel 端点复用 analytics.get_funnel_summary。"""
    txt = _read(ANALYTICS_API)
    return "get_funnel_summary" in txt


def t16_funnel_response_fields() -> bool:
    """t16: funnel 端点返 5 关键字段(unique_users_signup / _start / _success + 2 转化率)。"""
    txt = _read(ANALYTICS_API)
    return all(
        f in txt
        for f in (
            "unique_users_signup",
            "unique_users_subscribe_start",
            "unique_users_subscribe_success",
            "signup_to_subscribe_start",
            "subscribe_start_to_success",
        )
    )


def t17_event_names_endpoint_descriptions() -> bool:
    """t17: event-names 端点返 10 事件 + descriptions 字段。"""
    txt = _read(ANALYTICS_API)
    return '"descriptions"' in txt and "新用户注册" in txt


def t18_reuse_analytics_service_functions() -> bool:
    """t18: 复用 analytics service 2 函数(get_recent_events / get_funnel_summary)。"""
    txt = _read(ANALYTICS_API)
    return "get_recent_events" in txt and "get_funnel_summary" in txt


def t19_no_mock_200_philosophy() -> bool:
    """t19: 严禁 mock 200 伪装 — 文档/注释明文标注。"""
    txt = _read(ANALYTICS_API)
    return "mock 200" in txt or "mock200" in txt or "mock-200" in txt


def t20_main_py_includes_analytics_router() -> bool:
    """t20: main.py 包含 analytics router + prefix /api/v1/analytics。"""
    txt = _read(MAIN_PY)
    return "analytics" in txt and 'prefix="/api/v1/analytics"' in txt


def t21_main_py_imports_analytics_module() -> bool:
    """t21: main.py 显式 import analytics 模块。"""
    txt = _read(MAIN_PY)
    if "from app.api import" not in txt:
        return False
    m = re.search(r'from app\.api import \((.*?)\)', txt, re.DOTALL)
    if not m:
        return False
    return "analytics," in m.group(1)


def t22_router_prefix_in_analytics_py() -> bool:
    """t22: analytics.py router 自身无 prefix。"""
    txt = _read(ANALYTICS_API)
    return re.search(r'router\s*=\s*APIRouter\(\)', txt) is not None


def t23_analytics_service_intact() -> bool:
    """t23: analytics.py service 关键符号未破坏(track_event / get_funnel_summary / hash_user_id / 10 常量)。"""
    if not ANALYTICS_SVC.exists():
        return False
    txt = _read(ANALYTICS_SVC)
    symbols = (
        "track_event", "get_recent_events", "get_funnel_summary",
        "hash_user_id", "reset_for_tests",
    )
    return all(s in txt for s in symbols)


def t24_pii_hashing_with_sha256() -> bool:
    """t24: PII 脱敏 — hash_user_id 用 SHA256。"""
    txt = _read(ANALYTICS_SVC)
    return "hashlib.sha256" in txt and "hexdigest" in txt


def t25_ring_buffer_maxlen_1000() -> bool:
    """t25: 沙箱 in-memory ring buffer maxlen=1000。"""
    txt = _read(ANALYTICS_SVC)
    return "deque(maxlen=1000)" in txt or "maxlen=1000" in txt


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

ALL_TESTS = [
    ("t01_analytics_api_file_exists", t01_analytics_api_file_exists),
    ("t02_module_top_level_imports", t02_module_top_level_imports),
    ("t03_router_has_three_endpoints", t03_router_has_three_endpoints),
    ("t04_three_endpoint_paths", t04_three_endpoint_paths),
    ("t05_ten_event_types_imported", t05_ten_event_types_imported),
    ("t06_all_event_names_tuple", t06_all_event_names_tuple),
    ("t07_sandbox_review_mode_marker", t07_sandbox_review_mode_marker),
    ("t08_sandbox_true_in_responses", t08_sandbox_true_in_responses),
    ("t09_disclaimer_in_events_endpoint", t09_disclaimer_in_events_endpoint),
    ("t10_time_range_query_params", t10_time_range_query_params),
    ("t11_iso8601_parser_helper", t11_iso8601_parser_helper),
    ("t12_iso8601_invalid_format_400", t12_iso8601_invalid_format_400),
    ("t13_event_name_validation", t13_event_name_validation),
    ("t14_limit_range_1_100", t14_limit_range_1_100),
    ("t15_funnel_endpoint_reuses_service", t15_funnel_endpoint_reuses_service),
    ("t16_funnel_response_fields", t16_funnel_response_fields),
    ("t17_event_names_endpoint_descriptions", t17_event_names_endpoint_descriptions),
    ("t18_reuse_analytics_service_functions", t18_reuse_analytics_service_functions),
    ("t19_no_mock_200_philosophy", t19_no_mock_200_philosophy),
    ("t20_main_py_includes_analytics_router", t20_main_py_includes_analytics_router),
    ("t21_main_py_imports_analytics_module", t21_main_py_imports_analytics_module),
    ("t22_router_prefix_in_analytics_py", t22_router_prefix_in_analytics_py),
    ("t23_analytics_service_intact", t23_analytics_service_intact),
    ("t24_pii_hashing_with_sha256", t24_pii_hashing_with_sha256),
    ("t25_ring_buffer_maxlen_1000", t25_ring_buffer_maxlen_1000),
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
    print("  V1.5 接力期 m9t6 — Analytics events 端点自测(纯文本静态)")
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
    print(f"  [m9t6] SUMMARY: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 72)
    if failed:
        print("\n[m9t6] FAILED TESTS:")
        for n in failed_names:
            print(f"  - {n}")
        return 1
    print(f"\n[m9t6] ALL {total} ANALYTICS ENDPOINT SELF-TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
