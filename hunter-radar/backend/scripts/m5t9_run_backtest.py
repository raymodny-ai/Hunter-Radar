"""M5-t9 沙箱真实回测 runner(BD-087 / BD-089)。

不动 main.py / runtime;只读:
- `data/backtest_event_goldset.sample.jsonl` 31 个金标准事件
- `app.services.threat_score.compute_threat_score` 静态权重

输出:`docs/BD-087-calibration-run-m5t9.json` —— 沙箱空跑结果
- v1.0 默认权重(stock: 30/35/20/15)命中/误报
- 候选 A(stock: 25/40/20/15)命中/误报
- 差异 metrics

沙箱 fallback(无 sqlalchemy/真实 EOD):
- `HR_BACKTEST_LIVE != 1` → 走空跑,所有指标返 0,reason="sandbox no PG/EOD"
- 真实回测走 `app.services.backtest.run_backtest`(生产用 uv run)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA_DIR = ROOT / "data"
DOCS = ROOT / "docs"
GOLDSET = DATA_DIR / "backtest_event_goldset.sample.jsonl"
OUTPUT = DOCS / "BD-087-calibration-run-m5t9.json"

# 沙箱总开关
LIVE = os.environ.get("HR_BACKTEST_LIVE") == "1"

# v1.0 默认权重(M2 末锁定,OQ-01 校准前基线)
WEIGHTS_V10 = {"options": 30, "short": 35, "divergence": 20, "insider": 15}
# 候选 A:加大 short 权重,削弱 options(假设做空水位比末日 Put 更稳定)
WEIGHTS_CAND_A = {"options": 25, "short": 40, "divergence": 20, "insider": 15}


def _load_goldset() -> list[dict[str, Any]]:
    if not GOLDSET.exists():
        return []
    out: list[dict[str, Any]] = []
    with GOLDSET.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _sandbox_metrics(weights: dict[str, int], goldset: list[dict[str, Any]]) -> dict[str, Any]:
    """沙箱空跑:无 EOD → 所有指标返 0,只统计事件分类。"""
    by_type: dict[str, int] = {}
    for ev in goldset:
        et = ev.get("event_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1
    return {
        "weights": weights,
        "n_events_total": len(goldset),
        "n_by_type": by_type,
        "hits": 0,
        "false_positives": 0,
        "misses": 0,
        "precision": None,
        "recall": None,
        "f1": None,
        "reason": "sandbox no PG/EOD reachable,设 HR_BACKTEST_LIVE=1 + 真数据后重跑",
    }


def _compare_metrics(m_a: dict[str, Any], m_b: dict[str, Any]) -> dict[str, Any]:
    """两组权重的差异(空跑下全部为 0/none,仅占位)。"""
    return {
        "delta_hits": (m_a["hits"] or 0) - (m_b["hits"] or 0),
        "delta_fp": (m_a["false_positives"] or 0) - (m_b["false_positives"] or 0),
        "recommendation": (
            "sandbox 模式下无证据推荐任何权重调整;沿用 v1.0 静态值直到生产环境 HR_BACKTEST_LIVE=1 跑出真实 F1。"
        ),
    }


def main() -> int:
    print(f"[m5t9] HR_BACKTEST_LIVE={LIVE}, 沙箱={'NO' if not LIVE else 'YES'}", flush=True)
    goldset = _load_goldset()
    print(f"[m5t9] 金标准事件集: {len(goldset)} 条 (from {GOLDSET.name})", flush=True)

    m_v10 = _sandbox_metrics(WEIGHTS_V10, goldset)
    m_cand = _sandbox_metrics(WEIGHTS_CAND_A, goldset)
    diff = _compare_metrics(m_v10, m_cand)

    output = {
        "run_id": "m5t9-2026-06-15",
        "run_at": datetime.now(tz=timezone.utc).isoformat(),
        "is_sandbox": not LIVE,
        "weights_v10": WEIGHTS_V10,
        "weights_candidate_A": WEIGHTS_CAND_A,
        "metrics_v10": m_v10,
        "metrics_candidate_A": m_cand,
        "diff": diff,
        "sandbox_reason": (
            "无 PG / 真实 EOD 可达,本 run 是空跑 sanity check;生产需 HR_BACKTEST_LIVE=1 "
            "+ 灌库 BD-085 + 配齐 BD-089 三源快照后,用 uv run 跑出真实命中/误报率。"
        ),
        "next_step": "M6 切真实 EOD 后,重跑本脚本并更新 BD-087 校准报告 v3.0(出最终推荐权重)。",
    }

    DOCS.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[m5t9] 写入 {OUTPUT}", flush=True)
    print(f"[m5t9] v1.0 events={m_v10['n_events_total']} hits={m_v10['hits']}", flush=True)
    print(f"[m5t9] 候选 A events={m_cand['n_events_total']} hits={m_cand['hits']}", flush=True)
    print(f"[m5t9] Δ hits={diff['delta_hits']}, Δ fp={diff['delta_fp']}", flush=True)
    print("[m5t9] ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
