"""ORM 模型(全部对应 sql/00_init.sql)。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
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
