"""§4 自定义分析 — 自选篮子服务(BD-070 / BD-071)。

职责:
1. 篮子 CRUD + 成员增删
2. 篮子分布计算(取最近 N 日 threat_score_daily,算分位数 + 落库 basket_snapshot)
3. user_id 走 Header(M4 接力期未实装 JWT,BD-075 替换为 JWT 鉴权)

严格规则:
- 不 mock 伪装数据:无数据时返空,前端显占位
- 落库走 pg_insert ON CONFLICT DO UPDATE
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Symbol

log = logging.getLogger(__name__)


@dataclass(slots=True)
class BasketCreatePayload:
    user_id: UUID
    name: str
    description: str | None = None


@dataclass(slots=True)
class BasketSummary:
    id: int
    user_id: UUID
    name: str
    description: str | None
    member_count: int
    created_at: str  # ISO8601
    updated_at: str  # ISO8601


@dataclass(slots=True)
class BasketDistribution:
    """篮子分布(BD-071)。"""

    basket_id: int
    trade_date: date
    ticker_count: int
    day_count: int
    mean: float
    p25: float
    p50: float
    p75: float
    p90: float
    p99: float
    min_score: float
    max_score: float
    by_ticker: list[dict]  # [{ticker, latest, mean, max, lifecycle}]


# ---- CRUD ----


async def create_basket(payload: BasketCreatePayload) -> int | None:
    """创建篮子(BD-070)。返回 basket.id;失败返 None。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl = Symbol.__table__.metadata.tables["basket"]
            row = {
                "user_id": payload.user_id,
                "name": payload.name,
                "description": payload.description,
            }
            stmt = pg_insert(tbl).values(row).returning(tbl.c.id)
            rs = await session.execute(stmt)
            new_id = rs.scalar_one_or_none()
            await session.commit()
            return int(new_id) if new_id is not None else None
        except SQLAlchemyError as e:
            log.warning("basket.create.fail", error=str(e))
            await session.rollback()
            return None


async def list_baskets(user_id: UUID | None = None) -> list[BasketSummary]:
    """列篮子(BD-070)。user_id 过滤,None 返全部(开发期用)。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl_b = Symbol.__table__.metadata.tables["basket"]
            tbl_m = Symbol.__table__.metadata.tables["basket_member"]
            sql = (
                select(
                    tbl_b.c.id,
                    tbl_b.c.user_id,
                    tbl_b.c.name,
                    tbl_b.c.description,
                    tbl_b.c.created_at,
                    tbl_b.c.updated_at,
                )
            )
            if user_id is not None:
                sql = sql.where(tbl_b.c.user_id == user_id)
            sql = sql.order_by(tbl_b.c.id.desc())
            rs = await session.execute(sql)
            baskets = []
            for r in rs.all():
                bid = r[0]
                cnt_sql = select(tbl_m.c.id).where(tbl_m.c.basket_id == bid)
                cnt = len((await session.execute(cnt_sql)).all())
                baskets.append(
                    BasketSummary(
                        id=int(bid),
                        user_id=r[1],
                        name=r[2] or "",
                        description=r[3],
                        member_count=cnt,
                        created_at=r[4].isoformat() if r[4] else "",
                        updated_at=r[5].isoformat() if r[5] else "",
                    )
                )
            return baskets
        except SQLAlchemyError as e:
            log.warning("basket.list.fail", error=str(e))
            return []


async def get_basket(basket_id: int) -> BasketSummary | None:
    """单篮子详情(BD-070)。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl_b = Symbol.__table__.metadata.tables["basket"]
            sql = select(
                tbl_b.c.id,
                tbl_b.c.user_id,
                tbl_b.c.name,
                tbl_b.c.description,
                tbl_b.c.created_at,
                tbl_b.c.updated_at,
            ).where(tbl_b.c.id == basket_id)
            rs = await session.execute(sql)
            r = rs.first()
            if r is None:
                return None
            tbl_m = Symbol.__table__.metadata.tables["basket_member"]
            cnt = len((await session.execute(select(tbl_m.c.id).where(tbl_m.c.basket_id == basket_id))).all())
            return BasketSummary(
                id=int(r[0]),
                user_id=r[1],
                name=r[2] or "",
                description=r[3],
                member_count=cnt,
                created_at=r[4].isoformat() if r[4] else "",
                updated_at=r[5].isoformat() if r[5] else "",
            )
        except SQLAlchemyError as e:
            log.warning("basket.get.fail", error=str(e), id=basket_id)
            return None


async def update_basket(
    basket_id: int, *, name: str | None = None, description: str | None = None
) -> bool:
    """改名 / 改描述(BD-070)。"""
    if name is None and description is None:
        return True
    async with AsyncSessionLocal() as session:
        try:
            tbl = Symbol.__table__.metadata.tables["basket"]
            values: dict = {"updated_at": "NOW()"}
            if name is not None:
                values["name"] = name
            if description is not None:
                values["description"] = description
            stmt = (
                tbl.update()
                .where(tbl.c.id == basket_id)
                .values(**values)
                .returning(tbl.c.id)
            )
            rs = await session.execute(stmt)
            new_id = rs.scalar_one_or_none()
            await session.commit()
            return new_id is not None
        except SQLAlchemyError as e:
            log.warning("basket.update.fail", error=str(e), id=basket_id)
            await session.rollback()
            return False


async def delete_basket(basket_id: int) -> bool:
    """删除篮子(级联删 member / snapshot,BD-070)。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl = Symbol.__table__.metadata.tables["basket"]
            rs = await session.execute(tbl.delete().where(tbl.c.id == basket_id).returning(tbl.c.id))
            new_id = rs.scalar_one_or_none()
            await session.commit()
            return new_id is not None
        except SQLAlchemyError as e:
            log.warning("basket.delete.fail", error=str(e), id=basket_id)
            await session.rollback()
            return False


async def add_members(basket_id: int, tickers: Iterable[str]) -> int:
    """增成员(BD-070)。返回新插入条数(已存在自动跳过)。"""
    rows = []
    async with AsyncSessionLocal() as session:
        # 校验 ticker 在 symbol_master 中
        sym = Symbol.__table__
        for t in tickers:
            t_up = t.strip().upper()
            if not t_up:
                continue
            exists = (
                await session.execute(select(sym.c.ticker).where(sym.c.ticker == t_up).limit(1))
            ).first()
            if exists is None:
                log.info("basket.add_members.skip_unknown", ticker=t_up)
                continue
            rows.append({"basket_id": basket_id, "symbol": t_up})
        if not rows:
            return 0
        try:
            tbl = Symbol.__table__.metadata.tables["basket_member"]
            stmt = (
                pg_insert(tbl)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["basket_id", "symbol"])
                .returning(tbl.c.id)
            )
            rs = await session.execute(stmt)
            inserted = len(rs.all())
            await session.commit()
            return inserted
        except SQLAlchemyError as e:
            log.warning("basket.add_members.fail", error=str(e), id=basket_id)
            await session.rollback()
            return 0


async def remove_member(basket_id: int, ticker: str) -> bool:
    """删单个成员(BD-070)。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl = Symbol.__table__.metadata.tables["basket_member"]
            rs = await session.execute(
                tbl.delete()
                .where(tbl.c.basket_id == basket_id)
                .where(tbl.c.symbol == ticker.upper())
                .returning(tbl.c.id)
            )
            new_id = rs.scalar_one_or_none()
            await session.commit()
            return new_id is not None
        except SQLAlchemyError as e:
            log.warning("basket.remove_member.fail", error=str(e), id=basket_id, ticker=ticker)
            await session.rollback()
            return False


async def list_members(basket_id: int) -> list[dict]:
    """列成员(BD-070)。"""
    async with AsyncSessionLocal() as session:
        try:
            tbl = Symbol.__table__.metadata.tables["basket_member"]
            sql = (
                select(tbl.c.symbol, tbl.c.added_at)
                .where(tbl.c.basket_id == basket_id)
                .order_by(tbl.c.added_at.asc())
            )
            rs = await session.execute(sql)
            return [
                {"ticker": r[0], "added_at": r[1].isoformat() if r[1] else ""}
                for r in rs.all()
            ]
        except SQLAlchemyError as e:
            log.warning("basket.list_members.fail", error=str(e), id=basket_id)
            return []


# ---- 分布(BD-071) ----


async def _read_member_scores(
    session: AsyncSession, basket_id: int, days: int
) -> tuple[list[str], list[list[float]], date | None]:
    """读该篮子成员近 N 日 threat_score 序列。返回 (tickers, [每 ticker 分序列], 最新 trade_date)。"""
    tbl_m = Symbol.__table__.metadata.tables["basket_member"]
    tbl_t = Symbol.__table__.metadata.tables["threat_score_daily"]
    cutoff = date.today() - timedelta(days=int(days * 1.6) + 5)
    # 成员列表
    mem_rs = await session.execute(
        select(tbl_m.c.symbol).where(tbl_m.c.basket_id == basket_id)
    )
    tickers = [r[0] for r in mem_rs.all()]
    if not tickers:
        return [], [], None
    # 各 ticker 近 N 日
    score_sql = (
        select(tbl_t.c.symbol, tbl_t.c.trade_date, tbl_t.c.total)
        .where(tbl_t.c.symbol.in_(tickers))
        .where(tbl_t.c.trade_date >= cutoff)
        .order_by(tbl_t.c.symbol.asc(), tbl_t.c.trade_date.asc())
    )
    rs = await session.execute(score_sql)
    by_ticker: dict[str, list[float]] = {t: [] for t in tickers}
    latest_date: date | None = None
    for r in rs.all():
        sym, td, total = r[0], r[1], r[2]
        if total is None:
            continue
        by_ticker.setdefault(sym, []).append(float(total))
        if latest_date is None or td > latest_date:
            latest_date = td
    series = [by_ticker[t] for t in tickers]
    return tickers, series, latest_date


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def _per_ticker_summary(tickers: list[str], series: list[list[float]]) -> list[dict]:
    out: list[dict] = []
    for t, vals in zip(tickers, series):
        if not vals:
            out.append({"ticker": t, "latest": None, "mean": 0.0, "max": 0.0, "lifecycle": "init"})
            continue
        out.append(
            {
                "ticker": t,
                "latest": vals[-1],
                "mean": round(sum(vals) / len(vals), 2),
                "max": round(max(vals), 2),
                "lifecycle": "red" if vals[-1] >= 70 else ("yellow" if vals[-1] >= 50 else "green"),
            }
        )
    return out


async def compute_basket_distribution(basket_id: int, days: int = 30) -> BasketDistribution | None:
    """算篮子分布 + 落库 basket_snapshot(BD-071)。"""
    async with AsyncSessionLocal() as session:
        try:
            tickers, series, latest_date = await _read_member_scores(session, basket_id, days)
            if not tickers:
                return None
            all_vals: list[float] = []
            day_counts: list[int] = []
            for vals in series:
                if vals:
                    all_vals.extend(vals)
                    day_counts.append(len(vals))
            if not all_vals:
                return None
            td = latest_date or date.today()
            dist = BasketDistribution(
                basket_id=basket_id,
                trade_date=td,
                ticker_count=len(tickers),
                day_count=int(sum(day_counts) / max(1, len(day_counts))) if day_counts else 0,
                mean=round(statistics.fmean(all_vals), 2),
                p25=round(_percentile(all_vals, 25), 2),
                p50=round(_percentile(all_vals, 50), 2),
                p75=round(_percentile(all_vals, 75), 2),
                p90=round(_percentile(all_vals, 90), 2),
                p99=round(_percentile(all_vals, 99), 2),
                min_score=round(min(all_vals), 2),
                max_score=round(max(all_vals), 2),
                by_ticker=_per_ticker_summary(tickers, series),
            )
            # 落库 basket_snapshot
            snap_tbl = Symbol.__table__.metadata.tables["basket_snapshot"]
            snap_row = {
                "basket_id": basket_id,
                "trade_date": td,
                "score_distribution": {
                    "ticker_count": dist.ticker_count,
                    "day_count": dist.day_count,
                    "mean": dist.mean,
                    "p25": dist.p25,
                    "p50": dist.p50,
                    "p75": dist.p75,
                    "p90": dist.p90,
                    "p99": dist.p99,
                    "min": dist.min_score,
                    "max": dist.max_score,
                    "by_ticker": dist.by_ticker,
                },
            }
            stmt = (
                pg_insert(snap_tbl)
                .values(snap_row)
                .on_conflict_do_update(
                    index_elements=["basket_id", "trade_date"],
                    set_={"score_distribution": snap_row["score_distribution"]},
                )
            )
            await session.execute(stmt)
            await session.commit()
            return dist
        except SQLAlchemyError as e:
            log.warning("basket.distribution.fail", error=str(e), id=basket_id)
            await session.rollback()
            return None
