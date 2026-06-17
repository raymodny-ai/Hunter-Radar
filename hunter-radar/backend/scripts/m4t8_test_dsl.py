"""M4-t8 沙箱自测:DSL 评估器纯函数(不依赖 SQLAlchemy/AsyncSession)。"""
import datetime
import importlib.util
import sys
import types
from pathlib import Path

# 把 sqlalchemy 段抹掉后 exec(沙箱无 sqlalchemy)
SRC = Path("app/services/alert_rule.py").read_text(encoding="utf-8")
SRC = SRC.replace("from sqlalchemy import text", "# sqlalchemy skipped for test")
SRC = SRC.replace(
    "from sqlalchemy.ext.asyncio import AsyncSession", "# AsyncSession skipped"
)
mod = types.ModuleType("ar_test")
sys.modules["ar_test"] = mod
exec(compile(SRC, "ar_test", "exec"), mod.__dict__)


def main() -> None:
    dsl = mod.dsl_from_dict(
        {
            "when": [
                {"metric": "score.ema", "op": ">=", "value": 70},
                {"metric": "lifecycle", "op": "in", "value": ["red", "yellow"]},
                {"metric": "modules", "op": "contains", "value": "short"},
            ],
            "then": "push",
        }
    )

    # test 1: strong
    snap = mod.TickerSnapshot(
        ticker="GME",
        trade_date=datetime.date(2024, 5, 13),
        ema_score=78.5,
        raw_score=72.1,
        lifecycle="red",
        modules_active=["short", "options"],
        prev_lifecycle="yellow",
    )
    r = mod.evaluate_dsl_for_snapshot(dsl, snap, rule_id=1)
    print(f"[t1 strong] triggered={r.triggered} lifecycle={r.lifecycle} ema={r.ema_score}")
    assert r.triggered is True
    assert len(r.condition_evals) == 3
    for c in r.condition_evals:
        print(f"   {c.metric:20s} {c.op:6s} {c.expected!r}  -> passed={c.passed}  actual={c.actual}")
    print(f"   rationale: {r.rationale}")
    print()

    # test 2: weak (ema too low + green)
    snap2 = mod.TickerSnapshot(
        ticker="AAPL",
        trade_date=datetime.date(2024, 5, 13),
        ema_score=42.0,
        raw_score=40.0,
        lifecycle="green",
        modules_active=[],
        prev_lifecycle=None,
    )
    r2 = mod.evaluate_dsl_for_snapshot(dsl, snap2, rule_id=1)
    print(f"[t2 weak] triggered={r2.triggered} lifecycle={r2.lifecycle}")
    assert r2.triggered is False
    print(f"   rationale: {r2.rationale[:140]}")
    print()

    # test 3: no-data (ema=None)
    snap3 = mod.TickerSnapshot(
        ticker="XYZ",
        trade_date=datetime.date(2024, 5, 13),
        ema_score=None,
        raw_score=None,
        lifecycle="init",
        modules_active=[],
        prev_lifecycle=None,
    )
    r3 = mod.evaluate_dsl_for_snapshot(dsl, snap3, rule_id=1)
    print(f"[t3 no-data] triggered={r3.triggered}  (None should yield False)")
    assert r3.triggered is False
    print()

    # test 4: lifecycle_change
    dsl_lc = mod.dsl_from_dict(
        {
            "when": [
                {"metric": "lifecycle_change", "op": "in",
                 "value": ["gray->red", "init->red"]}
            ],
            "then": "log",
        }
    )
    snap4 = mod.TickerSnapshot(
        ticker="META",
        trade_date=datetime.date(2024, 5, 13),
        ema_score=72.0,
        raw_score=70.0,
        lifecycle="red",
        modules_active=["options"],
        prev_lifecycle="gray",
    )
    r4 = mod.evaluate_dsl_for_snapshot(dsl_lc, snap4, rule_id=2)
    print(
        f"[t4 lc-change] triggered={r4.triggered}  "
        f"change={mod._lifecycle_change('red', 'gray')}"
    )
    assert r4.triggered is True
    print()

    # test 5: DSL 校验
    for bad in (
        {"when": [], "then": "push"},
        {"when": [{"metric": "unknown", "op": ">=", "value": 1}], "then": "push"},
        {"when": [{"metric": "score.ema", "op": "~=", "value": 1}], "then": "push"},
        {"when": [{"metric": "score.ema", "op": ">=", "value": 1}], "then": "pwn"},
    ):
        try:
            mod.dsl_from_dict(bad)
            print(f"  [t5 DSL-bad {bad}] FAIL: should reject")
        except ValueError as e:
            print(f"[t5 DSL-bad] rejected: {e}")
    print()

    print("[m4t8] ALL DSL TESTS PASSED")


if __name__ == "__main__":
    main()
