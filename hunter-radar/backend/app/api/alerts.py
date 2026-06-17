"""§4.3 预警规则端点(BD-073)。

主路径:`/api/v1/alert-rules`(RESTful)
兼容别名:`POST /api/v1/alerts/rules`(M3 留的占位,内部转发到主路径)

端点:
- POST   /alert-rules                创建
- GET    /alert-rules                列表
- GET    /alert-rules/{id}           详情
- PUT    /alert-rules/{id}           改名 / 改 DSL / 改 channels / 改 is_active
- DELETE /alert-rules/{id}           级联删 alert_event
- POST   /alert-rules/{id}/eval      评估(给 ticker 列表 + as_of,返触发与否)

M5 接力期 user_id 走 JWT(BD-075 落地);X-User-Id 兼容(优先级低于 JWT,M6 退场)。
推送通道留待 BD-074 二期,本阶段仅落 alert_event 表。
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TUser, get_current_user
from app.core.database import get_session
from app.services import alert_rule as ar_svc

router = APIRouter()


# ---- DTO ----


class RuleConditionDTO(BaseModel):
    """DSL 单条 when 条件。"""

    metric: Literal["score.ema", "score.raw", "lifecycle", "lifecycle_change", "modules"]
    op: Literal[">=", ">", "<=", "<", "==", "!=", "in", "not_in", "contains"]
    value: Any


class RuleDSLDTO(BaseModel):
    """完整 DSL 块。"""

    when: list[RuleConditionDTO] = Field(..., min_length=1, max_length=20)
    then: Literal["push", "log", "silent"] = "push"


class AlertRuleCreateDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    dsl: RuleDSLDTO
    channels: list[str] = Field(default_factory=lambda: ["email"])


class AlertRuleUpdateDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    dsl: RuleDSLDTO | None = None
    channels: list[str] | None = None
    is_active: bool | None = None


class AlertRuleDTO(BaseModel):
    id: int
    user_id: UUID
    name: str
    dsl: RuleDSLDTO
    channels: list[str]
    is_active: bool
    created_at: str
    updated_at: str


class AlertRuleEvalRequestDTO(BaseModel):
    """评估请求:给 ticker 列表 + 评估日(默认今天)。"""

    tickers: list[str] = Field(..., min_length=1, max_length=200)
    as_of: _date | None = None
    persist: bool = Field(default=False, description="是否落 alert_event 记录(默认仅 dry-run)")


class ConditionEvalDTO(BaseModel):
    metric: str
    op: str
    expected: Any
    actual: Any
    passed: bool
    rationale: str


class AlertRuleEvalResultDTO(BaseModel):
    ticker: str
    trade_date: _date
    rule_id: int | None
    triggered: bool
    ema_score: float | None
    raw_score: float | None
    lifecycle: str
    condition_evals: list[ConditionEvalDTO]
    rationale: str
    event_id: int | None = None  # 持久化后回填


class AlertRuleEvalSummaryDTO(BaseModel):
    rule_id: int
    as_of: _date
    requested: int
    evaluated: int
    triggered: int
    no_data: int
    results: list[AlertRuleEvalResultDTO]
    warning: str | None = None  # 数据缺失 / 沙箱无 PG 等


# ---- 内部辅助 ----


def _dto_from_dict(d: dict) -> AlertRuleDTO:
    raw_dsl = d.get("dsl") or {}
    conds = [
        RuleConditionDTO(metric=c["metric"], op=c["op"], value=c["value"])
        for c in raw_dsl.get("when", [])
    ]
    return AlertRuleDTO(
        id=int(d["id"]),
        user_id=UUID(d["user_id"]),
        name=d["name"],
        dsl=RuleDSLDTO(when=conds, then=raw_dsl.get("then", "push")),
        channels=list(d.get("channels") or []),
        is_active=bool(d.get("is_active", True)),
        created_at=d.get("created_at") or "",
        updated_at=d.get("updated_at") or "",
    )


def _eval_to_dto(r: ar_svc.RuleEvalResult) -> AlertRuleEvalResultDTO:
    return AlertRuleEvalResultDTO(
        ticker=r.ticker,
        trade_date=r.trade_date,
        rule_id=r.rule_id,
        triggered=r.triggered,
        ema_score=r.ema_score,
        raw_score=r.raw_score,
        lifecycle=r.lifecycle,
        condition_evals=[
            ConditionEvalDTO(
                metric=e.metric,
                op=e.op,
                expected=e.expected,
                actual=e.actual,
                passed=e.passed,
                rationale=e.rationale,
            )
            for e in r.condition_evals
        ],
        rationale=r.rationale,
    )


# ---- 端点(主路径 /alert-rules) ----


@router.post(
    "/alert-rules",
    response_model=AlertRuleDTO,
    status_code=201,
    summary="创建预警规则(BD-073)",
)
async def create_alert_rule(
    payload: AlertRuleCreateDTO,
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleDTO:
    dsl = ar_svc.dsl_from_dict({"when": [c.model_dump() for c in payload.dsl.when], "then": payload.dsl.then})
    rid = await ar_svc.create_rule(
        session,
        user_id=user.user_id,
        name=payload.name,
        dsl=dsl,
        channels=payload.channels,
    )
    if rid is None:
        raise HTTPException(
            status_code=503,
            detail="alert_rule.create failed(沙箱无 PG 或 schema 未初始化,设 HR_PG_OK=1 后重试)",
        )
    got = await ar_svc.get_rule(session, rid)
    if got is None:
        raise HTTPException(status_code=404, detail="rule not found after create")
    return _dto_from_dict(got)


@router.get(
    "/alert-rules",
    response_model=list[AlertRuleDTO],
    summary="列预警规则(BD-073)",
)
async def list_alert_rules(
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertRuleDTO]:
    use_filter = user.is_authenticated
    rows = await ar_svc.list_rules(session, user_id=user.user_id if use_filter else None)
    if rows is None:
        raise HTTPException(
            status_code=503,
            detail="alert_rule.list failed(沙箱无 PG 或 schema 未初始化)",
        )
    return [_dto_from_dict(r) for r in rows]


@router.get(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleDTO,
    summary="预警规则详情(BD-073)",
)
async def get_alert_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleDTO:
    got = await ar_svc.get_rule(session, rule_id)
    if got is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "rule not found", "id": rule_id},
        )
    return _dto_from_dict(got)


@router.put(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleDTO,
    summary="改规则(改名 / DSL / channels / is_active,BD-073)",
)
async def update_alert_rule(
    rule_id: int,
    payload: AlertRuleUpdateDTO,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleDTO:
    new_dsl = None
    if payload.dsl is not None:
        new_dsl = ar_svc.dsl_from_dict(
            {"when": [c.model_dump() for c in payload.dsl.when], "then": payload.dsl.then}
        )
    ok = await ar_svc.update_rule(
        session,
        rule_id,
        name=payload.name,
        dsl=new_dsl,
        channels=payload.channels,
        is_active=payload.is_active,
    )
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="alert_rule.update failed(沙箱无 PG 或 rule 不存在)",
        )
    got = await ar_svc.get_rule(session, rule_id)
    if got is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "rule not found", "id": rule_id},
        )
    return _dto_from_dict(got)


@router.delete(
    "/alert-rules/{rule_id}",
    status_code=204,
    summary="删除规则(级联删 alert_event,BD-073)",
)
async def delete_alert_rule(
    rule_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    ok = await ar_svc.delete_rule(session, rule_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"message": "rule not found or delete failed", "id": rule_id},
        )


@router.post(
    "/alert-rules/{rule_id}/eval",
    response_model=AlertRuleEvalSummaryDTO,
    summary="评估规则(给 ticker 列表,BD-073;推送 BD-074 m5t3 email 通道已落地)",
)
async def evaluate_alert_rule(
    rule_id: int,
    payload: AlertRuleEvalRequestDTO,
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleEvalSummaryDTO:
    rule = await ar_svc.get_rule(session, rule_id)
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "rule not found", "id": rule_id},
        )
    if not rule.get("is_active", True):
        raise HTTPException(
            status_code=409,
            detail={"message": "rule is_active=False,暂不评估", "id": rule_id},
        )
    dsl = ar_svc.dsl_from_dict(rule["dsl"])
    as_of = payload.as_of or _date.today()
    results: list[AlertRuleEvalResultDTO] = []
    triggered_count = 0
    no_data_count = 0
    warning: str | None = None
    for raw_t in payload.tickers:
        t = raw_t.strip().upper()
        if not t:
            continue
        snap = await ar_svc.fetch_snapshot(session, t, as_of)
        if snap is None:
            no_data_count += 1
            # 数据缺失 → 不 mock,触发=False,rationale 显式说明
            results.append(AlertRuleEvalResultDTO(
                ticker=t,
                trade_date=as_of,
                rule_id=rule_id,
                triggered=False,
                ema_score=None,
                raw_score=None,
                lifecycle="init",
                condition_evals=[],
                rationale=f"无 threat_score_daily 数据(as_of={as_of},不 mock 伪装)",
            ))
            warning = (warning + "; " if warning else "") + f"{t}:无数据"
            continue
        eval_res = ar_svc.evaluate_dsl_for_snapshot(dsl, snap, rule_id=rule_id)
        event_id: int | None = None
        if eval_res.triggered and payload.persist:
            # m5t3 落地:推送走 dispatch_event(channels, recipient, event_payload)
            from app.services.push import dispatch_event

            event_payload = {
                "ticker": t,
                "trade_date": as_of.isoformat(),
                "ema_score": eval_res.ema_score,
                "raw_score": eval_res.raw_score,
                "lifecycle": eval_res.lifecycle,
                "rationale": eval_res.rationale,
                "rule_id": rule_id,
            }
            # 沙箱占位邮箱(M6 接 user profile 后取真 email)
            recipient = f"sandbox+{user.user_id}@hunter-radar.example"
            delivery_status = dispatch_event(
                channels=rule.get("channels") or ["email"],
                recipient_email=recipient,
                event_payload=event_payload,
            )
            event_id = await ar_svc.record_alert_event(
                session,
                rule_id=rule_id,
                triggered_at=ar_svc.now_utc(),
                payload=event_payload,
                delivery_status=delivery_status,
            )
        if eval_res.triggered:
            triggered_count += 1
        results.append(AlertRuleEvalResultDTO(
            ticker=t,
            trade_date=as_of,
            rule_id=rule_id,
            triggered=eval_res.triggered,
            ema_score=eval_res.ema_score,
            raw_score=eval_res.raw_score,
            lifecycle=eval_res.lifecycle,
            condition_evals=[
                ConditionEvalDTO(
                    metric=e.metric, op=e.op, expected=e.expected,
                    actual=e.actual, passed=e.passed, rationale=e.rationale,
                )
                for e in eval_res.condition_evals
            ],
            rationale=eval_res.rationale,
            event_id=event_id,
        ))

    return AlertRuleEvalSummaryDTO(
        rule_id=rule_id,
        as_of=as_of,
        requested=len(payload.tickers),
        evaluated=len(results),
        triggered=triggered_count,
        no_data=no_data_count,
        results=results,
        warning=warning,
    )


# ---- 兼容别名(M3 占位) ----


@router.post(
    "/alerts/rules",
    response_model=AlertRuleDTO,
    status_code=201,
    summary="创建预警规则(BD-073 兼容别名,推荐用 /alert-rules)",
)
async def create_alert_rule_legacy(
    payload: AlertRuleCreateDTO,
    user: TUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRuleDTO:
    return await create_alert_rule(
        payload=payload, user=user, session=session
    )
