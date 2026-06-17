"""§4.3 预警规则业务逻辑(BD-073)。

设计:
- DSL 数据格式(落 alert_rule.dsl JSONB):
    {
      "when": [
        {"metric": "score.ema",    "op": ">=",  "value": 75},
        {"metric": "lifecycle",    "op": "in",  "value": ["red","yellow"]},
        {"metric": "modules",      "op": "contains", "value": "short"},
        {"metric": "score.raw",    "op": "<",   "value": 60},
        {"metric": "lifecycle_change", "op": "in", "value": ["init->red","gray->red"]}
      ],
      "then": "push"   # 推送通道标识;M4 阶段仅落 alert_event,推送留待 BD-074
    }
- 评估器(evaluate_rule)走 threat_score_daily 取一段历史,逐条件 AND 判定。
- 沙箱 / 无 PG:所有 CRUD + 评估函数返 None(API 层回 503 / 200+空结果)。

硬约束:
- 不擅自修改 Threat Score 公式 / EMA 半衰期(OQ-02 锁定)
- 评估值走 ema 分(严禁用 raw 触发终极警报等同决策)
- 推送通道暂只落 alert_event,BD-074 二期再接 email/webpush
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---- DSL 数据类 ------------------------------------------------------------

ConditionMetric = Literal[
    "score.ema", "score.raw", "lifecycle", "lifecycle_change", "modules"
]
ConditionOp = Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in", "contains"]


@dataclass(slots=True, frozen=True)
class RuleCondition:
    """DSL 单条 when 条件。"""

    metric: ConditionMetric
    op: ConditionOp
    value: Any  # float | int | str | list[str]


@dataclass(slots=True, frozen=True)
class RuleDSL:
    """完整 DSL 块。"""

    when: list[RuleCondition] = field(default_factory=list)
    then_action: Literal["push", "log", "silent"] = "push"


# ---- 评估快照 ---------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class TickerSnapshot:
    """单标的一段时点的评估快照(从 threat_score_daily 抽)。"""

    ticker: str
    trade_date: date
    ema_score: float | None
    raw_score: float | None
    lifecycle: str  # init|red|yellow|gray|green
    modules_active: list[str]
    # 前一日 lifecycle(供 lifecycle_change 条件)
    prev_lifecycle: str | None = None


@dataclass(slots=True, frozen=True)
class ConditionEval:
    """单条 when 条件的评估详情(供调试 + 审计)。"""

    metric: str
    op: str
    expected: Any
    actual: Any
    passed: bool
    rationale: str


@dataclass(slots=True, frozen=True)
class RuleEvalResult:
    """单 ticker × 单 rule 的评估结果。"""

    ticker: str
    trade_date: date
    rule_id: int | None
    triggered: bool
    ema_score: float | None
    raw_score: float | None
    lifecycle: str
    condition_evals: list[ConditionEval] = field(default_factory=list)
    rationale: str = ""


# ---- DSL 序列化 / 反序列化 --------------------------------------------------


def dsl_from_dict(d: dict) -> RuleDSL:
    """将存储的 dict 转成 RuleDSL;容错:未知 metric 抛 ValueError。"""
    if not isinstance(d, dict):
        raise ValueError("dsl must be dict")
    raw_when = d.get("when", [])
    if not isinstance(raw_when, list) or not raw_when:
        raise ValueError("dsl.when must be non-empty list")
    conds: list[RuleCondition] = []
    for i, c in enumerate(raw_when):
        if not isinstance(c, dict):
            raise ValueError(f"dsl.when[{i}] must be dict")
        m = c.get("metric")
        o = c.get("op")
        v = c.get("value")
        if m not in ("score.ema", "score.raw", "lifecycle", "lifecycle_change", "modules"):
            raise ValueError(f"dsl.when[{i}].metric unknown: {m}")
        if o not in (">=", ">", "<=", "<", "==", "!=", "in", "not_in", "contains"):
            raise ValueError(f"dsl.when[{i}].op unknown: {o}")
        conds.append(RuleCondition(metric=m, op=o, value=v))
    then_action = d.get("then", "push")
    if then_action not in ("push", "log", "silent"):
        raise ValueError(f"dsl.then must be push|log|silent, got {then_action}")
    return RuleDSL(when=conds, then_action=then_action)


def dsl_to_dict(d: RuleDSL) -> dict:
    return {
        "when": [{"metric": c.metric, "op": c.op, "value": c.value} for c in d.when],
        "then": d.then_action,
    }


# ---- 评估器 -----------------------------------------------------------------


def _lifecycle_change(curr: str, prev: str | None) -> str:
    """生成 lifecycle_change 标签,例 'gray->red' / 'init->red' / 'same'。"""
    if prev is None or prev == curr:
        return f"same({curr})" if prev == curr else f"init->{curr}"
    return f"{prev}->{curr}"


def evaluate_condition(cond: RuleCondition, snap: TickerSnapshot) -> ConditionEval:
    """评估单条 when 条件。"""
    if cond.metric == "score.ema":
        actual = snap.ema_score
        passed = _eval_numeric(actual, cond.op, cond.value)
        return ConditionEval(
            metric=cond.metric,
            op=cond.op,
            expected=cond.value,
            actual=actual,
            passed=passed,
            rationale=f"score.ema={actual} {cond.op} {cond.value}" if actual is not None
            else f"score.ema=None(无数据),{cond.op} {cond.value} 视为 False",
        )
    if cond.metric == "score.raw":
        actual = snap.raw_score
        passed = _eval_numeric(actual, cond.op, cond.value)
        return ConditionEval(
            metric=cond.metric,
            op=cond.op,
            expected=cond.value,
            actual=actual,
            passed=passed,
            rationale=f"score.raw={actual} {cond.op} {cond.value}" if actual is not None
            else f"score.raw=None,{cond.op} {cond.value} 视为 False",
        )
    if cond.metric == "lifecycle":
        actual = snap.lifecycle
        passed = _eval_str_or_list(actual, cond.op, cond.value)
        return ConditionEval(
            metric=cond.metric,
            op=cond.op,
            expected=cond.value,
            actual=actual,
            passed=passed,
            rationale=f"lifecycle={actual} {cond.op} {cond.value}",
        )
    if cond.metric == "lifecycle_change":
        actual = _lifecycle_change(snap.lifecycle, snap.prev_lifecycle)
        passed = _eval_str_or_list(actual, cond.op, cond.value)
        return ConditionEval(
            metric=cond.metric,
            op=cond.op,
            expected=cond.value,
            actual=actual,
            passed=passed,
            rationale=f"lifecycle_change={actual} {cond.op} {cond.value}",
        )
    if cond.metric == "modules":
        actual = list(snap.modules_active or [])
        if cond.op == "contains":
            passed = cond.value in actual
            return ConditionEval(
                metric=cond.metric,
                op=cond.op,
                expected=cond.value,
                actual=actual,
                passed=passed,
                rationale=f"modules contains '{cond.value}': {passed}",
            )
        return ConditionEval(
            metric=cond.metric,
            op=cond.op,
            expected=cond.value,
            actual=actual,
            passed=False,
            rationale=f"modules op '{cond.op}' 未实现",
        )
    return ConditionEval(
        metric=cond.metric, op=cond.op, expected=cond.value, actual=None,
        passed=False, rationale=f"metric '{cond.metric}' 未识别",
    )


def _eval_numeric(actual: float | None, op: str, expected: Any) -> bool:
    if actual is None:
        return False
    try:
        e = float(expected)
    except (TypeError, ValueError):
        return False
    if op == ">=":
        return actual >= e
    if op == ">":
        return actual > e
    if op == "<=":
        return actual <= e
    if op == "<":
        return actual < e
    if op == "==":
        return abs(actual - e) < 1e-6
    if op == "!=":
        return abs(actual - e) >= 1e-6
    return False


def _eval_str_or_list(actual: str, op: str, expected: Any) -> bool:
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "in":
        return actual in (expected or [])
    if op == "not_in":
        return actual not in (expected or [])
    return False


def evaluate_dsl_for_snapshot(
    dsl: RuleDSL, snap: TickerSnapshot, rule_id: int | None = None
) -> RuleEvalResult:
    """单 ticker × 单 rule 的 AND 评估。"""
    evals = [evaluate_condition(c, snap) for c in dsl.when]
    triggered = all(e.passed for e in evals)
    if triggered:
        rationale = f"全部 {len(evals)} 条条件通过 → 触发 (rule #{rule_id})"
    else:
        failed = [e for e in evals if not e.passed]
        rationale = f"{len(failed)}/{len(evals)} 条未通过: " + "; ".join(e.rationale for e in failed[:3])
    return RuleEvalResult(
        ticker=snap.ticker,
        trade_date=snap.trade_date,
        rule_id=rule_id,
        triggered=triggered,
        ema_score=snap.ema_score,
        raw_score=snap.raw_score,
        lifecycle=snap.lifecycle,
        condition_evals=evals,
        rationale=rationale,
    )


# ---- 取数(从 threat_score_daily) ------------------------------------------


async def fetch_snapshot(
    session: AsyncSession,
    ticker: str,
    as_of: date,
) -> TickerSnapshot | None:
    """从 threat_score_daily 取 (T 日 + T-1 日) 一段快照。

    返回 None 表示当日无数据(此时评估器会把所有条件判为 False,
    API 层应返 200 + triggered=False,严禁 mock 伪装触发)。
    """
    sql = text(
        """
        SELECT trade_date, total, ema, lifecycle, modules_active
        FROM threat_score_daily
        WHERE symbol = :ticker
          AND trade_date IN (SELECT generate_series(:d0, :d1, '1 day'::interval)::date)
        ORDER BY trade_date DESC
        LIMIT 2
        """
    )
    try:
        rows = (await session.execute(
            sql, {"ticker": ticker, "d0": as_of, "d1": as_of}
        )).mappings().all()
    except Exception:
        return None
    if not rows:
        return None
    today = rows[0]
    yesterday = rows[1] if len(rows) > 1 else None
    modules_today = today.get("modules_active") or []
    if isinstance(modules_today, str):
        import json
        try:
            modules_today = json.loads(modules_today)
        except Exception:  # noqa: BLE001
            modules_today = []
    return TickerSnapshot(
        ticker=ticker,
        trade_date=today["trade_date"],
        ema_score=float(today["ema"]) if today.get("ema") is not None else None,
        raw_score=float(today["total"]) if today.get("total") is not None else None,
        lifecycle=str(today.get("lifecycle") or "init"),
        modules_active=list(modules_today) if modules_today else [],
        prev_lifecycle=str(yesterday.get("lifecycle")) if yesterday else None,
    )


# ---- CRUD(直接走 SQL,沙箱下返 None) ----------------------------------------


async def create_rule(
    session: AsyncSession,
    *,
    user_id: UUID,
    name: str,
    dsl: RuleDSL,
    channels: list[str] | None = None,
) -> int | None:
    """创建预警规则;返回 rule.id,沙箱 / 失败返 None。"""
    import json as _json
    chs = channels or ["email"]
    sql = text(
        """
        INSERT INTO alert_rule (user_id, name, dsl, channels, is_active, created_at, updated_at)
        VALUES (:uid, :name, CAST(:dsl AS JSONB), CAST(:chs AS JSONB), TRUE, NOW(), NOW())
        RETURNING id
        """
    )
    try:
        row = (await session.execute(sql, {
            "uid": str(user_id),
            "name": name,
            "dsl": _json.dumps(dsl_to_dict(dsl), ensure_ascii=False),
            "chs": _json.dumps(chs, ensure_ascii=False),
        })).first()
        await session.commit()
        return int(row[0]) if row else None
    except Exception:
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


async def list_rules(
    session: AsyncSession, *, user_id: UUID | None
) -> list[dict] | None:
    """列规则;user_id is None 时返全部(沙箱/管理员视角)。返 None 表示沙箱失败。"""
    sql = text(
        """
        SELECT id, user_id, name, dsl, channels, is_active, created_at, updated_at
        FROM alert_rule
        WHERE (:uid IS NULL OR user_id = CAST(:uid AS UUID))
        ORDER BY id DESC
        LIMIT 200
        """
    )
    try:
        rows = (await session.execute(
            sql, {"uid": str(user_id) if user_id else None}
        )).mappings().all()
    except Exception:
        return None
    out: list[dict] = []
    for r in rows:
        out.append({
            "id": int(r["id"]),
            "user_id": str(r["user_id"]),
            "name": r["name"],
            "dsl": r["dsl"] if isinstance(r["dsl"], dict) else {},
            "channels": r["channels"] if isinstance(r["channels"], list) else [],
            "is_active": bool(r["is_active"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        })
    return out


async def get_rule(
    session: AsyncSession, rule_id: int
) -> dict | None:
    sql = text("SELECT id, user_id, name, dsl, channels, is_active, created_at, updated_at FROM alert_rule WHERE id = :rid")
    try:
        row = (await session.execute(sql, {"rid": rule_id})).mappings().first()
    except Exception:
        return None
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "dsl": row["dsl"] if isinstance(row["dsl"], dict) else {},
        "channels": row["channels"] if isinstance(row["channels"], list) else [],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def update_rule(
    session: AsyncSession,
    rule_id: int,
    *,
    name: str | None = None,
    dsl: RuleDSL | None = None,
    channels: list[str] | None = None,
    is_active: bool | None = None,
) -> bool:
    """改名 / 改 DSL / 改 channels / 改 is_active;任意 None 字段不动。"""
    sets: list[str] = []
    params: dict[str, Any] = {"rid": rule_id}
    if name is not None:
        sets.append("name = :name")
        params["name"] = name
    if dsl is not None:
        import json as _json
        sets.append("dsl = CAST(:dsl AS JSONB)")
        params["dsl"] = _json.dumps(dsl_to_dict(dsl), ensure_ascii=False)
    if channels is not None:
        import json as _json
        sets.append("channels = CAST(:chs AS JSONB)")
        params["chs"] = _json.dumps(channels, ensure_ascii=False)
    if is_active is not None:
        sets.append("is_active = :act")
        params["act"] = is_active
    if not sets:
        return True
    sets.append("updated_at = NOW()")
    sql = text(f"UPDATE alert_rule SET {', '.join(sets)} WHERE id = :rid")
    try:
        await session.execute(sql, params)
        await session.commit()
        return True
    except Exception:
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
    sql = text("DELETE FROM alert_rule WHERE id = :rid")
    try:
        await session.execute(sql, {"rid": rule_id})
        await session.commit()
        return True
    except Exception:
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return False


async def record_alert_event(
    session: AsyncSession,
    *,
    rule_id: int,
    triggered_at: datetime,
    payload: dict,
    delivery_status: dict | None = None,
) -> int | None:
    """落 alert_event;沙箱/失败返 None。M4 阶段 delivery_status 默认空 dict(推送留待 BD-074)。"""
    import json as _json
    sql = text(
        """
        INSERT INTO alert_event (rule_id, triggered_at, payload, delivery_status)
        VALUES (:rid, :ts, CAST(:p AS JSONB), CAST(:ds AS JSONB))
        RETURNING id
        """
    )
    try:
        row = (await session.execute(sql, {
            "rid": rule_id,
            "ts": triggered_at,
            "p": _json.dumps(payload, ensure_ascii=False, default=str),
            "ds": _json.dumps(delivery_status or {}, ensure_ascii=False),
        })).first()
        await session.commit()
        return int(row[0]) if row else None
    except Exception:
        try:
            await session.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
