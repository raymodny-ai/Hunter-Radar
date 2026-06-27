"""代理池 + UA 轮换模块(Phase 2 预留,V1.5.9 stub)。

ATS Fallback 爬虫在高频场景下需要代理池来降低 IP 封锁风险。
本模块提供异步代理获取接口,Phase 1 由 ats_scraper 内置 UA 池完成,
Phase 2 对接付费代理服务(如 BrightData / Oxylabs / SmartProxy)。

接口契约:
    async def get_proxy() -> str | None   # 返回 "http://user:pass@host:port" 或 None
    async def get_user_agent() -> str     # 随机 UA
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProxyConfig:
    """代理配置(Phase 2 启用时由 settings 注入)。"""

    enabled: bool = False
    provider: str = "none"  # "brightdata" | "oxylabs" | "smartproxy" | "none"
    api_key: str | None = None
    rotation_strategy: str = "random"  # "random" | "sequential" | "geo"


# 内置 UA 池(Phase 1 即可用)
_BUILTIN_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


async def get_proxy(config: ProxyConfig | None = None) -> str | None:
    """获取一个代理 URL(Phase 2 实装后对接真实代理池)。

    Phase 1: 始终返回 None(直连)。
    """
    cfg = config or ProxyConfig()
    if not cfg.enabled:
        return None
    # Phase 2: 根据 cfg.provider 对接 API
    # if cfg.provider == "brightdata":
    #     return await _brightdata_proxy(cfg)
    return None


async def get_user_agent() -> str:
    """随机返回一个 User-Agent 字符串。"""
    return random.choice(_BUILTIN_USER_AGENTS)


def build_browser_args(proxy_url: str | None = None) -> list[str]:
    """构建 Playwright chromium 启动参数。"""
    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]
    if proxy_url:
        args.append(f"--proxy-server={proxy_url}")
    return args
