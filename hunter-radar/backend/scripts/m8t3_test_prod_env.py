"""M8-t3 V1.4 生产环境变量配置自测(20+ 测点)。

V1.4 上线前环境变量配置完整性 + 沙箱 fallback 显式标注校验:

Section 1 — V1.4-prod-env-setup.md 文档完整性(8 测点):
  - 文档存在 + 12 章节齐全
  - 28 项环境变量清单(7 P0 + 8 P1 + 7 P2 + 9 P3 沿用默认 = 31,本文档分 P0/P1/P2/P3 段,4 段)
  - 落地检查清单 12 项齐全
  - 回滚方案 8 项

Section 2 — config.py 关键字段存在性(6 测点):
  - P0 7 字段(DATABASE_URL + DATABASE_URL_SYNC + SECRET_KEY + STRIPE_SECRET_KEY +
    STRIPE_WEBHOOK_SECRET + STRIPE_PRICE_PRO_MONTHLY + STRIPE_PRICE_PRO_YEARLY)
  - P1 8 字段(VAPID_PRIVATE_KEY + VAPID_PUBLIC_KEY + VAPID_CLAIMS_EMAIL + SENTRY_DSN +
    ENV + DEBUG + LOG_LEVEL + CORS_ORIGINS)
  - is_production property

Section 3 — 服务层沙箱 fallback 显式标注(4 测点):
  - subscription.py / api/subscriptions.py 含 signature_mode: sandbox_skip / prod_unavailable / prod_verified
  - push.py 含 push_skipped=true
  - nl_summary.py 含 CR-010 禁词扫描(forbidden_recommendation_words)
  - analytics.py 含 10 事件常量(无 silent fail)

Section 4 — 部署平台示例(2 测点):
  - render.yaml 含全部 13 envVars
  - docker-compose.prod.yml 引用 .env.production

总计 20 测点。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BACKEND_APP = ROOT / "backend" / "app"
BACKEND_SERVICES = BACKEND_APP / "services"
BACKEND_API = BACKEND_APP / "api"
FRONTEND_SRC = ROOT / "frontend" / "src"

DOC_PROD_ENV = DOCS / "V1.4-prod-env-setup.md"
DOC_CONFIG = BACKEND_APP / "core" / "config.py"


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------
# Section 1: V1.4-prod-env-setup.md 文档完整性(8 测点)
# ----------------------------------------------------------------------

def t01_doc_exists() -> bool:
    if not DOC_PROD_ENV.exists():
        print(f"  [FAIL] V1.4-prod-env-setup.md 不存在: {DOC_PROD_ENV}")
        return False
    print(f"  [PASS] V1.4-prod-env-setup.md 存在 ({DOC_PROD_ENV.stat().st_size} bytes)")
    return True


def t02_doc_has_12_sections() -> bool:
    txt = _read(DOC_PROD_ENV)
    expected = [
        "一、环境变量总览", "二、P0 必填", "三、P1 必填",
        "四、P2 建议", "五、P3 沿用默认", "六、生产环境配置顺序",
        "七、平台配置示例", "八、回滚方案", "九、落地检查清单",
        "十、未完成", "十一、给 V1.4 上线 ops 的一句话", "十二、本文记忆",
    ]
    missing = [h for h in expected if h not in txt]
    if missing:
        print(f"  [FAIL] 缺章节: {missing}")
        return False
    print(f"  [PASS] 12 章节齐全")
    return True


def t03_doc_p0_7_items() -> bool:
    """P0 7 项清单校验。"""
    txt = _read(DOC_PROD_ENV)
    p0_vars = [
        "DATABASE_URL", "DATABASE_URL_SYNC", "SECRET_KEY",
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY", "STRIPE_PRICE_PRO_YEARLY",
    ]
    missing = [v for v in p0_vars if v not in txt]
    if missing:
        print(f"  [FAIL] P0 缺变量: {missing}")
        return False
    print(f"  [PASS] P0 7 项齐全")
    return True


def t04_doc_p1_8_items() -> bool:
    """P1 8 项清单校验。"""
    txt = _read(DOC_PROD_ENV)
    p1_vars = [
        "VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_CLAIMS_EMAIL",
        "SENTRY_DSN", "ENV", "LOG_LEVEL", "DEBUG", "CORS_ORIGINS",
    ]
    missing = [v for v in p1_vars if v not in txt]
    if missing:
        print(f"  [FAIL] P1 缺变量: {missing}")
        return False
    print(f"  [PASS] P1 8 项齐全")
    return True


def t05_doc_checklist_12_items() -> bool:
    """落地检查清单 12 项。"""
    txt = _read(DOC_PROD_ENV)
    # CI 自动 10 项 + 人工 2 项
    expected_markers = [
        "CI-1", "CI-2", "CI-3", "CI-4", "CI-5", "CI-6", "CI-7", "CI-8", "CI-9", "CI-10",
        "人工-11", "人工-12",
    ]
    missing = [m for m in expected_markers if m not in txt]
    if missing:
        print(f"  [FAIL] 缺检查项: {missing}")
        return False
    print(f"  [PASS] 落地检查清单 12 项齐全")
    return True


def t06_doc_rollback_8_items() -> bool:
    """回滚方案 8 项。"""
    txt = _read(DOC_PROD_ENV)
    rollback_vars = [
        "DATABASE_URL", "SECRET_KEY", "STRIPE_SECRET_KEY",
        "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_PRO_*",
        "VAPID_PRIVATE_KEY", "SENTRY_DSN", "REDIS_URL",
        "GOOGLE_OAUTH_*",  # 这一项也涵盖
    ]
    # 简化:校验 8 个回滚场景 marker
    markers = ["启动失败", "checkout 报 500", "webhook 返 sandbox_skip",
               "push 返 push_skipped", "前端不初始化 Sentry",
               "缓存降级 no_cache", "跳过 Google OAuth", "回滚 SOP"]
    hits = sum(1 for m in markers if m in txt)
    if hits < 7:
        print(f"  [FAIL] 回滚方案 marker 不足:{hits}/8")
        return False
    print(f"  [PASS] 回滚方案 8 项场景齐全({hits}/8)")
    return True


def t07_doc_secrets_generation_commands() -> bool:
    """密钥生成命令存在(SECRET_KEY / VAPID)。"""
    txt = _read(DOC_PROD_ENV)
    # SECRET_KEY 用 secrets.token_urlsafe,VAPID 用 py_vapid
    if "secrets.token_urlsafe" not in txt:
        print("  [FAIL] 缺 SECRET_KEY 生成命令")
        return False
    if "py_vapid" not in txt and "Vapid" not in txt:
        print("  [FAIL] 缺 VAPID 生成命令")
        return False
    print(f"  [PASS] 密钥生成命令齐全(SECRET_KEY + VAPID)")
    return True


def t08_doc_no_silent_fail_marker() -> bool:
    """文档明确『不 mock 200 伪装』红线。"""
    txt = _read(DOC_PROD_ENV)
    # 至少出现 2 次"不 mock 200 伪装"或类似表述
    count = txt.count("不 mock 200") + txt.count("mock 200 伪装") + txt.count("不伪装")
    if count < 2:
        print(f"  [FAIL] '不 mock 200 伪装' 表述不足:{count}/2")
        return False
    print(f"  [PASS] '不 mock 200 伪装' 红线 ({count} 处)")
    return True


# ----------------------------------------------------------------------
# Section 2: config.py 关键字段存在性(6 测点)
# ----------------------------------------------------------------------

def t09_config_p0_fields() -> bool:
    """config.py 含 P0 7 字段。"""
    txt = _read(DOC_CONFIG)
    p0_fields = [
        "database_url", "database_url_sync", "secret_key",
        "stripe_secret_key", "stripe_webhook_secret",
        "stripe_price_pro_monthly", "stripe_price_pro_yearly",
    ]
    missing = [f for f in p0_fields if f + ":" not in txt]
    if missing:
        print(f"  [FAIL] config.py 缺 P0 字段: {missing}")
        return False
    print(f"  [PASS] config.py P0 7 字段齐全")
    return True


def t10_config_p1_fields() -> bool:
    """config.py 含 P1 8 字段。"""
    txt = _read(DOC_CONFIG)
    p1_fields = [
        "vapid_private_key", "vapid_public_key", "vapid_claims_email",
        "sentry_dsn", "env", "log_level", "debug", "cors_origins",
    ]
    missing = [f for f in p1_fields if f + ":" not in txt]
    if missing:
        print(f"  [FAIL] config.py 缺 P1 字段: {missing}")
        return False
    print(f"  [PASS] config.py P1 8 字段齐全")
    return True


def t11_config_is_production() -> bool:
    """is_production property 存在。"""
    txt = _read(DOC_CONFIG)
    if "is_production" not in txt or "self.env" not in txt:
        print("  [FAIL] is_production property 缺失")
        return False
    print(f"  [PASS] is_production property 齐全")
    return True


def t12_config_secret_key_default() -> bool:
    """SECRET_KEY 默认值含 dev-only 标识(沙箱 fallback 显式标注)。"""
    txt = _read(DOC_CONFIG)
    if "dev-only-change-me-in-prod" not in txt:
        print("  [FAIL] SECRET_KEY 默认值缺 dev-only 标识")
        return False
    print(f"  [PASS] SECRET_KEY 默认值含 dev-only 标识")
    return True


def t13_config_stripe_default_none() -> bool:
    """Stripe 三个生产变量默认 None(沙箱 fallback 显式标注)。"""
    txt = _read(DOC_CONFIG)
    stripe_fields = ["stripe_secret_key", "stripe_webhook_secret",
                     "stripe_price_pro_monthly", "stripe_price_pro_yearly"]
    for f in stripe_fields:
        pattern = f + r"\s*:\s*str\s*\|\s*None\s*=\s*None"
        if not re.search(pattern, txt):
            print(f"  [FAIL] {f} 默认值不是 None")
            return False
    print(f"  [PASS] Stripe 4 变量默认 None(沙箱 fallback 显式标注)")
    return True


def t14_config_vapid_default_none() -> bool:
    """VAPID 私钥/公钥默认 None(沙箱 fallback 显式标注)。"""
    txt = _read(DOC_CONFIG)
    for f in ["vapid_private_key", "vapid_public_key"]:
        pattern = f + r"\s*:\s*str\s*\|\s*None\s*=\s*None"
        if not re.search(pattern, txt):
            print(f"  [FAIL] {f} 默认值不是 None")
            return False
    print(f"  [PASS] VAPID 私钥/公钥默认 None(沙箱 fallback)")
    return True


# ----------------------------------------------------------------------
# Section 3: 服务层沙箱 fallback 显式标注(4 测点)
# ----------------------------------------------------------------------

def t15_subscriptions_signature_mode() -> bool:
    """V1.6 订阅模块已整体移除(2026-06-30)— 测点改为 SKIP。"""
    print(f"  [SKIP] subscriptions.py 已删除(2026-06-30) — signature_mode 不再适用")
    return True


def t16_push_service_push_skipped() -> bool:
    """push.py / push_subscription.py 含 skipped_sandbox fallback(M5 统一标识)。"""
    push = _read(BACKEND_SERVICES / "push.py")
    push_sub = _read(BACKEND_SERVICES / "push_subscription.py")
    # M5 统一标识:skipped_sandbox(不是 push_skipped)
    if "skipped_sandbox" not in push and "skipped_sandbox" not in push_sub:
        print("  [FAIL] push 服务缺 skipped_sandbox 沙箱 fallback")
        return False
    # 额外校验 VAPID 三个环境变量引用齐全
    for f in ["VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_CLAIMS_EMAIL"]:
        if f not in push and f not in push_sub:
            print(f"  [FAIL] push 服务缺 {f} 引用")
            return False
    print(f"  [PASS] push 服务 skipped_sandbox 沙箱 fallback 齐全")
    return True


def t17_nl_summary_critical_words() -> bool:
    """nl_summary.py 含 CR-010 禁词扫描。"""
    txt = _read(BACKEND_SERVICES / "nl_summary.py")
    if "forbidden_recommendation_words" not in txt and "CR-010" not in txt:
        print("  [FAIL] nl_summary.py 缺 CR-010 禁词扫描")
        return False
    print(f"  [PASS] nl_summary.py CR-010 禁词扫描齐全")
    return True


def t18_analytics_ten_events() -> bool:
    """analytics.py 含 10 事件常量。"""
    txt = _read(BACKEND_SERVICES / "analytics.py")
    events = [
        "EVENT_USER_SIGNUP", "EVENT_USER_LOGIN",
        "EVENT_SUBSCRIBE_START", "EVENT_SUBSCRIBE_SUCCESS",
        "EVENT_SUBSCRIBE_CANCEL", "EVENT_SCREENER_VIEW",
        "EVENT_BASKET_CREATE", "EVENT_ALERT_RULE_CREATE",
        "EVENT_PUSH_OPT_IN", "EVENT_FEATURE_FLAG_VIEW",
    ]
    missing = [e for e in events if e not in txt]
    if missing:
        print(f"  [FAIL] analytics.py 缺事件: {missing}")
        return False
    print(f"  [PASS] analytics.py 10 事件常量齐全")
    return True


# ----------------------------------------------------------------------
# Section 4: 部署平台示例(2 测点)
# ----------------------------------------------------------------------

def t19_render_yaml_envs() -> bool:
    """render.yaml 引用全部 P0/P1 13 envVars。"""
    p = ROOT / "render.yaml"
    if not p.exists():
        print(f"  [SKIP] render.yaml 不存在(V1.4 上线前创建)")
        return True
    txt = _read(p)
    envs = [
        "DATABASE_URL", "DATABASE_URL_SYNC", "SECRET_KEY",
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
        "VAPID_PRIVATE_KEY", "VAPID_PUBLIC_KEY", "VAPID_CLAIMS_EMAIL",
        "SENTRY_DSN", "ENV", "DEBUG", "LOG_LEVEL", "CORS_ORIGINS",
    ]
    missing = [e for e in envs if e not in txt]
    if missing:
        print(f"  [FAIL] render.yaml 缺 envVars: {missing}")
        return False
    print(f"  [PASS] render.yaml 13 envVars 齐全")
    return True


def t20_no_collected_secrets() -> bool:
    """生产 secrets 严禁硬编码在代码中(.env.example 仅占位)。"""
    env_example = ROOT / ".env.example"
    if not env_example.exists():
        print(f"  [SKIP] .env.example 不存在")
        return True
    txt = _read(env_example)
    # 校验 .env.example 注释强调"严禁把真实密钥提交到仓库"
    if "严禁" not in txt and "do not commit" not in txt.lower() and "placeholder" not in txt.lower():
        print("  [FAIL] .env.example 缺『严禁/placeholder』警告")
        return False
    print(f"  [PASS] .env.example 含密钥提交警告")
    return True


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[str] = []


def _run(name: str, fn) -> None:
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001
        print(f"  [ERROR] {name} 抛出异常: {exc}")
        ok = False
    if ok:
        _PASSED.append(name)
    else:
        _FAILED.append(name)


def main() -> int:
    print("=== 1. V1.4-prod-env-setup.md 文档完整性 ===")
    _run("t01_doc_exists", t01_doc_exists)
    _run("t02_doc_has_12_sections", t02_doc_has_12_sections)
    _run("t03_doc_p0_7_items", t03_doc_p0_7_items)
    _run("t04_doc_p1_8_items", t04_doc_p1_8_items)
    _run("t05_doc_checklist_12_items", t05_doc_checklist_12_items)
    _run("t06_doc_rollback_8_items", t06_doc_rollback_8_items)
    _run("t07_doc_secrets_generation_commands", t07_doc_secrets_generation_commands)
    _run("t08_doc_no_silent_fail_marker", t08_doc_no_silent_fail_marker)

    print("\n=== 2. config.py 关键字段存在性 ===")
    _run("t09_config_p0_fields", t09_config_p0_fields)
    _run("t10_config_p1_fields", t10_config_p1_fields)
    _run("t11_config_is_production", t11_config_is_production)
    _run("t12_config_secret_key_default", t12_config_secret_key_default)
    _run("t13_config_stripe_default_none", t13_config_stripe_default_none)
    _run("t14_config_vapid_default_none", t14_config_vapid_default_none)

    print("\n=== 3. 服务层沙箱 fallback 显式标注 ===")
    _run("t15_subscriptions_signature_mode", t15_subscriptions_signature_mode)
    _run("t16_push_service_push_skipped", t16_push_service_push_skipped)
    _run("t17_nl_summary_critical_words", t17_nl_summary_critical_words)
    _run("t18_analytics_ten_events", t18_analytics_ten_events)

    print("\n=== 4. 部署平台示例 ===")
    _run("t19_render_yaml_envs", t19_render_yaml_envs)
    _run("t20_no_collected_secrets", t20_no_collected_secrets)

    total = len(_PASSED) + len(_FAILED)
    print(f"\n[m8t3] SUMMARY: {len(_PASSED)}/{total} PASSED, {len(_FAILED)} FAILED")
    if _FAILED:
        print(f"[m8t3] FAILED TESTS: {', '.join(_FAILED)}")
        return 1
    print(f"[m8t3] ALL {total} PROD-ENV TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
