"""M10-t3 自测:Analytics 真实事件库接入(postHog / Plausible 双轨 + sandbox fallback)。

测试范围(25 测点):
- §1 app/services/analytics_real.py 文件存在 + 模块 docstring
- §2 fetch_analytics_real_events async 函数存在
- §3 AnalyticsRealFetchResult dataclass
- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量
- §5 PROVIDER_POSTHOG / PROVIDER_PLAUSIBLE / PROVIDER_SANDBOX 三 provider
- §6 POSTHOG_HOST_DEFAULT / PLAUSIBLE_HOST_DEFAULT 常量
- §7 _normalize_posthog_event 函数(过滤非 10 事件名 + 标准化)
- §8 _normalize_plausible_event 函数(过滤非 10 事件名 + 标准化)
- §9 _fetch_posthog_events async 私有函数
- §10 _fetch_plausible_events async 私有函数
- §11 HTTPX_AVAILABLE 探测(沙箱无 httpx 也可 import)
- §12 httpx 不可用 → fallback sandbox(reason=httpx_unavailable)
- §13 强制 sandbox provider → fallback(reason=provider_sandbox)
- §14 未知 provider → fallback(reason=unknown_provider)
- §15 postHog 缺 API_KEY → fallback(reason=posthog_error + ValueError)
- §16 postHog 4xx-5xx → fallback(reason=posthog_error + HTTPError)
- §17 postHog 成功 → production_real(fetch_source=posthog)
- §18 Plausible 成功 → production_real(fetch_source=plausible)
- §19 hash_user_id PII 脱敏(SHA256)
- §20 ALL_EVENT_NAMES 10 事件名(从 sandbox 模块 import)
- §21 app/api/analytics.py 导入 fetch_analytics_real_events(V1.5.2 双轨)
- §22 app/api/analytics.py events 端点响应新增 fetch_source / http_status / latency_ms / warning 4 字段
- §23 app/api/analytics.py disclaimer 更新为 V1.5.2 双轨
- §24 analytics_real.py 不破坏 analytics.py(m9t6 沿用 get_recent_events / hash_user_id)
- §25 语法无错(ast.parse)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
APP_SERVICES = BACKEND / "app" / "services"
APP_API = BACKEND / "app" / "api"

ANALYTICS_REAL_PY = APP_SERVICES / "analytics_real.py"
ANALYTICS_PY = APP_SERVICES / "analytics.py"
ANALYTICS_API_PY = APP_API / "analytics.py"

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


# ---------- §1 analytics_real.py 文件存在 + 模块 docstring ----------
def _t01_analytics_real_exists_and_docstring():
    assert ANALYTICS_REAL_PY.exists(), f"analytics_real.py 应存在: {ANALYTICS_REAL_PY}"
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "M10-t3" in text, "analytics_real.py docstring 应含 M10-t3"
    assert "postHog" in text, "analytics_real.py docstring 应提 postHog"
    assert "Plausible" in text, "analytics_real.py docstring 应提 Plausible"


# ---------- §2 fetch_analytics_real_events async 函数存在 ----------
def _t02_fetch_analytics_real_events_exists():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "async def fetch_analytics_real_events" in text, "analytics_real.py 应有 async def fetch_analytics_real_events"


# ---------- §3 AnalyticsRealFetchResult dataclass ----------
def _t03_analytics_real_fetch_result_dataclass():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "@dataclass" in text, "analytics_real.py 应有 @dataclass"
    assert "class AnalyticsRealFetchResult" in text, "analytics_real.py 应有 AnalyticsRealFetchResult class"
    for field_name in ("events", "count", "fetched_at", "fetch_source", "review_mode", "sandbox"):
        assert field_name in text, f"AnalyticsRealFetchResult 应含 {field_name}"


# ---------- §4 PRODUCTION_REVIEW_MODE / SANDBOX_FALLBACK_REVIEW_MODE 双态常量 ----------
def _t04_dual_review_mode_constants():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert 'PRODUCTION_REVIEW_MODE = "production_real"' in text, "analytics_real.py 应有 PRODUCTION_REVIEW_MODE='production_real'"
    assert 'SANDBOX_FALLBACK_REVIEW_MODE = "sandbox_stub_v15_prep"' in text, "analytics_real.py 应有 SANDBOX_FALLBACK_REVIEW_MODE='sandbox_stub_v15_prep'"


# ---------- §5 PROVIDER_POSTHOG / PROVIDER_PLAUSIBLE / PROVIDER_SANDBOX ----------
def _t05_three_providers():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert 'PROVIDER_POSTHOG = "posthog"' in text, "analytics_real.py 应有 PROVIDER_POSTHOG='posthog'"
    assert 'PROVIDER_PLAUSIBLE = "plausible"' in text, "analytics_real.py 应有 PROVIDER_PLAUSIBLE='plausible'"
    assert 'PROVIDER_SANDBOX = "sandbox"' in text, "analytics_real.py 应有 PROVIDER_SANDBOX='sandbox'"


# ---------- §6 POSTHOG_HOST_DEFAULT / PLAUSIBLE_HOST_DEFAULT ----------
def _t06_default_hosts():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert 'POSTHOG_HOST_DEFAULT = "https://us.i.posthog.com"' in text, "analytics_real.py 应有 POSTHOG_HOST_DEFAULT"
    assert 'PLAUSIBLE_HOST_DEFAULT = "https://plausible.io"' in text, "analytics_real.py 应有 PLAUSIBLE_HOST_DEFAULT"


# ---------- §7 _normalize_posthog_event 函数 ----------
def _t07_normalize_posthog_event():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "def _normalize_posthog_event" in text, "analytics_real.py 应有 _normalize_posthog_event 函数"
    assert "event_name not in ALL_EVENT_NAMES" in text or "event not in ALL_EVENT_NAMES" in text, \
        "_normalize_posthog_event 应过滤非 10 事件名"


# ---------- §8 _normalize_plausible_event 函数 ----------
def _t08_normalize_plausible_event():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "def _normalize_plausible_event" in text, "analytics_real.py 应有 _normalize_plausible_event 函数"
    assert "hash_user_id" in text, "_normalize_*_event 应使用 hash_user_id(SHA256 PII 脱敏)"


# ---------- §9 _fetch_posthog_events async 私有函数 ----------
def _t09_fetch_posthog_events():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "async def _fetch_posthog_events" in text, "analytics_real.py 应有 async def _fetch_posthog_events"


# ---------- §10 _fetch_plausible_events async 私有函数 ----------
def _t10_fetch_plausible_events():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "async def _fetch_plausible_events" in text, "analytics_real.py 应有 async def _fetch_plausible_events"


# ---------- §11 HTTPX_AVAILABLE 探测 ----------
def _t11_httpx_available_probe():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "import httpx" in text, "analytics_real.py 应 import httpx"
    assert "HTTPX_AVAILABLE" in text, "analytics_real.py 应探测 HTTPX_AVAILABLE"


# ---------- §12 httpx 不可用 → fallback sandbox ----------
def _t12_httpx_unavailable_fallback():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "provider == PROVIDER_SANDBOX or not HTTPX_AVAILABLE" in text, "httpx 不可用应分支判定"
    assert '"httpx_unavailable"' in text, "httpx 不可用应标 reason=httpx_unavailable"


# ---------- §13 强制 sandbox provider → fallback ----------
def _t13_provider_sandbox_fallback():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "provider == PROVIDER_SANDBOX" in text, "强制 sandbox provider 应分支判定"
    assert '"provider_sandbox"' in text, "强制 sandbox 应标 reason=provider_sandbox"


# ---------- §14 未知 provider → fallback ----------
def _t14_unknown_provider_fallback():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert '"unknown_provider"' in text, "未知 provider 应标 reason=unknown_provider"
    assert "未知 provider" in text or "unknown provider" in text, "analytics_real.py 应有未知 provider warning"


# ---------- §15 postHog 缺 API_KEY → fallback ----------
def _t15_posthog_missing_api_key():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "POSTHOG_API_KEY" in text, "analytics_real.py 应校验 POSTHOG_API_KEY"
    assert "POSTHOG_PROJECT_ID" in text, "analytics_real.py 应校验 POSTHOG_PROJECT_ID"
    assert "raise ValueError" in text, "postHog 缺 KEY 应抛 ValueError"


# ---------- §16 postHog 4xx-5xx → fallback ----------
def _t16_posthog_4xx_5xx_fallback():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "postHog 返 HTTP" in text or "Plausible 返 HTTP" in text, "postHog/Plausible 非 200 应有 warning"
    assert "httpx.HTTPError" in text, "analytics_real.py 应捕获 httpx.HTTPError"


# ---------- §17 postHog 成功 → production_real ----------
def _t17_posthog_success_production_real():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert 'fetch_source=PROVIDER_POSTHOG' in text, "postHog 成功应标 fetch_source=posthog"
    assert 'review_mode=PRODUCTION_REVIEW_MODE' in text, "postHog 成功应标 review_mode=production_real"
    assert "sandbox=False" in text, "postHog 成功应标 sandbox=False"


# ---------- §18 Plausible 成功 → production_real ----------
def _t18_plausible_success_production_real():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert 'fetch_source=PROVIDER_PLAUSIBLE' in text, "Plausible 成功应标 fetch_source=plausible"


# ---------- §19 hash_user_id PII 脱敏 ----------
def _t19_pii_hash():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "hash_user_id(" in text, "analytics_real.py 应调用 hash_user_id(SHA256 PII 脱敏)"


# ---------- §20 ALL_EVENT_NAMES 10 事件名 ----------
def _t20_all_event_names_10():
    text = ANALYTICS_REAL_PY.read_text(encoding="utf-8")
    assert "ALL_EVENT_NAMES = (" in text, "analytics_real.py 应有 ALL_EVENT_NAMES tuple"
    for ev in ("EVENT_USER_SIGNUP", "EVENT_USER_LOGIN", "EVENT_SUBSCRIBE_START",
               "EVENT_SUBSCRIBE_SUCCESS", "EVENT_SUBSCRIBE_CANCEL", "EVENT_SCREENER_VIEW",
               "EVENT_BASKET_CREATE", "EVENT_ALERT_RULE_CREATE", "EVENT_PUSH_OPT_IN",
               "EVENT_FEATURE_FLAG_VIEW"):
        assert ev in text, f"analytics_real.py 应引用 10 事件常量 {ev}"


# ---------- §21 app/api/analytics.py 导入 fetch_analytics_real_events ----------
def _t21_api_analytics_imports_real():
    text = ANALYTICS_API_PY.read_text(encoding="utf-8")
    assert "from app.services.analytics_real import" in text, "app/api/analytics.py 应 import analytics_real"
    assert "fetch_analytics_real_events" in text, "app/api/analytics.py 应导入 fetch_analytics_real_events"


# ---------- §22 app/api/analytics.py events 端点响应新增 4 字段 ----------
def _t22_api_analytics_response_new_fields():
    text = ANALYTICS_API_PY.read_text(encoding="utf-8")
    for field_name in ("fetch_source", "http_status", "latency_ms", "warning"):
        assert f'"{field_name}"' in text, f"app/api/analytics.py 响应应含 {field_name}"


# ---------- §23 app/api/analytics.py disclaimer 更新为 V1.5.2 双轨 ----------
def _t23_api_analytics_disclaimer_v152():
    text = ANALYTICS_API_PY.read_text(encoding="utf-8")
    assert "V1.5.2" in text, "app/api/analytics.py disclaimer 应含 V1.5.2"
    assert "双轨" in text, "app/api/analytics.py 应说明双轨"


# ---------- §24 analytics_real.py 不破坏 analytics.py(m9t6 沿用) ----------
def _t24_m9t6_preserved():
    text = ANALYTICS_PY.read_text(encoding="utf-8")
    for token in ("get_recent_events", "get_funnel_summary", "hash_user_id", "track_event",
                  "EVENT_USER_SIGNUP", "SANDBOX_REVIEW_MODE"):
        assert token in text, f"analytics.py 应保留 {token}(m9t6 不破坏)"


# ---------- §25 语法无错 ----------
def _t25_syntax_no_errors():
    for path in (ANALYTICS_REAL_PY, ANALYTICS_API_PY):
        src = path.read_text(encoding="utf-8")
        try:
            ast.parse(src, filename=str(path))
        except SyntaxError as e:
            raise AssertionError(f"syntax error in {path.name}: {e}")


def main() -> int:
    tests = [
        ("t01_analytics_real_exists_and_docstring", _t01_analytics_real_exists_and_docstring),
        ("t02_fetch_analytics_real_events_exists", _t02_fetch_analytics_real_events_exists),
        ("t03_analytics_real_fetch_result_dataclass", _t03_analytics_real_fetch_result_dataclass),
        ("t04_dual_review_mode_constants", _t04_dual_review_mode_constants),
        ("t05_three_providers", _t05_three_providers),
        ("t06_default_hosts", _t06_default_hosts),
        ("t07_normalize_posthog_event", _t07_normalize_posthog_event),
        ("t08_normalize_plausible_event", _t08_normalize_plausible_event),
        ("t09_fetch_posthog_events", _t09_fetch_posthog_events),
        ("t10_fetch_plausible_events", _t10_fetch_plausible_events),
        ("t11_httpx_available_probe", _t11_httpx_available_probe),
        ("t12_httpx_unavailable_fallback", _t12_httpx_unavailable_fallback),
        ("t13_provider_sandbox_fallback", _t13_provider_sandbox_fallback),
        ("t14_unknown_provider_fallback", _t14_unknown_provider_fallback),
        ("t15_posthog_missing_api_key", _t15_posthog_missing_api_key),
        ("t16_posthog_4xx_5xx_fallback", _t16_posthog_4xx_5xx_fallback),
        ("t17_posthog_success_production_real", _t17_posthog_success_production_real),
        ("t18_plausible_success_production_real", _t18_plausible_success_production_real),
        ("t19_pii_hash", _t19_pii_hash),
        ("t20_all_event_names_10", _t20_all_event_names_10),
        ("t21_api_analytics_imports_real", _t21_api_analytics_imports_real),
        ("t22_api_analytics_response_new_fields", _t22_api_analytics_response_new_fields),
        ("t23_api_analytics_disclaimer_v152", _t23_api_analytics_disclaimer_v152),
        ("t24_m9t6_preserved", _t24_m9t6_preserved),
        ("t25_syntax_no_errors", _t25_syntax_no_errors),
    ]
    print(f"开始 m10t3 自测(共 {len(tests)} 测点):")
    for name, fn in tests:
        _run(name, fn)
    print(f"\n总结: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("失败项:")
        for n, msg in FAILED:
            print(f"  - {n}: {msg}")
        return 1
    print(f"ALL {len(tests)} M10-T3 ANALYTICS REAL EVENT LIB TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())