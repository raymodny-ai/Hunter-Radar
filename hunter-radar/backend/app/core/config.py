# Hunter Radar V1.4 — Backend Settings
# 复制为 .env 后按需覆盖;严禁把真实密钥提交到仓库。

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置(单一来源)。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "Hunter Radar V1.4"
    env: str = Field(default="development", description="development | staging | production")
    debug: bool = True
    log_level: str = "INFO"

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+asyncpg://hunter:hunter@localhost:5432/hunter_radar",
        description="PostgreSQL DSN(asyncpg)",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://hunter:hunter@localhost:5432/hunter_radar",
        description="Alembic 与 ETL 使用的同步 DSN",
    )
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_echo: bool = False

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_report_seconds: int = 43200  # 12h

    # ---- Security ----
    secret_key: str = "dev-only-change-me-in-prod-32-bytes-min"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 天
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---- OAuth / Magic Link ----
    magic_link_ttl_minutes: int = 15
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None

    # ---- Stripe ----
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_pro_yearly: str | None = None

    # ---- Web Push (VAPID) ----
    vapid_private_key: str | None = None
    vapid_public_key: str | None = None
    vapid_claims_email: str = "admin@hunter-radar.example"

    # ---- Data sources ----
    finra_short_url: str = "https://www.finra.org/sites/default/files/2021-03/RegSHO-data.csv"
    sec_edgar_base: str = "https://www.sec.gov"
    sec_user_agent: str = "HunterRadar/1.4 (ops@hunter-radar.example)"  # SEC 要求
    yfinance_rate_limit_per_sec: float = 1.0

    # ---- Compliance (CR-010 红线) ----
    # 在生成自然语言摘要时,严禁出现以下高危词,CI 也会拦截
    forbidden_recommendation_words: list[str] = [
        "建议买入",
        "建议卖出",
        "建仓时机",
        "清仓",
        "必涨",
        "必跌",
        "100%",
        "保证收益",
        "无风险",
    ]

    # ---- Threat Score 默认权重(校准前默认,校准后由配置中心覆盖) ----
    # 个股 30/35/20/15,ETF 35/45/20,见 PRD §3.5
    threat_weights_default: dict[str, dict[str, float]] = {
        "stock": {"options": 0.30, "short": 0.35, "divergence": 0.20, "insider": 0.15},
        "etf": {"options": 0.35, "short": 0.45, "divergence": 0.20},
    }
    threat_red_threshold: int = 70
    threat_red_threshold_panic: int = 80  # VIX>30 或 SPX<MA20 时上调
    # OQ-02 EMA 平滑半衰期(交易日)
    ema_halflife_days: int = 2

    # ---- V1.5.9 ATS Fallback ----
    ats_fallback_enabled: bool = True
    ats_fallback_consecutive_threshold: int = 3  # 连续 N 次 fallback 触发 WARNING
    ats_cron_schedule_et: list[str] = ["18:00", "04:00"]  # 美东时间

    # ---- V1.5.9 Options Anomaly V2 ----
    options_cron_interval_min: int = 30  # 轮询间隔(分钟)
    options_cron_rate_per_sec: float = 1.5  # 限流(标的/秒)
    options_cron_dte_max: int = 7  # 仅拉 0-7 DTE
    options_cache_ttl_seconds: int = 2400  # 40min(> 30min 轮询)
    options_pcr_z_threshold: float = 2.0  # Z-Score 极值阈值(2σ)
    options_dynamic_baseline_etf_multiplier: float = 3.0
    options_dynamic_baseline_stock_multiplier: float = 5.0

    # ---- V1.6.0 多源冗余 ----
    alpha_vantage_api_key: str = ""  # Alpha Vantage API key(空=不启用备份源)
    data_provider_fallback_enabled: bool = True  # 是否启用备份源降级

    # ---- Backtest ----
    backtest_history_years: int = 2
    backtest_goldset_min_events: int = 30

    # ---- Quota ----
    free_tier_daily_quota: int = 3
    pro_tier_daily_quota: int = 9999

    # ---- Sentry ----
    sentry_dsn: str | None = None

    # ---- Admin Auth (V1.5 接力期 m9t1)----
    # admin_api_key: 备选 API key(供 ops 应急,优先 JWT role)
    # admin_ip_whitelist: 逗号分隔的 IP 白名单(空表示不限)
    # admin_role_enabled: 是否启用 admin role 鉴权(False 时 sandbox_skip_admin)
    admin_api_key: str | None = None
    admin_ip_whitelist: str = ""  # 逗号分隔 e.g. "10.0.0.1,192.168.1.1"
    admin_role_enabled: bool = True  # M5/M6 锁定 True,V1.5 production 必须 True

    # ---- Paths ----
    project_root: Path = Path(__file__).resolve().parents[2]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """全局唯一配置实例(测试时可通过 `get_settings.cache_clear()` 重置)。"""
    return Settings()


settings = get_settings()
