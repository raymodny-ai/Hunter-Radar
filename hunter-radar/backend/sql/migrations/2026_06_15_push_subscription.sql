-- §6.2 push_subscription 表(BD-074 m5t4)
-- 创建日期:2026-06-15
-- 适用:Hunter Radar V1.4
-- 沙箱无 alembic 时直接 psql 跑这一份;生产环境请用 alembic 套同一份 DDL

CREATE TABLE IF NOT EXISTS push_subscription (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID         NOT NULL,
    endpoint      TEXT         NOT NULL UNIQUE,
    p256dh        TEXT         NOT NULL,
    auth          TEXT         NOT NULL,
    user_agent    TEXT,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- 列某 user 的 active 订阅的快速索引
CREATE INDEX IF NOT EXISTS idx_push_sub_user_active
    ON push_subscription (user_id)
    WHERE is_active = TRUE;

-- 软删扫描(运维清理脚本用)
CREATE INDEX IF NOT EXISTS idx_push_sub_inactive
    ON push_subscription (updated_at)
    WHERE is_active = FALSE;

COMMENT ON TABLE  push_subscription IS 'BD-074 m5t4:用户 Web Push 订阅(endpoint 唯一)';
COMMENT ON COLUMN push_subscription.endpoint   IS 'PushSubscription.endpoint(浏览器给的服务端 URL)';
COMMENT ON COLUMN push_subscription.p256dh     IS 'ECDH P-256 公钥(base64url)';
COMMENT ON COLUMN push_subscription.auth       IS '认证密钥(base64url,16 字节)';
COMMENT ON COLUMN push_subscription.user_agent IS '订阅时 UA,便于客户端多端识别';
COMMENT ON COLUMN push_subscription.is_active  IS 'FALSE 时视为软删(410 Gone 后由 API 层标记)';
