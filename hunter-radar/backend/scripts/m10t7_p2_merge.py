"""M10-t7 V1.5.2 P2 合并工具(候选 A 权重切换 + VAPID 沙箱生产密钥分离)。

V1.5.2 接力期 m10t7 — P2 候选 2 项合并到单一 CLI:

子命令:
  weight-switch-eval    评估候选 A 权重是否切换为默认(Mann-Whitney U p_value 阈值)
                       输入: docs/BD-087-calibration-run-m7t4.json(m7t4 compare 输出)
                       阈值: p < 0.05 → 切 candidate_a;p >= 0.05 → 保持 v1.0
                       默认: V1.5.2 沿用 v3.0-final 结论"保持 v1.0"

  vapid-separator       VAPID 沙箱(HR_ 前缀)与生产(无前缀)密钥分离校验
                       输入: os.environ[VAPID_PUBLIC_KEY / HR_VAPID_PUBLIC_KEY]
                       输出: 三态(VAPID_PROD_ONLY / VAPID_SANDBOX_ONLY / VAPID_DUAL / VAPID_NONE)
                       强制: 生产环境严禁使用 HR_ 前缀的 dev key

BD-087 v3.0-final 已知结论(沿用):
  p=0.3827, U=418.5 → 保持 v1.0
  delta_hit_rate = -0.0645(候选 A 略低)
  delta_f1 = -0.0703(候选 A 略低)

VAPID 沙箱生产分离规则:
  - HR_VAPID_PUBLIC_KEY(沙箱 dev key)与 VAPID_PUBLIC_KEY(生产)不可同时在生产环境激活
  - HR_ 前缀 dev key 仅沙箱 / CI / 单测使用
  - VAPID_PROD_ONLY:生产 key 设了,HR_ 未设 → 正常生产态
  - VAPID_SANDBOX_ONLY:HR_ 设了,VAPID 未设 → 沙箱态(生产环境禁止)
  - VAPID_DUAL:两个都设了 → 严重配置错(生产环境禁止)
  - VAPID_NONE:两个都没设 → CI 无 VAPID(必须 sandbox_skip_push)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ---- 候选 A 权重切换阈值(BD-087 v3.0-final 沿用) -----------------------

# 显著性阈值 α = 0.05(双尾)
P_VALUE_THRESHOLD_DEFAULT = 0.05

# BD-087 v3.0-final 已知结论(沿用)
BD087_V30_FINAL_P_VALUE = 0.3827
BD087_V30_FINAL_U_STAT = 418.5
BD087_V30_FINAL_DELTA_HIT_RATE = -0.0645
BD087_V30_FINAL_DELTA_F1 = -0.0703
BD087_V30_FINAL_DECISION = "keep_v1.0"

# ---- 候选 A 权重 --------------------------------------------------


CANDIDATE_A_WEIGHTS = {
    "stock": {"options": 0.25, "short": 0.40, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.30, "short": 0.50, "divergence": 0.20},
}

V10_DEFAULT_WEIGHTS = {
    "stock": {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.35, "short": 0.45, "divergence": 0.20},
}

# ---- VAPID 沙箱生产分离 --------------------------------------------

VAPID_PROD_PUBLIC = "VAPID_PUBLIC_KEY"
VAPID_PROD_PRIVATE = "VAPID_PRIVATE_KEY"
VAPID_SANDBOX_PUBLIC = "HR_VAPID_PUBLIC_KEY"
VAPID_SANDBOX_PRIVATE = "HR_VAPID_PRIVATE_KEY"

VAPID_PROD_ONLY = "VAPID_PROD_ONLY"
VAPID_SANDBOX_ONLY = "VAPID_SANDBOX_ONLY"
VAPID_DUAL = "VAPID_DUAL"
VAPID_NONE = "VAPID_NONE"


# ---- 候选 A 权重切换评估 ---------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_compare_json(path: Path) -> dict:
    """读 m7t4 compare 输出 JSON。"""
    if not path.exists():
        raise SystemExit(f"compare json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _evaluate_weight_switch(
    compare_data: dict,
    p_threshold: float = P_VALUE_THRESHOLD_DEFAULT,
) -> dict:
    """评估是否切换为候选 A 权重(V1.5.2 m10t7 P2-1)。

    Args:
        compare_data: m7t4 compare 输出 JSON
        p_threshold: p_value 显著性阈值(默认 0.05)

    Returns:
        评估结果 dict:
        - p_value: 实际 p_value
        - u_statistic: U 统计量
        - delta_hit_rate / delta_f1: 候选 A - v1.0
        - p_threshold: 阈值
        - significant: p < p_threshold
        - recommendation: "switch_to_candidate_a" | "keep_v1.0"
        - decision: 决策依据
        - source: "compare_input" | "bd087_v30_final_default"
    """
    mw = compare_data.get("mann_whitney_u", {})
    p_value = mw.get("p_value")
    u_stat = mw.get("U_statistic")
    delta_hr = compare_data.get("delta_hit_rate")
    delta_f1 = compare_data.get("delta_f1")

    # 如果 compare_data 无 p_value,沿用 BD-087 v3.0-final 已知结论
    if p_value is None:
        p_value = BD087_V30_FINAL_P_VALUE
        u_stat = BD087_V30_FINAL_U_STAT
        delta_hr = BD087_V30_FINAL_DELTA_HIT_RATE
        delta_f1 = BD087_V30_FINAL_DELTA_F1
        source = "bd087_v30_final_default"
    else:
        source = "compare_input"

    significant = p_value < p_threshold
    if significant and delta_hr is not None and delta_hr > 0:
        recommendation = "switch_to_candidate_a"
        decision = (
            f"p={p_value} < {p_threshold}(显著)+ delta_hit_rate={delta_hr} > 0(候选 A 优)→ 切换"
        )
    else:
        recommendation = "keep_v1.0"
        if not significant:
            decision = (
                f"p={p_value} >= {p_threshold}(不显著)→ 保持 v1.0(BD-087 v3.0-final 沿用)"
            )
        else:
            decision = (
                f"p={p_value} < {p_threshold}(显著)但 delta_hit_rate={delta_hr} <= 0 → 保持 v1.0"
            )

    return {
        "p_value": p_value,
        "u_statistic": u_stat,
        "delta_hit_rate": delta_hr,
        "delta_f1": delta_f1,
        "p_threshold": p_threshold,
        "significant": significant,
        "recommendation": recommendation,
        "decision": decision,
        "source": source,
        "fetched_at": _now_iso(),
    }


# ---- VAPID 沙箱生产分离 ---------------------------------------------


def _check_vapid_separator(env: dict[str, str] | None = None) -> dict:
    """校验 VAPID 沙箱(HR_ 前缀)/生产(无前缀)分离(V1.5.2 m10t7 P2-2)。

    Args:
        env: 环境变量 dict(默认用 os.environ)

    Returns:
        校验结果 dict:
        - state: VAPID_PROD_ONLY | VAPID_SANDBOX_ONLY | VAPID_DUAL | VAPID_NONE
        - has_prod_public / has_prod_private / has_sandbox_public / has_sandbox_private
        - is_production_safe: 生产环境是否安全(VAPID_PROD_ONLY 或 VAPID_NONE 才算安全)
        - warning: 警告信息
        - error: 错误信息
    """
    if env is None:
        env = dict(os.environ)

    has_prod_pub = bool(env.get(VAPID_PROD_PUBLIC))
    has_prod_priv = bool(env.get(VAPID_PROD_PRIVATE))
    has_sand_pub = bool(env.get(VAPID_SANDBOX_PUBLIC))
    has_sand_priv = bool(env.get(VAPID_SANDBOX_PRIVATE))

    # 状态判定
    if has_prod_pub and has_sand_pub:
        state = VAPID_DUAL
        warning = (
            "严重配置错:同时设了 VAPID_PUBLIC_KEY(生产)和 HR_VAPID_PUBLIC_KEY(沙箱)。"
            "生产环境严禁,沙箱环境会混淆。"
        )
        error = "VAPID_DUAL 配置错,生产部署前必须修复"
    elif has_prod_pub:
        state = VAPID_PROD_ONLY
        warning = "正常生产态:仅 VAPID_PUBLIC_KEY(生产)设了"
        error = None
    elif has_sand_pub:
        state = VAPID_SANDBOX_ONLY
        warning = (
            "⚠️ 仅沙箱 dev key(HR_VAPID_PUBLIC_KEY)设了,生产 key 缺失。"
            "生产环境禁止 — 上线前必须切到 VAPID_PUBLIC_KEY。"
        )
        error = "VAPID_SANDBOX_ONLY,生产环境禁止"
    else:
        state = VAPID_NONE
        warning = "VAPID 都没设 — 仅 CI / 单测可用,需 sandbox_skip_push"
        error = None

    is_production_safe = state in (VAPID_PROD_ONLY, VAPID_NONE)

    return {
        "state": state,
        "has_prod_public": has_prod_pub,
        "has_prod_private": has_prod_priv,
        "has_sandbox_public": has_sand_pub,
        "has_sandbox_private": has_sand_priv,
        "is_production_safe": is_production_safe,
        "warning": warning,
        "error": error,
        "fetched_at": _now_iso(),
    }


# ---- CLI 子命令 -----------------------------------------------------


def cmd_weight_switch_eval(args: argparse.Namespace) -> dict:
    """跑候选 A 权重切换评估。"""
    p_threshold = getattr(args, "p_threshold", P_VALUE_THRESHOLD_DEFAULT)
    if args.input:
        compare_data = _load_compare_json(Path(args.input))
    else:
        # 默认输入路径(m7t4 默认输出)
        compare_data = _load_compare_json(
            ROOT / "docs" / "BD-087-calibration-run-m7t4.json"
        )
    return _evaluate_weight_switch(compare_data, p_threshold)


def cmd_vapid_separator(args: argparse.Namespace) -> dict:
    """跑 VAPID 沙箱生产分离校验。"""
    return _check_vapid_separator()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="V1.5.2 接力期 m10t7 — P2 合并工具(候选 A 权重切换 + VAPID 分离)"
    )
    # V1.5.3 接力期 m11t5:--json-only 全局 flag(CI 友好输出)
    p.add_argument(
        "--json-only",
        action="store_true",
        help="V1.5.3 m11t5:CI 友好输出。单行 JSON,不含 banner / 解释。便于 jq / pipeline 解析。",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # weight-switch-eval
    p_ws = sub.add_parser(
        "weight-switch-eval",
        help="评估候选 A 权重是否切换为默认(Mann-Whitney U p_value)",
    )
    p_ws.add_argument(
        "--input",
        type=str,
        default=None,
        help="m7t4 compare 输出 JSON 路径(默认 docs/BD-087-calibration-run-m7t4.json)",
    )
    p_ws.add_argument(
        "--p-threshold",
        type=float,
        default=P_VALUE_THRESHOLD_DEFAULT,
        help="p_value 显著性阈值(默认 0.05)",
    )

    # vapid-separator
    sub.add_parser(
        "vapid-separator",
        help="VAPID 沙箱(HR_ 前缀)与生产(无前缀)密钥分离校验",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "weight-switch-eval":
        result = cmd_weight_switch_eval(args)
    elif args.cmd == "vapid-separator":
        result = cmd_vapid_separator(args)
    else:
        parser.print_help()
        return 2

    # V1.5.3 接力期 m11t5:--json-only 走单行 JSON(便于 CI / jq 解析)
    # 默认 indent=2 人类可读
    if getattr(args, "json_only", False):
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
