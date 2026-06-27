-- V1.5.9 Migration: ATS Fallback + Options Anomaly V2 + Dynamic Weights
-- 执行: psql -U hunter -d hunter_radar -f sql/01_v1.5.9_options_ats.sql
-- 回滚: 见末尾 ROLLBACK 注释

BEGIN;

-- =============================================================
-- 1. ATS 暗池做空: data_ingestion_status 新增 ats_fallback source
--    (ats_short 表已存在, fallback 复用同一表, source='ats_fallback')
-- =============================================================

-- data_ingestion_status 的 CHECK 约束需要更新以允许 'ats_fallback' / 'options_pcr' / 'options_gamma'
-- 注意: 00_init.sql 没有 CHECK 约束在 data_source 上, 所以无需迁移。
-- 仅做文档记录。
COMMENT ON TABLE data_ingestion_status IS
    '数据状态灯(BD-011)。V1.5.9 新增 data_source: ats_fallback / options_pcr / options_gamma';

-- =============================================================
-- 2. option_anomaly 表: 新增 V1.5.9 增强列
-- =============================================================
ALTER TABLE option_anomaly
    ADD COLUMN IF NOT EXISTS signal_strength TEXT NOT NULL DEFAULT 'NORMAL'
        CHECK (signal_strength IN ('HIGH', 'NORMAL', 'LOW'));

ALTER TABLE option_anomaly
    ADD COLUMN IF NOT EXISTS otm_assassin BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE option_anomaly
    ADD COLUMN IF NOT EXISTS gamma_cluster_ratio NUMERIC(8, 4) NOT NULL DEFAULT 0;

ALTER TABLE option_anomaly
    ADD COLUMN IF NOT EXISTS pcr_z_score NUMERIC(8, 4);

-- 索引: 按 signal_strength 快速查询 HIGH 信号
CREATE INDEX IF NOT EXISTS idx_option_anomaly_signal
    ON option_anomaly (trade_date DESC, signal_strength)
    WHERE signal_strength = 'HIGH';

-- =============================================================
-- 3. threat_score_daily: 记录实际使用的权重(JSONB 已有)
--    V1.5.9 动态重分配的权重自动存入 weights 列
-- =============================================================
-- weights 列已存在为 JSONB, 无需改动。
-- 仅添加索引方便按信号生命周期查询。
CREATE INDEX IF NOT EXISTS idx_threat_lifecycle
    ON threat_score_daily (trade_date DESC, signal_lifecycle);

-- =============================================================
-- 4. 新增: option_pcr_daily 表(PCR + Gamma 聚集聚合结果)
-- =============================================================
CREATE TABLE IF NOT EXISTS option_pcr_daily (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    total_put_volume  BIGINT NOT NULL DEFAULT 0,
    total_call_volume BIGINT NOT NULL DEFAULT 0,
    pcr               NUMERIC(10, 4) NOT NULL,
    pcr_z_score       NUMERIC(8, 4),
    pcr_extreme       BOOLEAN NOT NULL DEFAULT FALSE,
    otm_assassin_count INT NOT NULL DEFAULT 0,
    gamma_clusters    JSONB NOT NULL DEFAULT '[]'::jsonb,
    signal_strength   TEXT NOT NULL DEFAULT 'NORMAL'
                      CHECK (signal_strength IN ('HIGH', 'NORMAL', 'LOW')),
    signal_modules    JSONB NOT NULL DEFAULT '[]'::jsonb,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_option_pcr_date_signal
    ON option_pcr_daily (trade_date DESC, signal_strength)
    WHERE signal_strength = 'HIGH';
CREATE INDEX IF NOT EXISTS idx_option_pcr_sym_date
    ON option_pcr_daily (symbol, trade_date DESC);

COMMIT;

-- =============================================================
-- ROLLBACK(如需回滚):
-- DROP TABLE IF EXISTS option_pcr_daily;
-- ALTER TABLE option_anomaly DROP COLUMN IF EXISTS signal_strength;
-- ALTER TABLE option_anomaly DROP COLUMN IF EXISTS otm_assassin;
-- ALTER TABLE option_anomaly DROP COLUMN IF EXISTS gamma_cluster_ratio;
-- ALTER TABLE option_anomaly DROP COLUMN IF EXISTS pcr_z_score;
-- DROP INDEX IF EXISTS idx_option_anomaly_signal;
-- DROP INDEX IF EXISTS idx_threat_lifecycle;
-- =============================================================
