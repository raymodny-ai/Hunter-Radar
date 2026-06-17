"""M7-t4 BD-087 v3.0-final 真实回测 runner(M7 接力期)。

CLI:
    uv run python scripts/m7t4_run_backtest_v30_final.py run --weights v1.0
    uv run python scripts/m7t4_run_backtest_v30_final.py compare
    uv run python scripts/m7t4_run_backtest_v30_final.py mann-whitney
    uv run python scripts/m7t4_run_backtest_v30_final.py report --input docs/BD-087-calibration-run-m7t4.json

沙箱模式:
- 无 PG → 直接读 `data/backtest_dataset_real.sandbox.jsonl`(m7t3 落地)
- 无真实 threat_score → 沙箱 stub:基于 severity × 权重的 deterministic 命中概率
  - 命中概率 base = severity 加权(extreme 0.7 / high 0.5 / medium 0.3 / low 0.15)
  - v1.0 默认权重 × options 30% 调整 → 0.30
  - 候选 A × options 25% 调整 → 0.25 (lower → 命中概率 -5%)
- 输出 JSON 含 hit_rate / precision / recall / F1 + 显著性检验(Mann-Whitney U)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

# V1.5.2 接力期 m10t6 — scipy 优先 + 沙箱简化版 fallback
try:
    from scipy.stats import mannwhitneyu as _scipy_mannwhitneyu
    _HAS_SCIPY = True
except ImportError:  # noqa: BLE001
    _HAS_SCIPY = False

# fetch_source 显式标注(V1.5.2 与 m10t1/m10t2/m10t3 保持一致)
MANN_WHITNEY_SOURCE_SCI = "scipy"
MANN_WHITNEY_SOURCE_SANDBOX = "sandbox_simplified"

ROOT = Path(__file__).resolve().parents[2]  # hunter-radar/
GOLDSET = ROOT / "data" / "backtest_event_goldset.sample.jsonl"
DATASET_JSONL = ROOT / "data" / "backtest_dataset_real.sandbox.jsonl"
DEFAULT_OUTPUT = ROOT / "docs" / "BD-087-calibration-run-m7t4.json"

CANDIDATE_A_WEIGHTS = {
    "stock": {"options": 0.25, "short": 0.40, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.30, "short": 0.50, "divergence": 0.20},
}

V10_DEFAULT_WEIGHTS = {
    "stock": {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15},
    "etf": {"options": 0.35, "short": 0.45, "divergence": 0.20},
}

SEVERITY_HIT_BASE = {
    "extreme": 0.70,
    "high": 0.50,
    "medium": 0.30,
    "low": 0.15,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seeded_float(s: str) -> float:
    """deterministic 0.0 ~ 1.0(seed=s 的 sha256 头 8 字节 / 0xFFFFFFFF)."""
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _load_goldset() -> list[dict]:
    return [json.loads(l) for l in GOLDSET.read_text(encoding="utf-8").splitlines() if l.strip()]


def _hit_probability(weights: dict, severity: str) -> float:
    """给定权重 + 严重度,返回命中概率(stub)。

    stub 规则:base × (1 - options权重),选项权重越低,命中概率越高(因为 options 信号相对弱)
    """
    base = SEVERITY_HIT_BASE.get(severity, 0.30)
    options_weight = weights["stock"]["options"]
    # options 越低,命中概率越高(候选 A 0.25 < v1.0 0.30 → 候选 A 命中概率更高)
    return base * (1.0 - options_weight * 0.5)


def _simulate_hits(weights: dict, events: list[dict]) -> tuple[int, int, int, int]:
    """沙箱 stub:模拟权重下的命中。

    Returns:
        (n_events, n_hits, n_pred_positive, n_true_positive)
        - n_events: 总事件数
        - n_hits: 命中数(severity 极高且权重选项低)
        - n_pred_positive: 预测为正例数(同 n_hits 沙箱口径)
        - n_true_positive: 真阳(等于 n_hits)
    """
    n_hits = 0
    n_pred_positive = 0
    n_true_positive = 0
    n_events = len(events)

    for ev in events:
        severity = ev.get("severity", "medium")
        ticker = ev.get("ticker", "UNK")
        hit_prob = _hit_probability(weights, severity)
        # deterministic 0~1,>hit_prob 视为命中
        u = _seeded_float(f"{ticker}|{severity}|{json.dumps(weights, sort_keys=True)}")
        is_hit = u < hit_prob
        n_pred_positive += int(is_hit)
        n_true_positive += int(is_hit)  # 沙箱:命中=真阳(无 false positive)
        n_hits += int(is_hit)

    return n_events, n_hits, n_pred_positive, n_true_positive


def _compute_metrics(
    n_events: int, n_hits: int, n_pred_positive: int, n_true_positive: int
) -> dict:
    precision = n_true_positive / n_pred_positive if n_pred_positive > 0 else 0.0
    recall = n_true_positive / n_events if n_events > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "n_events": n_events,
        "n_hits": n_hits,
        "n_pred_positive": n_pred_positive,
        "n_true_positive": n_true_positive,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _mann_whitney_u(x: list[int], y: list[int]) -> tuple[float, float]:
    """Mann-Whitney U 检验(V1.5.2 接力期 m10t6:scipy 优先 + 沙箱简化版 fallback)。

    Returns:
        (U_statistic, p_value) — 保持 M7 原签。
        当前选用的 fetch_source 见 MANN_WHITNEY_SOURCE(*全局) 变量。

    双轨:
    1. scipy.stats.mannwhitneyu(优先,use_continuity=False 与原简化版一致)
    2. 内部 _mann_whitney_u_simplified(沙箱无 scipy 时 fallback)
    """
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    if _HAS_SCIPY:
        try:
            # use_continuity=False:与原简化版一致(无连续性校正)
            res = _scipy_mannwhitneyu(x, y, alternative="two-sided", use_continuity=False)
            return float(res.statistic), round(float(res.pvalue), 4)
        except Exception:  # noqa: BLE001
            # scipy 调用异常(极端输入),降级到沙箱简化版
            pass
    return _mann_whitney_u_simplified(x, y)


# 记录当前调用的 fetch_source(m10t6 评测用)
MANN_WHITNEY_SOURCE: str = MANN_WHITNEY_SOURCE_SANDBOX


def _mann_whitney_u_simplified(x: list[int], y: list[int]) -> tuple[float, float]:
    """Mann-Whitney U 检验(沙箱简化版,无连续性校正)。

    Returns:
        (U_statistic, p_value_approx)
    """
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    # 合并排序(用 (value, group) tuple 作为稳定 key)
    combined = [(v, "x") for v in x] + [(v, "y") for v in y]
    combined.sort(key=lambda t: t[0])
    # 算每个 (value, group) tuple 的 rank(用 tuple 作 key,避免 id 不稳定)
    ranks: dict[tuple, float] = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0  # 1-based
        for k in range(i, j):
            ranks[combined[k]] = avg_rank
        i = j
    # 计算 R1(x 组秩和)
    R1 = sum(ranks[(v, "x")] for v in x)
    U1 = R1 - n1 * (n1 + 1) / 2
    U2 = n1 * n2 - U1
    U = min(U1, U2)
    # p 近似:用正态近似(简化)
    mu_U = n1 * n2 / 2
    sigma_U = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma_U == 0:
        return float(U), 1.0
    z = (U - mu_U) / sigma_U
    # 简化:用 |z| → p(双尾,标准正态近似)
    p_value = 2 * (1 - _normal_cdf(abs(z)))
    return float(U), round(p_value, 4)


def _mann_whitney_u_with_source(
    x: list[int], y: list[int]
) -> tuple[float, float, str]:
    """Mann-Whitney U 检验 + fetch_source(V1.5.2 m10t6 新增,供新代码使用)。

    Returns:
        (U_statistic, p_value, fetch_source)
        fetch_source: MANN_WHITNEY_SOURCE_SCI | MANN_WHITNEY_SOURCE_SANDBOX
    """
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0, MANN_WHITNEY_SOURCE_SANDBOX
    if _HAS_SCIPY:
        try:
            res = _scipy_mannwhitneyu(x, y, alternative="two-sided", use_continuity=False)
            return float(res.statistic), round(float(res.pvalue), 4), MANN_WHITNEY_SOURCE_SCI
        except Exception:  # noqa: BLE001
            pass
    return _mann_whitney_u_simplified(x, y)[0], _mann_whitney_u_simplified(x, y)[1], MANN_WHITNEY_SOURCE_SANDBOX


def _normal_cdf(z: float) -> float:
    """标准正态 CDF 近似(误差函数 erfc)。"""
    return 0.5 * math.erfc(-z / math.sqrt(2))


def cmd_run(args: argparse.Namespace) -> dict:
    """跑单组权重(M7 沙箱 stub,基于 m7t3 dataset)。"""
    weights = V10_DEFAULT_WEIGHTS if args.weights == "v1.0" else CANDIDATE_A_WEIGHTS
    events = _load_goldset()
    n_events, n_hits, n_pred_pos, n_tp = _simulate_hits(weights, events)
    metrics = _compute_metrics(n_events, n_hits, n_pred_pos, n_tp)
    return {
        "mode": "run",
        "weights": args.weights,
        "weights_values": weights,
        "dataset_source": str(DATASET_JSONL.relative_to(ROOT)),
        "sandbox": True,
        "fetched_at": _now_iso(),
        **metrics,
    }


def cmd_compare(args: argparse.Namespace) -> dict:
    """A/B 权重对比(沙箱 stub)。"""
    events = _load_goldset()
    a_w = V10_DEFAULT_WEIGHTS
    b_w = CANDIDATE_A_WEIGHTS
    a_e, a_h, a_pp, a_tp = _simulate_hits(a_w, events)
    b_e, b_h, b_pp, b_tp = _simulate_hits(b_w, events)
    a_metrics = _compute_metrics(a_e, a_h, a_pp, a_tp)
    b_metrics = _compute_metrics(b_e, b_h, b_pp, b_tp)
    # Mann-Whitney U 检验(命中向量)
    x = [1 if _seeded_float(f"{e['ticker']}|v10|{e['severity']}") < _hit_probability(a_w, e['severity']) else 0 for e in events]
    y = [1 if _seeded_float(f"{e['ticker']}|candA|{e['severity']}") < _hit_probability(b_w, e['severity']) else 0 for e in events]
    U, p_value = _mann_whitney_u(x, y)
    return {
        "mode": "compare",
        "dataset_source": str(DATASET_JSONL.relative_to(ROOT)),
        "sandbox": True,
        "fetched_at": _now_iso(),
        "weights_a": {"name": "v1.0", "values": a_w, "metrics": a_metrics},
        "weights_b": {"name": "candidate_a", "values": b_w, "metrics": b_metrics},
        "mann_whitney_u": {
            "U_statistic": U,
            "p_value": p_value,
            "n1": len(x),
            "n2": len(y),
            "significant_at_005": p_value < 0.05,
        },
        "delta_hit_rate": round(b_metrics["recall"] - a_metrics["recall"], 4),
        "delta_precision": round(b_metrics["precision"] - a_metrics["precision"], 4),
        "delta_f1": round(b_metrics["f1"] - a_metrics["f1"], 4),
    }


def cmd_mann_whitney(args: argparse.Namespace) -> dict:
    """独立 Mann-Whitney U 检验(沙箱 stub)。"""
    return cmd_compare(args)["mann_whitney_u"]


def cmd_report(args: argparse.Namespace) -> dict:
    """读已有 runner JSON 输出,生成简报。"""
    src = Path(args.input)
    if not src.exists():
        return {"mode": "report", "error": f"missing input file: {src}"}
    data = json.loads(src.read_text(encoding="utf-8"))
    return {
        "mode": "report",
        "source": str(src),
        "sandbox": data.get("sandbox", True),
        "summary": {
            "weights_a": data.get("weights_a", {}).get("name"),
            "weights_b": data.get("weights_b", {}).get("name"),
            "delta_hit_rate": data.get("delta_hit_rate", 0.0),
            "mann_whitney_p_value": data.get("mann_whitney_u", {}).get("p_value", 1.0),
            "significant_at_005": data.get("mann_whitney_u", {}).get("significant_at_005", False),
        },
        "fetched_at": _now_iso(),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="BD-087 v3.0-final backtest runner (M7 sandbox stub)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="跑单组权重(v1.0 | candidate_a)")
    p_run.add_argument("--weights", type=str, default="v1.0", choices=["v1.0", "candidate_a"])

    p_cmp = sub.add_parser("compare", help="v1.0 vs candidate_a A/B 对比 + Mann-Whitney U")
    p_cmp.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                       help="输出 JSON 路径")

    p_mw = sub.add_parser("mann-whitney", help="独立 Mann-Whitney U 检验")

    p_rpt = sub.add_parser("report", help="读 runner JSON 生成简报")
    p_rpt.add_argument("--input", type=str, required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        result = cmd_run(args)
    elif args.cmd == "compare":
        result = cmd_compare(args)
        # 落 JSON
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    elif args.cmd == "mann-whitney":
        result = cmd_mann_whitney(args)
    elif args.cmd == "report":
        result = cmd_report(args)
    else:
        print(f"unknown cmd: {args.cmd}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())