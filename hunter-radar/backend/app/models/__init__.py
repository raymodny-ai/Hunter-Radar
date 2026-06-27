"""ORM 模型(全部对应 sql/00_init.sql)。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Symbol(Base):
    __tablename__ = "symbol_master"

    ticker: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_universe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warmup_started_at: Mapped[date | None] = mapped_column(Date)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShortVolume(Base):
    __tablename__ = "short_volume"
    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", "source", name="uq_short_volume"),
        Index("idx_short_volume_date_sym", "trade_date", "symbol"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, ForeignKey("symbol_master.ticker"), nullable=False)
    short_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    non_short_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    venue: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="finra")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ThreatScoreDaily(Base):
    __tablename__ = "threat_score_daily"
    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", name="uq_threat"),
        CheckConstraint(
            "signal_lifecycle IN ('init','red','yellow','gray','green')", name="ck_lifecycle"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, ForeignKey("symbol_master.ticker"), nullable=False)
    symbol_type: Mapped[str] = mapped_column(Text, nullable=False)
    module_options: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    module_short: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    module_divergence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    module_insider: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_raw: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ema_halflife: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_lifecycle: Mapped[str] = mapped_column(Text, nullable=False, default="init")
    nl_summary: Mapped[str | None] = mapped_column(Text)
    regime: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UltimateAlert(Base):
    __tablename__ = "ultimate_alert"
    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", name="uq_ultimate_alert"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(Text, ForeignKey("symbol_master.ticker"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    threat_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    modules_active: Mapped[list] = mapped_column(JSONB, nullable=False)
    regime: Mapped[str] = mapped_column(Text, nullable=False)
    consecutive_days: Mapped[int] = mapped_column(Integer, nullable=False)
    debounce_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ema_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


# ---- 其他 core Table 注册(用于 metadata.tables 查找) ----
_SHARED_META = Base.metadata
# 这些表只在 sql/00_init.sql 中定义,但被 API/ETL 用 metadata.tables 引用。
# 定义足够的列使 metadata.tables[name].c.colname 可访问。
# 注意:extend_existing 必须是关键字参数,放在所有 Column 位置参数后
for _tname, _tcols in [
    ("daily_price", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("open", Numeric), Column("high", Numeric), Column("low", Numeric),
        Column("close", Numeric), Column("adj_close", Numeric), Column("volume", BigInteger),
        Column("source", Text)]),
    ("short_volume", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("short_volume", BigInteger), Column("non_short_volume", BigInteger),
        Column("venue", Text), Column("source", Text)]),
    ("short_ratio_daily", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("short_ratio", Numeric), Column("z_score_60d", Numeric),
        Column("ats_short_pct", Numeric), Column("computed_at", DateTime)]),
    ("divergence_window", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("price_slope_10d", Numeric), Column("short_slope_10d", Numeric),
        Column("p_price", Numeric), Column("p_short", Numeric),
        Column("divergence_state", Text), Column("computed_at", DateTime)]),
    ("option_anomaly", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("contract", Text), Column("dte", Integer), Column("oi_increase_pct", Numeric),
        Column("volume_oi_ratio", Numeric), Column("notional", Numeric),
        Column("is_top10_notional", Boolean), Column("oi_5d_series", ARRAY(String)),
        Column("has_known_catalyst", Boolean), Column("catalyst_note", Text),
        Column("computed_at", DateTime)]),
    ("daily_screener", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("threat_score", Numeric), Column("breakdown", JSONB), Column("rank", Integer)]),
    ("basket", [Column("id", BigInteger), Column("user_id", UUID), Column("name", Text),
        Column("description", Text), Column("created_at", DateTime), Column("updated_at", DateTime)]),
    ("basket_member", [Column("id", BigInteger), Column("basket_id", BigInteger), Column("symbol", Text),
        Column("added_at", DateTime)]),
    ("basket_snapshot", [Column("id", BigInteger)]),
    ("options_chain", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("contract", Text), Column("underlying", Text), Column("expiry", Date),
        Column("strike", Numeric), Column("right", CHAR(1)),
        Column("last_price", Numeric), Column("bid", Numeric), Column("ask", Numeric),
        Column("volume", BigInteger), Column("open_interest", BigInteger),
        Column("implied_vol", Numeric), Column("in_the_money", Boolean),
        Column("source", Text), Column("fetched_at", DateTime)]),
    ("ats_short", [Column("id", BigInteger), Column("trade_date", Date), Column("symbol", Text),
        Column("ats_short_volume", BigInteger), Column("venue_pool", Text),
        Column("source", Text), Column("fetched_at", DateTime)]),
    ("form4_event", [Column("id", BigInteger), Column("symbol", Text),
        Column("insider_name", Text), Column("insider_role", Text),
        Column("txn_date", Date), Column("filed_at", Date), Column("direction", Text),
        Column("qty", BigInteger), Column("price", Numeric), Column("form_url", Text)]),
    ("buyback_event", [Column("id", BigInteger), Column("symbol", Text),
        Column("form_type", Text), Column("announced_at", Date),
        Column("amount_usd", BigInteger), Column("execution_window", Text),
        Column("source_url", Text)]),
    ("data_ingestion_status", [Column("id", BigInteger), Column("trade_date", Date),
        Column("symbol", Text), Column("data_source", Text), Column("status", Text),
        Column("last_attempt_at", DateTime), Column("detail", JSONB)]),
    ("option_pcr_daily", [Column("id", BigInteger), Column("trade_date", Date),
        Column("symbol", Text), Column("total_put_volume", BigInteger),
        Column("total_call_volume", BigInteger), Column("pcr", Numeric),
        Column("pcr_z_score", Numeric), Column("pcr_extreme", Boolean),
        Column("otm_assassin_count", Integer), Column("gamma_clusters", JSONB),
        Column("signal_strength", Text), Column("signal_modules", JSONB),
        Column("computed_at", DateTime)]),
]:
    if _tname not in _SHARED_META.tables:
        Table(_tname, _SHARED_META, *_tcols, extend_existing=True)
