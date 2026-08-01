-- § threat_score_daily.data_quality 列 (IMPL-DQ-002 断裂点 3)
-- 创建日期:2026-08-01
-- 适用:Hunter Radar V1.6.1+
-- 背景:services.threat_score 已动态计算 data_quality(complete/degraded/stale),
--       但 load_threat_score 只打日志不落库,导致 DTO 字段形同虚设。
--       本迁移把列加进 threat_score_daily,load 时由 compute payload 写入,
--       API 优先读持久化值,历史 NULL 行 fallback 到模块推导。
-- 幂等:ADD COLUMN IF NOT EXISTS

ALTER TABLE threat_score_daily
    ADD COLUMN IF NOT EXISTS data_quality TEXT;
