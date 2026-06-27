"""V1.6.0 数据入库前校验层(Validation Layer)。

在 ETL 入库前自动识别极端离群值,防止脏数据污染 Z-Score 计算。

校验策略:
- 不直接丢弃数据,而是标记异常 + log.warning
- 严重异常 → 标记待人工审核(mark_pending)
- 轻度异常 → 允许入库但附加 warning

四类校验:
1. validate_daily_price(): 日涨跌幅 > ±50%(排除停牌/拆股/退市)
2. validate_short_volume(): 单日做空量 > 历史 99 分位数 × 3
3. validate_form4(): 单笔交易金额 > 该股过去 1 年最大单笔 × 5
4. validate_options_chain(): PCR > 10 或 < 0.1(数据质量异常)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationWarning:
    """单条校验警告。"""

    field: str
    symbol: str
    message: str
    severity: str = "warning"  # 'warning' | 'critical'
    value: float | str | None = None


@dataclass(slots=True)
class ValidationResult:
    """校验结果汇总。"""

    is_valid: bool = True
    outlier_count: int = 0
    warnings: list[ValidationWarning] = field(default_factory=list)
    checked_count: int = 0

    def add_warning(
        self,
        warning_field: str,
        symbol: str,
        message: str,
        *,
        severity: str = "warning",
        value: float | str | None = None,
    ) -> None:
        self.warnings.append(
            ValidationWarning(
                field=warning_field,
                symbol=symbol,
                message=message,
                severity=severity,
                value=value,
            )
        )
        self.outlier_count += 1
        if severity == "critical":
            self.is_valid = False

    def summary(self) -> str:
        status = "PASS" if self.is_valid else "FAIL"
        return f"[{status}] checked={self.checked_count} outliers={self.outlier_count} warnings={len(self.warnings)}"


# ---- 1) 日 K 线校验 ----


def validate_daily_price(
    bars: list,
    *,
    max_daily_change_pct: float = 0.50,
    min_volume: int = 1,
) -> ValidationResult:
    """校验日 K 线数据质量。

    检测:
    - 日涨跌幅 > ±50%(可能停牌/拆股/退市/数据错误)
    - 成交量 = 0(停牌日)
    - OHLC 逻辑错误(high < low 等)

    Args:
        bars: DailyBar 列表(按 trade_date 升序)
        max_daily_change_pct: 最大日涨跌幅阈值(默认 50%)
        min_volume: 最小成交量(默认 1,过滤停牌)
    """
    result = ValidationResult(checked_count=len(bars))
    if len(bars) < 2:
        return result

    for i, bar in enumerate(bars):
        # OHLC 逻辑校验
        if bar.high < bar.low:
            result.add_warning(
                "ohlc_logic",
                bar.symbol,
                f"high({bar.high}) < low({bar.low}) on {bar.trade_date}",
                severity="critical",
                value=f"H={bar.high} L={bar.low}",
            )
            continue

        # 成交量校验
        if bar.volume < min_volume:
            result.add_warning(
                "zero_volume",
                bar.symbol,
                f"volume={bar.volume} on {bar.trade_date} (可能停牌)",
                severity="warning",
                value=bar.volume,
            )

        # 日涨跌幅校验(需要前一日数据)
        if i > 0:
            prev_close = bars[i - 1].close
            if prev_close > 0:
                change_pct = abs(bar.close - prev_close) / prev_close
                if change_pct > max_daily_change_pct:
                    result.add_warning(
                        "extreme_change",
                        bar.symbol,
                        f"日涨跌幅 {change_pct:.1%} 超过阈值 {max_daily_change_pct:.0%} on {bar.trade_date}",
                        severity="warning",
                        value=round(change_pct, 4),
                    )

    if result.warnings:
        log.warning(
            "validation.daily_price",
            symbol=bars[0].symbol if bars else "?",
            outliers=result.outlier_count,
            critical=sum(1 for w in result.warnings if w.severity == "critical"),
        )
    return result


# ---- 2) 做空量校验 ----


def validate_short_volume(
    rows: list,
    *,
    historical_p99: dict[str, float] | None = None,
    outlier_multiplier: float = 3.0,
) -> ValidationResult:
    """校验 FINRA 做空量数据。

    检测:
    - 单日做空量 > 历史 99 分位数 × outlier_multiplier → 标记异常
    - short_volume + non_short_volume = 0(无效数据)
    - short_volume > total_volume(逻辑错误)

    Args:
        rows: ShortVolumeRow 列表
        historical_p99: {symbol: p99_value} 历史 99 分位数;None 则跳过统计校验
        outlier_multiplier: 离群倍数(默认 3x)
    """
    result = ValidationResult(checked_count=len(rows))

    for row in rows:
        total = row.short_volume + row.non_short_volume

        # 逻辑校验:总量为 0
        if total <= 0:
            result.add_warning(
                "zero_total",
                row.symbol,
                f"short_volume + non_short_volume = 0 on {row.trade_date}",
                severity="critical",
            )
            continue

        # 逻辑校验:做空 > 总量(不可能)
        if row.short_volume > total:
            result.add_warning(
                "short_gt_total",
                row.symbol,
                f"short_volume({row.short_volume}) > total({total}) on {row.trade_date}",
                severity="critical",
            )
            continue

        # 统计校验:超过历史 99 分位数 × N
        if historical_p99 and row.symbol in historical_p99:
            p99 = historical_p99[row.symbol]
            threshold = p99 * outlier_multiplier
            if threshold > 0 and row.short_volume > threshold:
                result.add_warning(
                    "statistical_outlier",
                    row.symbol,
                    f"做空量 {row.short_volume} > 历史P99×{outlier_multiplier}={threshold:.0f} on {row.trade_date}",
                    severity="warning",
                    value=row.short_volume,
                )

    if result.warnings:
        log.warning(
            "validation.short_volume",
            outliers=result.outlier_count,
            critical=sum(1 for w in result.warnings if w.severity == "critical"),
        )
    return result


# ---- 3) SEC Form 4 校验 ----


def validate_form4(
    rows: list,
    *,
    historical_max_txn: dict[str, float] | None = None,
    outlier_multiplier: float = 5.0,
) -> ValidationResult:
    """校验 SEC Form 4 内部人交易数据。

    检测:
    - 单笔交易金额 > 该股过去 1 年最大单笔 × outlier_multiplier
    - qty <= 0 或 price < 0(无效数据)
    - txn_date 在未来(数据错误)

    Args:
        rows: Form4Row 列表
        historical_max_txn: {symbol: max_transaction_value} 历史最大单笔;None 则跳过
        outlier_multiplier: 离群倍数(默认 5x)
    """
    result = ValidationResult(checked_count=len(rows))
    today = date.today()

    for row in rows:
        # 基础校验
        if row.qty is not None and row.qty <= 0:
            result.add_warning(
                "invalid_qty",
                row.symbol,
                f"qty={row.qty} <= 0 on {row.txn_date}",
                severity="critical",
            )
            continue

        if row.price is not None and row.price < 0:
            result.add_warning(
                "negative_price",
                row.symbol,
                f"price={row.price} < 0 on {row.txn_date}",
                severity="critical",
            )
            continue

        # 日期校验
        if row.txn_date > today:
            result.add_warning(
                "future_date",
                row.symbol,
                f"txn_date={row.txn_date} 在未来",
                severity="warning",
            )

        # 统计校验:单笔金额异常大
        if (
            historical_max_txn
            and row.symbol in historical_max_txn
            and row.qty is not None
            and row.price is not None
        ):
            txn_value = abs(row.qty) * row.price
            max_val = historical_max_txn[row.symbol]
            threshold = max_val * outlier_multiplier
            if threshold > 0 and txn_value > threshold:
                result.add_warning(
                    "statistical_outlier",
                    row.symbol,
                    f"交易金额 ${txn_value:,.0f} > 历史Max×{outlier_multiplier}=${threshold:,.0f} on {row.txn_date}",
                    severity="warning",
                    value=txn_value,
                )

    if result.warnings:
        log.warning(
            "validation.form4",
            outliers=result.outlier_count,
            critical=sum(1 for w in result.warnings if w.severity == "critical"),
        )
    return result


# ---- 4) 期权链校验 ----


def validate_options_chain(
    contracts: list,
    *,
    pcr_min: float = 0.1,
    pcr_max: float = 10.0,
) -> ValidationResult:
    """校验期权链数据质量。

    检测:
    - PCR(Put/Call Ratio) > 10 或 < 0.1 → 数据质量异常
    - volume < 0 或 open_interest < 0(无效数据)
    - strike <= 0(无效行权价)
    - expiry 在过去(已过期合约不应出现在链中)

    Args:
        contracts: OptionContract 列表
        pcr_min: PCR 下限阈值(默认 0.1)
        pcr_max: PCR 上限阈值(默认 10.0)
    """
    result = ValidationResult(checked_count=len(contracts))
    if not contracts:
        return result

    today = date.today()
    put_vol = 0
    call_vol = 0

    for c in contracts:
        # 基础校验
        if c.volume < 0:
            result.add_warning(
                "negative_volume",
                c.underlying,
                f"volume={c.volume} < 0 for {c.contract}",
                severity="critical",
            )
            continue

        if c.open_interest < 0:
            result.add_warning(
                "negative_oi",
                c.underlying,
                f"open_interest={c.open_interest} < 0 for {c.contract}",
                severity="critical",
            )

        if c.strike <= 0:
            result.add_warning(
                "invalid_strike",
                c.underlying,
                f"strike={c.strike} <= 0 for {c.contract}",
                severity="critical",
            )

        if c.expiry < today:
            result.add_warning(
                "expired_contract",
                c.underlying,
                f"expiry={c.expiry} 已过期 for {c.contract}",
                severity="warning",
            )

        # 统计 PCR
        if c.right == "P":
            put_vol += c.volume
        elif c.right == "C":
            call_vol += c.volume

    # PCR 校验
    if call_vol > 0:
        pcr = put_vol / call_vol
        sym = contracts[0].underlying if contracts else "?"
        if pcr > pcr_max:
            result.add_warning(
                "pcr_too_high",
                sym,
                f"PCR={pcr:.2f} > {pcr_max}(数据质量异常)",
                severity="warning",
                value=round(pcr, 4),
            )
        elif pcr < pcr_min:
            result.add_warning(
                "pcr_too_low",
                sym,
                f"PCR={pcr:.2f} < {pcr_min}(数据质量异常)",
                severity="warning",
                value=round(pcr, 4),
            )

    if result.warnings:
        log.warning(
            "validation.options_chain",
            symbol=contracts[0].underlying if contracts else "?",
            outliers=result.outlier_count,
            critical=sum(1 for w in result.warnings if w.severity == "critical"),
        )
    return result


# ---- Pipeline 集成辅助 ----


def validate_batch(
    validations: list[tuple[str, ValidationResult]],
) -> dict[str, ValidationResult]:
    """批量执行校验并返回结果。

    Args:
        validations: [(stage_name, result), ...]

    Returns:
        {stage_name: ValidationResult}
    """
    results = {}
    for name, vr in validations:
        results[name] = vr
        if not vr.is_valid:
            log.warning(
                "validation.batch.critical",
                stage=name,
                outliers=vr.outlier_count,
            )
    return results
