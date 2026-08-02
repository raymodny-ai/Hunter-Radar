-- § threat_score_daily 可观测性列扩展 (IMPL 4.1 / DB-02 / DB-03)
-- 创建日期:2026-08-02
-- 适用:Hunter Radar V1.6.2+
-- 背景:2.6 的 explain API 是在响应时从现有列动态派生 confidence/active_modules/module_scores。
--       本迁移把评分分解落库,形成完整可审计闭环:
--         - module_scores_json : 4 模块归一化分 dict {options, short, divergence, insider}
--         - module_quality     : 每模块数据质量标记 {options: complete|degraded|stale, ...}
--         - confidence         : high(4 模块全活) / medium(<4) / insufficient_data(<MIN_ACTIVE)
--         - active_modules     : 参与打分的活动模块数
--   历史行保持 NULL,API 侧 fallback 到模块推导(与 data_quality NULL 处理一致)。
-- 幂等:ADD COLUMN IF NOT EXISTS

ALTER TABLE threat_score_daily
    ADD COLUMN IF NOT EXISTS module_scores_json JSONB,
    ADD COLUMN IF NOT EXISTS module_quality JSONB,
    ADD COLUMN IF NOT EXISTS confidence VARCHAR(20) DEFAULT 'high',
    ADD COLUMN IF NOT EXISTS active_modules SMALLINT DEFAULT 4;
