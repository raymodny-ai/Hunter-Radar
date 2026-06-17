"""M7-t7 admin 端点(M7 接力期):V1.5 OpenAPI freeze 新增 4 端点。

端点:
- POST /api/v1/admin/etl/run            触发 BD-085 真实数据集 ETL(沙箱 stub) — require_admin_role
- POST /api/v1/admin/backtest/run       触发 v3.0-final backtest(沙箱 stub) — require_admin_role
- GET  /api/v1/admin/backtest/result    读最近 backtest 结果 — require_admin_role
- POST /api/v1/admin/webhook/replay     重放 sandbox webhook(测试用,super_admin) — require_super_admin_role

安全(V1.5 接力期 m9t1 补全 + V1.5.4 接力期 m12t1 super_admin 拆分):
- 普通 admin 端点(require_admin_role):JWT role=admin / X-Admin-API-Key / 沙箱 fallback
- 高危 admin 端点(require_super_admin_role):webhook 重放仅 super_admin 可触发
- 三态显式标注: prod_admin_jwt / prod_admin_apikey / sandbox_skip_admin
- super admin 三态标注: prod_super_admin_jwt / prod_super_admin_apikey / sandbox_skip_super_admin
- IP 白名单(可选, settings.admin_ip_whitelist)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import TUser, require_admin_role, require_super_admin_role

router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
BACKEND_SCRIPTS = ROOT / "backend" / "scripts"
DOCS = ROOT / "docs"
BACKTEST_RESULT_JSON = DOCS / "BD-087-calibration-run-m7t4.json"


def _resolve_auth_mode(
    request: Request,
    user: TUser,
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> str:
    """返当前 admin 鉴权模式(V1.5.3 接力期 m11t2 简化版)。

    V1.5.3 变更(m11t2):
    - IP 白名单校验已合并到 `require_admin_role` 内部(Request 注入)
    - 本函数仅判断 auth_mode 标签,不重复校验 IP
    - 调用顺序:require_admin_role 先过 IP 白名单,过了才进本函数
    - 故不会出现 IP 限定却走到的路径

    优先级:
    1. 走 API key 头 → "prod_admin_apikey"
    2. JWT role=admin + 真实用户(非沙箱占位) → "prod_admin_jwt"
    3. 其他 → "sandbox_skip_admin"
    """
    from app.core.auth import SANDBOX_PLACEHOLDER_USER_ID, _check_api_key

    # 1) API key
    if _check_api_key(x_admin_api_key):
        return "prod_admin_apikey"
    # 2) JWT role=admin
    from uuid import UUID
    try:
        is_real_user = UUID(str(user.user_id)) != SANDBOX_PLACEHOLDER_USER_ID
    except Exception:  # noqa: BLE001
        is_real_user = False
    if user.is_admin and is_real_user:
        return "prod_admin_jwt"
    return "sandbox_skip_admin"


@router.post("/admin/etl/run", summary="触发 BD-085 真实数据集 ETL(沙箱 stub)")
async def post_etl_run(
    request: Request,
    user: TUser = Depends(require_admin_role),
) -> dict:
    """触发 BD-085 真实数据集 ETL。

    沙箱 stub:调 `etl/backtest_dataset_real.py` 合成 deterministic OHLCV 数据。
    生产环境:替换为 PG 真实 ETL + FINRA RegSHO + Yahoo Finance EOD + SEC Form 4。

    鉴权(V1.5 接力期 m9t1):
    - require_admin_role(JWT role=admin / X-Admin-API-Key / 沙箱 fallback)
    - 返 auth_mode 标注

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v153
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: true (m11t2 IP 校验合并)
    m12t1_super_admin: false
    """
    auth_mode = _resolve_auth_mode(request, user)
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'D:/Financial Project/Hunter Radar/hunter-radar/backend');"
             "from etl import backtest_dataset_real;"
             "r, pl = backtest_dataset_real.build_real_dataset_sandbox("
             "r'D:/Financial Project/Hunter Radar/hunter-radar/data/backtest_event_goldset.sample.jsonl',"
             "window_days=90);"
             "print(r.to_dict().__str__() if hasattr(r, 'to_dict') else str(r))"],
            capture_output=True, text=True, timeout=60
        )
        ok = result.returncode == 0
        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "sandbox": True,
            "auth_mode": auth_mode,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        }
    except Exception as e:
        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "sandbox": True,
            "auth_mode": auth_mode,
            "error": f"{type(e).__name__}: {e}",
        }


@router.post("/admin/backtest/run", summary="触发 v3.0-final backtest(沙箱 stub)")
async def post_backtest_run(
    request: Request,
    user: TUser = Depends(require_admin_role),
) -> dict:
    """触发 v3.0-final backtest(Mann-Whitney U 检验)。

    沙箱 stub:调 `m7t4_run_backtest_v30_final.py compare`,输出 JSON 到 docs/。
    生产环境:替换为真实 PG 数据 + scipy.stats.mannwhitneyu。

    鉴权(V1.5 接力期 m9t1):require_admin_role + auth_mode 标注。

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v153
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: true (m11t2 IP 校验合并)
    m12t1_super_admin: false
    """
    auth_mode = _resolve_auth_mode(request, user)
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(
            [sys.executable, "-u",
             str(BACKEND_SCRIPTS / "m7t4_run_backtest_v30_final.py"), "compare"],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT)
        )
        ok = result.returncode == 0
        # 读落地的 JSON
        summary: dict = {}
        if BACKTEST_RESULT_JSON.exists():
            try:
                summary = json.loads(BACKTEST_RESULT_JSON.read_text(encoding="utf-8"))
                summary = {
                    "weights_a": summary.get("weights_a", {}).get("name"),
                    "weights_b": summary.get("weights_b", {}).get("name"),
                    "delta_hit_rate": summary.get("delta_hit_rate"),
                    "delta_f1": summary.get("delta_f1"),
                    "mann_whitney_p_value": summary.get("mann_whitney_u", {}).get("p_value"),
                    "significant_at_005": summary.get("mann_whitney_u", {}).get("significant_at_005"),
                }
            except Exception:
                summary = {}
        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "sandbox": True,
            "auth_mode": auth_mode,
            "summary": summary,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        }
    except Exception as e:
        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "ok": False,
            "sandbox": True,
            "auth_mode": auth_mode,
            "error": f"{type(e).__name__}: {e}",
        }


@router.get("/admin/backtest/result", summary="读最近 backtest 结果")
async def get_backtest_result(
    request: Request,
    user: TUser = Depends(require_admin_role),
) -> dict:
    """读最近一次 backtest 结果(`docs/BD-087-calibration-run-m7t4.json`)。

    鉴权(V1.5 接力期 m9t1):require_admin_role + auth_mode 标注。

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v153
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: true (m11t2 IP 校验合并)
    m12t1_super_admin: false
    """
    auth_mode = _resolve_auth_mode(request, user)
    if not BACKTEST_RESULT_JSON.exists():
        return {
            "available": False,
            "path": str(BACKTEST_RESULT_JSON.relative_to(ROOT)),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "auth_mode": auth_mode,
        }
    try:
        data = json.loads(BACKTEST_RESULT_JSON.read_text(encoding="utf-8"))
        return {
            "available": True,
            "path": str(BACKTEST_RESULT_JSON.relative_to(ROOT)),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "auth_mode": auth_mode,
            "summary": {
                "weights_a": data.get("weights_a", {}).get("name"),
                "weights_b": data.get("weights_b", {}).get("name"),
                "delta_hit_rate": data.get("delta_hit_rate"),
                "delta_f1": data.get("delta_f1"),
                "mann_whitney_p_value": data.get("mann_whitney_u", {}).get("p_value"),
                "significant_at_005": data.get("mann_whitney_u", {}).get("significant_at_005"),
                "sandbox": data.get("sandbox"),
            },
        }
    except Exception as e:
        return {
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "path": str(BACKTEST_RESULT_JSON.relative_to(ROOT)),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "auth_mode": auth_mode,
        }


@router.post("/admin/webhook/replay", summary="重放 sandbox webhook(测试用,super_admin)")
async def post_webhook_replay(
    request: Request,
    payload: dict,
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
    user: TUser = Depends(require_super_admin_role),
) -> dict:
    """重放 sandbox Stripe webhook(测试用)。

    V1.5.4 接力期 m12t1:webhook 重放属于高危操作(可重放用户订阅事件,影响计费),
    从 require_admin_role 升级为 require_super_admin_role,普通 admin 不可触发。

    沙箱 stub:直接 dispatch 到 `subscription.handle_webhook_event`。
    生产环境:super_admin role + 限流 + audit log。

    ### REVIEW META (V1.5.4 m12t3)
    review_status: passes_v154
    owner: platform-team
    last_reviewed: 2026-06-15
    touched_in_v153: false
    m12t1_super_admin: true (require_super_admin_role)
    m12t3_high_risk: true (webhook 重放 = 计费事件)
    """
    from app.core.auth import _check_api_key
    # V1.5.4 接力期 m12t1:webhook/replay 是 super_admin 端点,auth_mode 标签用 super_admin 三态
    if _check_api_key(x_admin_api_key):
        auth_mode = "prod_super_admin_apikey"
    elif user.is_super_admin and user.is_authenticated:
        auth_mode = "prod_super_admin_jwt"
    else:
        auth_mode = "sandbox_skip_super_admin"
    received_at = datetime.now(timezone.utc).isoformat()
    result = handle_webhook_event(payload)
    return {
        "received_at": received_at,
        "replayed": True,
        "signature_mode": "sandbox_skip",
        "auth_mode": auth_mode,
        "result": result,
    }