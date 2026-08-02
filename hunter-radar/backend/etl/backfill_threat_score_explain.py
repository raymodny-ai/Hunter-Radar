"""历史回填 threat_score_daily 的 4.1 评分分解列 + data_quality。

背景: 断裂点 3 (a2ff808) 引入 data_quality 落库、4.1 (3a92e58) 引入
module_scores_json / module_quality / confidence / active_modules 列并在新 ETL 落库,
但**历史行**(2026-04-24 ~ 2026-07-30)在列引入前写入, 这些新列全 NULL。

本脚本从已持久化的 module_options/module_short/module_divergence/module_insider/
weights 重建这些列(与 load_threat_score 的推导一致), 幂等可重跑。

用法:
    uv run python -m etl.backfill_threat_score_explain [--dry-run] [--date YYYY-MM-DD]

--date 只回填指定日; 省略则回填所有 module_quality IS NULL 的行。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from sqlalchemy import text as _t

from app.core.database import AsyncSessionLocal

# 与 load_threat_score._is_data_warmup / CA-11 对齐
MIN_ACTIVE_MODULES = 2

SCOPE_BY_TYPE = {
    # etf 无 insider 模块
    "etf": ["options", "short", "divergence"],
    "stock": ["options", "short", "divergence", "insider"],
}


def _build_explain(
    *,
    mod_opts, mod_short, mod_div, mod_insider,
    symbol_type: str,
) -> dict:
    scope = SCOPE_BY_TYPE.get(symbol_type, ["options", "short", "divergence", "insider"])
    scores = {
        "options": mod_opts,
        "short": mod_short,
        "divergence": mod_div,
        "insider": mod_insider,
    }
    module_scores = {m: (round(float(scores[m]), 2) if scores[m] is not None else None) for m in scope}
    active = [m for m in scope if module_scores[m] is not None]
    module_quality = {m: ("complete" if module_scores[m] is not None else "missing") for m in scope}
    active_modules = len(active)
    confidence = "high" if active_modules >= MIN_ACTIVE_MODULES else "insufficient_data"
    data_quality = "complete" if active_modules == len(scope) else "partial"

    return {
        "module_scores_json": json.dumps(module_scores, ensure_ascii=False),
        "module_quality": json.dumps(module_quality, ensure_ascii=False),
        "confidence": confidence,
        "active_modules": active_modules,
        "data_quality": data_quality,
    }


async def run(dry_run: bool = False, only_date: str | None = None) -> int:
    where = "WHERE module_quality IS NULL"
    params: dict = {}
    if only_date:
        where += " AND trade_date = :d"
        params["d"] = only_date

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                _t(
                    f"SELECT trade_date, symbol, symbol_type, module_options, "
                    f"module_short, module_divergence, module_insider, data_quality "
                    f"FROM threat_score_daily {where} ORDER BY trade_date"
                )
            )
        ).all()

    print(f"[backfill] 待回填 {len(rows)} 行 ({'DRY-RUN' if dry_run else 'apply'})")
    if dry_run:
        # 打印前 3 行预览
        for r in rows[:3]:
            b = _build_explain(
                mod_opts=r.module_options, mod_short=r.module_short,
                mod_div=r.module_divergence, mod_insider=r.module_insider,
                symbol_type=r.symbol_type,
            )
            print(f"  {r.trade_date} {r.symbol} ({r.symbol_type}) -> "
                  f"active={b['active_modules']} conf={b['confidence']} dq={b['data_quality']} "
                  f"mq={b['module_quality']}")
        return len(rows)

    updated = 0
    async with AsyncSessionLocal() as session:
        for r in rows:
            b = _build_explain(
                mod_opts=r.module_options, mod_short=r.module_short,
                mod_div=r.module_divergence, mod_insider=r.module_insider,
                symbol_type=r.symbol_type,
            )
            await session.execute(
                _t(
                    "UPDATE threat_score_daily SET module_scores_json=:msj, "
                    "module_quality=:mq, confidence=:conf, active_modules=:am, "
                    "data_quality=COALESCE(data_quality,:dq) "
                    "WHERE trade_date=:d AND symbol=:s"
                ),
                {
                    "msj": b["module_scores_json"],
                    "mq": b["module_quality"],
                    "conf": b["confidence"],
                    "am": b["active_modules"],
                    "dq": b["data_quality"],
                    "d": r.trade_date,
                    "s": r.symbol,
                },
            )
            updated += 1
        await session.commit()

    print(f"[backfill] ✅ 更新 {updated} 行")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description="回填 threat_score_daily 评分分解列")
    ap.add_argument("--dry-run", action="store_true", help="只预览不写入")
    ap.add_argument("--date", default=None, help="只回填指定 YYYY-MM-DD")
    args = ap.parse_args()

    n = asyncio.run(run(dry_run=args.dry_run, only_date=args.date))
    if n == 0:
        print("[backfill] 无需回填(全部已填充)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
