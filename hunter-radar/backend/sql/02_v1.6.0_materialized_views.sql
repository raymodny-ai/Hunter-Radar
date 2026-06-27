-- V1.6.0 Screener 物化视图优化
-- 用于加速 Top N 榜单查询,避免每次请求都扫描 threat_score_daily 全表。

-- §1: 创建物化视图 mv_screener_top100
-- 预计算最新交易日的 Top 100 危险标的(含模块子评分 + 信号灯)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_screener_top100 AS
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
        PARTITION BY ts.trade_date, ts.symbol_type
        ORDER BY ts.total DESC
    ) AS rank_in_type
FROM threat_score_daily ts
JOIN symbol_master sm ON sm.ticker = ts.symbol
WHERE ts.trade_date = (
    SELECT MAX(trade_date) FROM threat_score_daily
)
ORDER BY ts.total DESC
LIMIT 100;

-- §2: 唯一索引(支持 CONCURRENTLY 刷新)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_screener_top100
    ON mv_screener_top100 (trade_date, symbol);

-- §3: 刷新物化视图(由 pipeline 尾部触发)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_screener_top100;

-- §4: 查询示例(API 层使用)
-- SELECT * FROM mv_screener_top100
-- WHERE symbol_type = 'stock'
-- ORDER BY threat_score DESC
-- LIMIT 20;

-- §5: 清理旧视图(如存在)
-- DROP MATERIALIZED VIEW IF EXISTS mv_screener_top100 CASCADE;
