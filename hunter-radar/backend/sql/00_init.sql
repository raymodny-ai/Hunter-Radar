-- Hunter Radar V1.4 — PostgreSQL Schema Init
-- 对应 PRD §2.2 数据源 + §3 五大核心功能模块
-- 启动方式: psql -U hunter -d hunter_radar -f sql/00_init.sql
-- 任何变更请生成 alembic migration,勿直接改本文件。

BEGIN;

-- =============================================================
-- 通用扩展
-- =============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- 复合索引

-- =============================================================
-- §2.2.0 标的元信息(symbol_master)
-- =============================================================
CREATE TABLE IF NOT EXISTS symbol_master (
    ticker           TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    type             TEXT NOT NULL CHECK (type IN ('stock', 'etf', 'index', 'crypto', 'adr')),
    exchange         TEXT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    is_universe      BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否纳入 Screener 全市场
    warmup_started_at DATE,                          -- 冷启动数据开始积累日
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_symbol_type_active
    ON symbol_master (type, is_active);

-- =============================================================
-- §2.2.1 FINRA 全监管做空(short_volume)
-- 字段:date, symbol, short_volume, non_short_volume, total_volume, venue
-- =============================================================
CREATE TABLE IF NOT EXISTS short_volume (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    short_volume      BIGINT NOT NULL,
    non_short_volume  BIGINT NOT NULL,
    total_volume      BIGINT GENERATED ALWAYS AS (short_volume + non_short_volume) STORED,
    venue             TEXT,                       -- 单一 FINRA 报告不含 venue;预留
    source            TEXT NOT NULL DEFAULT 'finra',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol, source)
);
CREATE INDEX IF NOT EXISTS idx_short_volume_date_sym
    ON short_volume (trade_date DESC, symbol);

-- §2.2.1 ATS 暗池做空(从 FINRA 分离)
CREATE TABLE IF NOT EXISTS ats_short (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    ats_short_volume  BIGINT NOT NULL,
    venue_pool        TEXT NOT NULL,              -- ATS 名称;FINRA 提供的暗池清单
    source            TEXT NOT NULL DEFAULT 'finra',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol, venue_pool, source)
);
CREATE INDEX IF NOT EXISTS idx_ats_short_date_sym
    ON ats_short (trade_date DESC, symbol);

-- §3.2 计算产物
CREATE TABLE IF NOT EXISTS short_ratio_daily (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    short_ratio       NUMERIC(8, 6) NOT NULL,     -- short / total
    z_score_60d       NUMERIC(8, 4),              -- 60 日滚动 Z-Score(BD-031)
    ats_short_pct     NUMERIC(8, 6),              -- 暗池占比
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_short_ratio_daily_sym
    ON short_ratio_daily (symbol, trade_date DESC);

-- =============================================================
-- §2.2.2 SEC EDGAR
-- =============================================================
CREATE TABLE IF NOT EXISTS form4_event (
    id                BIGSERIAL PRIMARY KEY,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    insider_name      TEXT NOT NULL,
    insider_role      TEXT NOT NULL,               -- 'CEO','CFO','Director','10%_holder','Officer'
    txn_date          DATE NOT NULL,
    filed_at          DATE NOT NULL,
    direction         TEXT NOT NULL CHECK (direction IN ('buy','sell','grant','exercise')),
    qty               BIGINT NOT NULL,
    price             NUMERIC(14, 4),
    classification    TEXT,                        -- 'c-level' / 'director' / '10%_holder' (BD-050)
    form_url          TEXT NOT NULL,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, insider_name, txn_date, direction, qty, price)
);
CREATE INDEX IF NOT EXISTS idx_form4_sym_date
    ON form4_event (symbol, txn_date DESC);

CREATE TABLE IF NOT EXISTS buyback_event (
    id                BIGSERIAL PRIMARY KEY,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    form_type         TEXT NOT NULL,               -- '8-K','10-Q','10-K'
    announced_at      DATE NOT NULL,
    amount_usd        BIGINT,
    pct_of_float      NUMERIC(8, 4),
    execution_window  TEXT,
    source_url        TEXT NOT NULL,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, form_type, announced_at, source_url)
);

-- =============================================================
-- §2.2.3 Yahoo Finance
-- =============================================================
CREATE TABLE IF NOT EXISTS daily_price (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    open              NUMERIC(14, 4),
    high              NUMERIC(14, 4),
    low               NUMERIC(14, 4),
    close             NUMERIC(14, 4) NOT NULL,
    adj_close         NUMERIC(14, 4),
    volume            BIGINT,
    source            TEXT NOT NULL DEFAULT 'yfinance',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol, source)
);
CREATE INDEX IF NOT EXISTS idx_daily_price_sym_date
    ON daily_price (symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS options_chain (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    contract          TEXT NOT NULL,               -- O:AAPL240621C00200000
    underlying        TEXT NOT NULL,
    expiry            DATE NOT NULL,
    strike            NUMERIC(14, 4) NOT NULL,
    right             CHAR(1) NOT NULL CHECK (right IN ('C','P')),
    last_price        NUMERIC(14, 4),
    bid               NUMERIC(14, 4),
    ask               NUMERIC(14, 4),
    volume            BIGINT,
    open_interest     BIGINT,
    implied_vol       NUMERIC(8, 4),
    in_the_money      BOOLEAN,
    source            TEXT NOT NULL DEFAULT 'yfinance',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, contract, source)
);
CREATE INDEX IF NOT EXISTS idx_options_sym_expiry
    ON options_chain (symbol, expiry);
CREATE INDEX IF NOT EXISTS idx_options_sym_date_right
    ON options_chain (symbol, trade_date DESC, right);

-- §3.1 计算产物:末日 Put 异常合约
CREATE TABLE IF NOT EXISTS option_anomaly (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    contract          TEXT NOT NULL,
    dte               INT NOT NULL,
    oi_increase_pct   NUMERIC(8, 4) NOT NULL,
    volume_oi_ratio   NUMERIC(10, 4) NOT NULL,
    notional          NUMERIC(20, 4) NOT NULL,
    is_top10_notional BOOLEAN NOT NULL DEFAULT FALSE,
    oi_5d_series      NUMERIC[] NOT NULL DEFAULT '{}',
    has_known_catalyst BOOLEAN NOT NULL DEFAULT FALSE,
    catalyst_note     TEXT,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, contract)
);
CREATE INDEX IF NOT EXISTS idx_option_anomaly_date_sym
    ON option_anomaly (trade_date DESC, symbol);

-- =============================================================
-- §2.2.4 ETF 一级市场申赎(本期返回 501,V1.5 真接入)
-- =============================================================
CREATE TABLE IF NOT EXISTS etf_primary_flow (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    creation_units    BIGINT,                       -- 申购单位
    redemption_units  BIGINT,                       -- 赎回单位
    aum_usd           NUMERIC(20, 4),
    source            TEXT,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (trade_date, symbol, source)
);

-- OQ-16 决策:折溢价率代理指标
CREATE TABLE IF NOT EXISTS etf_proxy_metrics (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    close             NUMERIC(14, 4) NOT NULL,
    inav              NUMERIC(14, 4),               -- 盘中资产净值
    premium_pct       NUMERIC(8, 4),               -- (close - inav) / inav
    volume_vs_ma20    NUMERIC(8, 4),               -- 量比
    proxy_signal      TEXT,                         -- 'creation_likely' / 'redemption_likely' / 'normal'
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_etf_proxy_date_sym
    ON etf_proxy_metrics (trade_date DESC, symbol);

-- =============================================================
-- §3.3 量价背离
-- =============================================================
CREATE TABLE IF NOT EXISTS divergence_window (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    price_slope_10d   NUMERIC(14, 6),
    short_slope_10d   NUMERIC(14, 6),
    p_price           NUMERIC(8, 6),               -- 120 日斜率分位数
    p_short           NUMERIC(8, 6),
    divergence_state  TEXT NOT NULL DEFAULT 'none'
                      CHECK (divergence_state IN ('none','rising','confirmed')),
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol)
);

-- =============================================================
-- §3.5 共振看板
-- =============================================================
CREATE TABLE IF NOT EXISTS threat_score_daily (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    symbol_type       TEXT NOT NULL,
    module_options    NUMERIC(5, 2) NOT NULL,      -- 0–100
    module_short      NUMERIC(5, 2) NOT NULL,
    module_divergence NUMERIC(5, 2) NOT NULL,
    module_insider    NUMERIC(5, 2) NOT NULL DEFAULT 0,  -- ETF = 0
    weights           JSONB NOT NULL,              -- 实际生效的权重
    total             NUMERIC(5, 2) NOT NULL,      -- EMA 平滑后的最终分
    total_raw         NUMERIC(5, 2) NOT NULL,      -- 平滑前原始分
    ema_halflife      INT NOT NULL,
    signal_lifecycle  TEXT NOT NULL DEFAULT 'init'
                      CHECK (signal_lifecycle IN ('init','red','yellow','gray','green')),
    nl_summary        TEXT,                         -- 自然语言摘要
    regime            TEXT,                         -- 'normal' | 'panic'
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (trade_date, symbol)
);
CREATE INDEX IF NOT EXISTS idx_threat_date_score
    ON threat_score_daily (trade_date DESC, total DESC);
CREATE INDEX IF NOT EXISTS idx_threat_sym_date
    ON threat_score_daily (symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS ultimate_alert (
    id                BIGSERIAL PRIMARY KEY,
    triggered_at      TIMESTAMPTZ NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    trade_date        DATE NOT NULL,
    threat_score      NUMERIC(5, 2) NOT NULL,
    modules_active    JSONB NOT NULL,              -- ['options','short','divergence']
    regime            TEXT NOT NULL,
    consecutive_days  INT NOT NULL,                 -- OQ-02:连续交易日
    debounce_passed   BOOLEAN NOT NULL DEFAULT FALSE,
    raw_score         NUMERIC(5, 2) NOT NULL,       -- EMA 前原始分
    ema_score         NUMERIC(5, 2) NOT NULL,
    UNIQUE (trade_date, symbol)
);

-- =============================================================
-- §4 自定义分析
-- =============================================================
CREATE TABLE IF NOT EXISTS basket (
    id                BIGSERIAL PRIMARY KEY,
    user_id           UUID NOT NULL,
    name              TEXT NOT NULL,
    description       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS basket_member (
    id                BIGSERIAL PRIMARY KEY,
    basket_id         BIGINT NOT NULL REFERENCES basket(id) ON DELETE CASCADE,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    added_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (basket_id, symbol)
);

CREATE TABLE IF NOT EXISTS basket_snapshot (
    id                BIGSERIAL PRIMARY KEY,
    basket_id         BIGINT NOT NULL REFERENCES basket(id) ON DELETE CASCADE,
    trade_date        DATE NOT NULL,
    avg_score         NUMERIC(5, 2),
    max_score         NUMERIC(5, 2),
    risk_concentration BOOLEAN NOT NULL DEFAULT FALSE,  -- 危险聚集:成员 ≥3 Score≥70
    member_scores     JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (basket_id, trade_date)
);

-- §4.3 Screener
CREATE TABLE IF NOT EXISTS daily_screener (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    threat_score      NUMERIC(5, 2) NOT NULL,
    breakdown         JSONB NOT NULL,
    rank              INT NOT NULL,
    UNIQUE (trade_date, symbol),
    UNIQUE (trade_date, rank)
);
CREATE INDEX IF NOT EXISTS idx_screener_date_rank
    ON daily_screener (trade_date DESC, rank);

-- §4.3 预警
CREATE TABLE IF NOT EXISTS alert_rule (
    id                BIGSERIAL PRIMARY KEY,
    user_id           UUID NOT NULL,
    name              TEXT NOT NULL,
    dsl               JSONB NOT NULL,               -- 规则 DSL:Score 阈值 + 模块条件 + 标的范围
    channels          JSONB NOT NULL,               -- ['email','webpush']
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_event (
    id                BIGSERIAL PRIMARY KEY,
    rule_id           BIGINT NOT NULL REFERENCES alert_rule(id) ON DELETE CASCADE,
    triggered_at      TIMESTAMPTZ NOT NULL,
    payload           JSONB NOT NULL,
    delivery_status   JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- =============================================================
-- §5.1 数据状态灯(BD-011)
-- =============================================================
CREATE TABLE IF NOT EXISTS data_ingestion_status (
    id                BIGSERIAL PRIMARY KEY,
    trade_date        DATE NOT NULL,
    symbol            TEXT REFERENCES symbol_master(ticker) ON DELETE CASCADE,  -- NULL = 全市场
    data_source       TEXT NOT NULL,                -- 'finra' / 'sec_form4' / 'yfinance_eod' / 'yfinance_options'
    status            TEXT NOT NULL CHECK (status IN ('ready','pending_disclosure','failed','skipped')),
    last_attempt_at   TIMESTAMPTZ,
    detail            JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (trade_date, symbol, data_source)
);
CREATE INDEX IF NOT EXISTS idx_data_ingestion_date
    ON data_ingestion_status (trade_date DESC, data_source);

-- =============================================================
-- §3.1.9 回测与校准
-- =============================================================
CREATE TABLE IF NOT EXISTS backtest_event_goldset (
    id                BIGSERIAL PRIMARY KEY,
    ticker            TEXT NOT NULL REFERENCES symbol_master(ticker) ON DELETE CASCADE,
    event_type        TEXT NOT NULL,                -- 'short_squeeze' / 'earnings_crash' / 'institutional_slaughter'
    severity          TEXT NOT NULL CHECK (severity IN ('low','medium','high','extreme')),
    t_window_start    DATE NOT NULL,
    t_window_end      DATE NOT NULL,
    source_url        TEXT NOT NULL,
    reviewer_signoff  JSONB NOT NULL DEFAULT '{}'::jsonb,  -- CR + 产品签字
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_goldset_ticker_window
    ON backtest_event_goldset (ticker, t_window_start);

CREATE TABLE IF NOT EXISTS backtest_dataset (
    id                BIGSERIAL PRIMARY KEY,
    ticker            TEXT NOT NULL,
    trade_date        DATE NOT NULL,
    payload           JSONB NOT NULL,               -- 含 FINRA / Yahoo / SEC 三源快照
    checksum          TEXT NOT NULL,
    UNIQUE (ticker, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_backtest_dataset_date
    ON backtest_dataset (trade_date DESC);

-- =============================================================
-- §6 用户/订阅
-- =============================================================
CREATE TABLE IF NOT EXISTS app_user (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             TEXT UNIQUE,
    auth_provider     TEXT NOT NULL,                 -- 'magic_link' | 'google'
    is_pro            BOOLEAN NOT NULL DEFAULT FALSE,
    pro_expires_at    TIMESTAMPTZ,
    quota_used_today  INT NOT NULL DEFAULT 0,
    quota_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    preferences       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscription_event (
    id                BIGSERIAL PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    event_type        TEXT NOT NULL,                 -- 'subscribe' / 'cancel' / 'renew'
    occurred_at       TIMESTAMPTZ NOT NULL,
    stripe_event_id   TEXT UNIQUE,
    raw               JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- =============================================================
-- 视图:数据状态灯(BD-011)
-- =============================================================
CREATE OR REPLACE VIEW v_data_ingestion_latest AS
SELECT DISTINCT ON (symbol, data_source)
    symbol, data_source, status, trade_date, last_attempt_at, detail
FROM data_ingestion_status
ORDER BY symbol, data_source, trade_date DESC, last_attempt_at DESC NULLS LAST;

COMMIT;

-- =============================================================
-- 提示
-- =============================================================
-- 种子数据(标普 500 + 主流 ETF)在 M1 阶段由 symbol_seed.py 导入。
-- 本文件不含任何种子,确保 schema 可在 CI 中反复创建。
