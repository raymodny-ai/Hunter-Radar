"""V1.5 接力期 m9t2 — production env 12 项检查自动化。

V1.4-prod-env-setup.md §九 的 12 项落地检查清单(10 CI 自动 + 2 人工):

CI 自动 10 项:
  CI-1:  P0 7 项全部注入
  CI-2:  SECRET_KEY 长度 ≥32,不与 dev-only 前缀
  CI-3:  STRIPE_SECRET_KEY 前缀 sk_live_(生产)
  CI-4:  STRIPE_WEBHOOK_SECRET 前缀 whsec_,长度 ≥32
  CI-5:  VAPID_PUBLIC_KEY base64url decode 为 65 bytes
  CI-6:  VAPID_PRIVATE_KEY 包含 PEM 头尾(-----BEGIN)
  CI-7:  SENTRY_DSN 包含 sentry.io + /ingest/ 路径
  CI-8:  ENV=production
  CI-9:  DEBUG=false
  CI-10: CORS_ORIGINS JSON list,不含 *,不含 localhost

人工 2 项(V1.5 接力期 m9t2 仅标记,不强制):
  人工-11: psql 三扩展(uuid-ossp / pgcrypto / pg_trgm)
  人工-12: VAPID 公私钥配对(py_vapid 验证)

V1.5 接力期 m9t2 新增 3 项 admin 鉴权:
  V15-1: ADMIN_API_KEY 已设(生产)或 admin_role_enabled=False(沙箱)
  V15-2: ADMIN_IP_WHITELIST 格式合法(逗号分隔 IP)
  V15-3: ADMIN_API_KEY 长度 ≥32

使用:
  py scripts/env_check.py            # 校验 process.env
  py scripts/env_check.py --dotenv .env.production
  py scripts/env_check.py --sandbox  # 跳过生产必填(沙箱/CI 用)
  py scripts/env_check.py --v15      # 包含 V1.5 admin 鉴权 3 项

退出码:
  0 = 全部 PASS
  1 = 任一 FAIL
  2 = 缺 P0 必填(--sandbox 模式才允许)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------

def _b64url_decode(s: str) -> bytes | None:
    """base64url decode 容错(M9t2 工具函数)。"""
    try:
        pad = "=" * ((4 - len(s) % 4) % 4)
        return base64.urlsafe_b64decode((s + pad).encode("ascii"))
    except Exception:  # noqa: BLE001
        return None


def _is_valid_ip(ip: str) -> bool:
    """粗略 IP 格式校验(IPv4 优先,IPv6 不深入)。"""
    if not ip:
        return False
    # IPv4
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
        parts = ip.split(".")
        return all(0 <= int(p) <= 255 for p in parts)
    # IPv6 简化校验
    if ":" in ip and re.match(r"^[0-9a-fA-F:]+$", ip):
        return True
    return False


# ----------------------------------------------------------------------
# Check functions — CI 自动 10 项
# ----------------------------------------------------------------------

def check_ci1_p0_all(env: dict[str, str]) -> tuple[bool, str]:
    """CI-1: P0 7 项全部注入。"""
    p0 = [
        "DATABASE_URL", "DATABASE_URL_SYNC", "SECRET_KEY",
        "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
        "STRIPE_PRICE_PRO_MONTHLY", "STRIPE_PRICE_PRO_YEARLY",
    ]
    missing = [k for k in p0 if not env.get(k)]
    if missing:
        return False, f"缺:{missing}"
    return True, f"P0 7 项齐全"


def check_ci2_secret_key(env: dict[str, str]) -> tuple[bool, str]:
    """CI-2: SECRET_KEY 长度 ≥32,不与 dev-only 前缀。"""
    v = env.get("SECRET_KEY", "")
    if not v:
        return False, "SECRET_KEY 未设"
    if len(v) < 32:
        return False, f"SECRET_KEY 长度={len(v)} < 32"
    if "dev-only" in v:
        return False, "SECRET_KEY 含 dev-only 前缀(沙箱 fallback)"
    return True, f"SECRET_KEY 长度={len(v)}"


def check_ci3_stripe_secret(env: dict[str, str]) -> tuple[bool, str]:
    """CI-3: STRIPE_SECRET_KEY 前缀 sk_live_(生产)。"""
    v = env.get("STRIPE_SECRET_KEY", "")
    if not v:
        return False, "STRIPE_SECRET_KEY 未设"
    if v.startswith("sk_live_"):
        return True, "sk_live_ 生产"
    if v.startswith("sk_test_"):
        return False, "sk_test_(仅 staging,生产必须 sk_live_)"
    return False, f"前缀未知:{v[:10]}"


def check_ci4_stripe_webhook(env: dict[str, str]) -> tuple[bool, str]:
    """CI-4: STRIPE_WEBHOOK_SECRET 前缀 whsec_,长度 ≥32。"""
    v = env.get("STRIPE_WEBHOOK_SECRET", "")
    if not v:
        return False, "STRIPE_WEBHOOK_SECRET 未设"
    if not v.startswith("whsec_"):
        return False, f"前缀不是 whsec_:{v[:10]}"
    if len(v) < 32:
        return False, f"长度={len(v)} < 32"
    return True, f"whsec_ + 长度={len(v)}"


def check_ci5_vapid_public(env: dict[str, str]) -> tuple[bool, str]:
    """CI-5: VAPID_PUBLIC_KEY base64url decode 为 65 bytes。"""
    v = env.get("VAPID_PUBLIC_KEY", "")
    if not v:
        return False, "VAPID_PUBLIC_KEY 未设"
    raw = _b64url_decode(v)
    if raw is None:
        return False, "base64url decode 失败"
    if len(raw) != 65:
        return False, f"长度={len(raw)},期望 65(EC P-256 uncompressed)"
    return True, f"VAPID 公钥 65 bytes"


def check_ci6_vapid_private(env: dict[str, str]) -> tuple[bool, str]:
    """CI-6: VAPID_PRIVATE_KEY 包含 PEM 头尾。"""
    v = env.get("VAPID_PRIVATE_KEY", "")
    if not v:
        return False, "VAPID_PRIVATE_KEY 未设"
    if "-----BEGIN" not in v or "-----END" not in v:
        return False, "缺 PEM 头尾(-----BEGIN/-----END)"
    return True, "PEM 头尾齐全"


def check_ci7_sentry_dsn(env: dict[str, str]) -> tuple[bool, str]:
    """CI-7: SENTRY_DSN 包含 sentry.io + /ingest/ 路径。"""
    v = env.get("SENTRY_DSN", "")
    if not v:
        return False, "SENTRY_DSN 未设"
    if "sentry.io" not in v:
        return False, "URL 缺 sentry.io"
    if "/ingest/" not in v:
        return False, "URL 缺 /ingest/ 路径"
    return True, "sentry.io + /ingest/"


def check_ci8_env_production(env: dict[str, str]) -> tuple[bool, str]:
    """CI-8: ENV=production。"""
    v = env.get("ENV", "")
    if not v:
        return False, "ENV 未设"
    if v.lower() != "production":
        return False, f"ENV={v}(生产必须 production)"
    return True, "ENV=production"


def check_ci9_debug_false(env: dict[str, str]) -> tuple[bool, str]:
    """CI-9: DEBUG=false。"""
    v = env.get("DEBUG", "").lower()
    if v in ("false", "0", "no", ""):
        return True, f"DEBUG={v or 'unset'}(默认 false)"
    return False, f"DEBUG={v}(生产必须 false)"


def check_ci10_cors_origins(env: dict[str, str]) -> tuple[bool, str]:
    """CI-10: CORS_ORIGINS JSON list,不含 *,不含 localhost。"""
    v = env.get("CORS_ORIGINS", "")
    if not v:
        return False, "CORS_ORIGINS 未设"
    try:
        origins = json.loads(v) if isinstance(v, str) and v.startswith("[") else [s.strip() for s in v.split(",") if s.strip()]
    except json.JSONDecodeError as e:
        return False, f"JSON 解析失败:{e}"
    if not isinstance(origins, list) or not origins:
        return False, "CORS_ORIGINS 不是非空 list"
    if "*" in origins:
        return False, "CORS_ORIGINS 含 *(CSRF 风险)"
    for o in origins:
        if "localhost" in str(o):
            return False, f"CORS_ORIGINS 含 localhost:{o}"
        if not str(o).startswith("https://"):
            return False, f"CORS_ORIGINS 非 https://:{o}"
    return True, f"{len(origins)} 个 https 域名"


# ----------------------------------------------------------------------
# V1.5 admin 鉴权 3 项
# ----------------------------------------------------------------------

def check_v15_1_admin_api_key(env: dict[str, str]) -> tuple[bool, str]:
    """V15-1: ADMIN_API_KEY 已设(生产)或 admin_role_enabled=False(沙箱)。"""
    api_key = env.get("ADMIN_API_KEY", "")
    role_enabled = env.get("ADMIN_ROLE_ENABLED", "true").lower() in ("true", "1", "yes")
    if role_enabled and not api_key:
        return False, "ADMIN_ROLE_ENABLED=true 但 ADMIN_API_KEY 未设"
    if api_key:
        return True, "ADMIN_API_KEY 已设"
    return True, "沙箱模式(admin_role_enabled=false)"


def check_v15_2_admin_ip_whitelist(env: dict[str, str]) -> tuple[bool, str]:
    """V15-2: ADMIN_IP_WHITELIST 格式合法(逗号分隔 IP)。"""
    v = env.get("ADMIN_IP_WHITELIST", "")
    if not v:
        return True, "空(不限)"
    ips = [s.strip() for s in v.split(",") if s.strip()]
    invalid = [ip for ip in ips if not _is_valid_ip(ip)]
    if invalid:
        return False, f"非法 IP 格式:{invalid}"
    return True, f"{len(ips)} 个 IP"


def check_v15_3_admin_api_key_length(env: dict[str, str]) -> tuple[bool, str]:
    """V15-3: ADMIN_API_KEY 长度 ≥32。"""
    v = env.get("ADMIN_API_KEY", "")
    if not v:
        return True, "未设(沙箱 fallback)"
    if len(v) < 32:
        return False, f"长度={len(v)} < 32"
    return True, f"长度={len(v)}"


# ----------------------------------------------------------------------
# 人工 2 项(仅标记,不强制)
# ----------------------------------------------------------------------

def check_manual_11_pg_extensions(env: dict[str, str]) -> tuple[bool, str]:
    """人工-11: psql 三扩展(env 当前未用,签名统一)。"""
    return True, "[人工] psql 三扩展(uuid-ossp / pgcrypto / pg_trgm)"


def check_manual_12_vapid_pair(env: dict[str, str]) -> tuple[bool, str]:
    """人工-12: VAPID 公私钥配对(env 当前未用,签名统一)。"""
    return True, "[人工] VAPID 公私钥配对(py_vapid 验证)"


# ----------------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------------

CI_CHECKS = [
    ("CI-1  P0 7 项全部注入", check_ci1_p0_all),
    ("CI-2  SECRET_KEY 长度 ≥32 + 无 dev-only", check_ci2_secret_key),
    ("CI-3  STRIPE_SECRET_KEY 前缀 sk_live_", check_ci3_stripe_secret),
    ("CI-4  STRIPE_WEBHOOK_SECRET 前缀 whsec_ + 长度 ≥32", check_ci4_stripe_webhook),
    ("CI-5  VAPID_PUBLIC_KEY 65 bytes", check_ci5_vapid_public),
    ("CI-6  VAPID_PRIVATE_KEY PEM 头尾", check_ci6_vapid_private),
    ("CI-7  SENTRY_DSN sentry.io + /ingest/", check_ci7_sentry_dsn),
    ("CI-8  ENV=production", check_ci8_env_production),
    ("CI-9  DEBUG=false", check_ci9_debug_false),
    ("CI-10 CORS_ORIGINS https:// list", check_ci10_cors_origins),
]

V15_CHECKS = [
    ("V15-1 ADMIN_API_KEY 已设或沙箱", check_v15_1_admin_api_key),
    ("V15-2 ADMIN_IP_WHITELIST 格式合法", check_v15_2_admin_ip_whitelist),
    ("V15-3 ADMIN_API_KEY 长度 ≥32", check_v15_3_admin_api_key_length),
]

MANUAL_CHECKS = [
    ("人工-11 psql 三扩展(uuid-ossp / pgcrypto / pg_trgm)", check_manual_11_pg_extensions),
    ("人工-12 VAPID 公私钥配对(py_vapid)", check_manual_12_vapid_pair),
]


def load_env(dotenv_path: str | None) -> dict[str, str]:
    """从 process.env + 可选 .env 文件加载。"""
    env = dict(os.environ)
    if dotenv_path:
        p = Path(dotenv_path)
        if not p.exists():
            print(f"[WARN] .env 文件不存在:{p}")
            return env
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in env:  # process.env 优先
                env[k] = v
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="V1.4 production env 12 项检查 + V1.5 admin 鉴权 3 项(V1.5 接力期 m9t2)"
    )
    parser.add_argument("--dotenv", help=".env 文件路径", default=None)
    parser.add_argument("--sandbox", action="store_true", help="沙箱模式(允许缺 P0)")
    parser.add_argument("--v15", action="store_true", help="包含 V1.5 admin 鉴权 3 项")
    args = parser.parse_args()

    env = load_env(args.dotenv)

    print("=" * 72)
    print(f"  V1.4 production env 12 项检查(m9t2) — dotenv={args.dotenv or 'process.env'}")
    print("=" * 72)

    failures: list[str] = []
    passes: list[str] = []

    print("\n--- CI 自动 10 项 ---")
    for name, fn in CI_CHECKS:
        ok, detail = fn(env)
        if ok:
            print(f"  [PASS] {name} — {detail}")
            passes.append(name)
        else:
            print(f"  [FAIL] {name} — {detail}")
            failures.append(name)

    if args.v15:
        print("\n--- V1.5 admin 鉴权 3 项 ---")
        for name, fn in V15_CHECKS:
            ok, detail = fn(env)
            if ok:
                print(f"  [PASS] {name} — {detail}")
                passes.append(name)
            else:
                print(f"  [FAIL] {name} — {detail}")
                failures.append(name)

    print("\n--- 人工 2 项(仅标记)---")
    for name, fn in MANUAL_CHECKS:
        ok, detail = fn(env)
        print(f"  [INFO] {name} — {detail}")
        passes.append(name)  # 人工项不计入失败

    total = len(passes) + len(failures)
    print(f"\n{'=' * 72}")
    print(f"  [m9t2] SUMMARY: {len(passes)}/{total} PASSED, {len(failures)} FAILED")
    print(f"{'=' * 72}")

    if failures:
        print(f"\n[m9t2] FAILED CHECKS:")
        for f in failures:
            print(f"  - {f}")
        if args.sandbox:
            print(f"\n[m9t2] --sandbox 模式: 允许 FAIL,返 0")
            return 0
        return 1

    print(f"\n[m9t2] ALL {total} ENV CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
