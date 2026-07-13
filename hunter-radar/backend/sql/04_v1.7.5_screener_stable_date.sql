-- V1.7.5 Screener 物化视图 — 使用 trade_date with ≥5 symbols
-- 修复:当前 MAX(trade_date) 可能只包含 1-2 个标的(刚 warmup 完当天),
-- 导致 screener 只显示 1 条记录。改用最新"≥5 个 symbols 有数据"的日期。

DROP MATERIALIZED VIEW IF EXISTS mv_screener_top100 CASCADE;

CREATE MATERIALIZED VIEW mv_screener_top100 AS
WITH latest_stable_date AS (
    SELECT trade_date
    FROM threat_score_daily
    GROUP BY trade_date
    HAVING COUNT(DISTINCT symbol) >= 5
    ORDER BY trade_date DESC
    LIMIT 1
)
SELECT
    ts.trade_date,
    ts.symbol,
    sm.name,
    ts.symbol_type,
    ts.total AS threat_score,
    ts.signal_lifecycle,
    ts.module_options,
    ts.module_short,
    ts.module_divergence,
    ts.module_insider,
    ts.weights,
    ts.nl_summary,
    RANK() OVER (
        PARTITION BY ts.symbol_type
        ORDER BY ts.total DESC
    ) AS rank_in_type
FROM threat_score_daily ts
JOIN symbol_master sm ON sm.ticker = ts.symbol
WHERE ts.trade_date = (SELECT trade_date FROM latest_stable_date)
ORDER BY ts.total DESC
LIMIT 100;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_screener_top100
    ON mv_screener_top100 (trade_date, symbol);
