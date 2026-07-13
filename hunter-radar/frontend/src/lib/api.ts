/** 后端 API 客户端薄封装。所有调用走 /api 前缀(由 vite 代理到 :8000)。 */

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(`API ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    credentials: "include",
    ...init,
  });
  if (!r.ok) {
    // 先用 text() 再尝试 JSON.parse,避免 body stream already read
    const body = await r.text();
    let detail: unknown = null;
    try {
      detail = JSON.parse(body);
    } catch {
      detail = body;
    }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  // §0 标的 upsert + warmup 状态查询(V1.7.4)
  /** 入库 + 触发后台 ETL 拉数。返 200 不等任务完成。 */
  createSymbol: (ticker: string, name?: string, sym_type?: string) =>
    request<{
      ticker: string;
      created: boolean;
      warmup_scheduled: boolean;
    }>("/symbols", {
      method: "POST",
      body: JSON.stringify({ ticker, name: name ?? ticker, type: sym_type ?? "stock" }),
    }),
  /** 读 symbol_master 静态字段(warmup_started_at / metadata_json)。 */
  getWarmupState: (ticker: string) =>
    request<{
      ticker: string;
      warmup_started_at: string | null;
      is_universe: boolean;
      metadata: Record<string, unknown>;
    }>(`/symbols/${ticker}/warmup-state`),

  // §3.5 Threat Score
  getThreatScore: (ticker: string) =>
    request<{
      trade_date: string;
      symbol: string;
      symbol_type: "stock" | "etf";
      total: number;
      total_raw: number;
      ema_halflife: number;
      module_options: number;
      module_short: number;
      module_divergence: number;
      module_insider: number;
      weights: Record<string, number>;
      signal_lifecycle: "init" | "red" | "yellow" | "gray" | "green";
      regime: "normal" | "panic";
      nl_summary: string | null;
      data_warmup: boolean;
    }>(`/symbols/${ticker}/threat`),

  getThreatHistory: (ticker: string, days = 90) =>
    request<Array<{ date: string; total: number; total_raw: number; signal_lifecycle?: string }>>(
      `/symbols/${ticker}/threat-history?days=${days}`,
    ),

  // §3.5 终极警报(BD-064 / FE-031)
  getUltimateAlert: (ticker: string) =>
    request<UltimateAlertDTO>(`/symbols/${ticker}/ultimate-alert`),

  // §3.1 期权异常
  getOptionsAnomaly: (ticker: string, days = 1) =>
    request<Array<{
      trade_date: string;
      contract: string;
      dte: number;
      oi_increase_pct: number;
      volume_oi_ratio: number;
      notional: number;
      is_top10_notional: boolean;
      oi_5d_series: number[];
      has_known_catalyst: boolean;
    }>>(`/symbols/${ticker}/options-anomaly?days=${days}`),

  // §3.2 做空水位
  getShortIceberg: (ticker: string, days = 20) =>
    request<Array<{
      trade_date: string;
      short_ratio: number;
      ats_short_pct: number | null;
      z_score_60d: number | null;
      data_warmup: boolean;
    }>>(`/symbols/${ticker}/short-iceberg?days=${days}`),

  // §3.3 量价背离
  getDivergence: (ticker: string, days = 30) =>
    request<Array<{
      trade_date: string;
      p_price: number;
      p_short: number;
      state: "none" | "rising" | "confirmed";
    }>>(`/symbols/${ticker}/divergence?days=${days}`),

  // §3.5 市场门控
  getRegime: () =>
    request<{
      trade_date: string;
      regime: "normal" | "panic";
      vix: number | null;
      spx_close: number | null;
      spx_ma20: number | null;
      threshold_red: number;
      banner_text: string;
    }>(`/regime`),

  // §4.3 每日猎物榜单
  getScreener: (top = 20, symbol_type?: "stock" | "etf") =>
    request<{
      trade_date: string;
      total_scanned: number;
      rows: Array<{
        rank: number;
        symbol: string;
        name: string;
        symbol_type: string;
        threat_score: number;
        signal_lifecycle: string;
        modules_active: string[];
        nl_summary: string | null;
      }>;
    }>(`/screener?top=${top}${symbol_type ? `&symbol_type=${symbol_type}` : ""}`),

  // §4.1 搜索
  lookup: (q: string) => request<Array<{ ticker: string; name: string; type: string; exchange: string }>>(
    `/symbols/lookup?q=${encodeURIComponent(q)}`,
  ),

  // §4 自选篮子(BD-070 / BD-071)
  listBaskets: () => request<BasketDTO[]>(`/baskets`),

  getBasket: (id: number) => request<BasketDTO>(`/baskets/${id}`),

  createBasket: (body: { name: string; description?: string }) =>
    request<BasketDTO>(`/baskets`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateBasket: (id: number, body: { name?: string; description?: string }) =>
    request<BasketDTO>(`/baskets/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  deleteBasket: (id: number) =>
    request<void>(`/baskets/${id}`, { method: "DELETE" }),

  listBasketMembers: (id: number) =>
    request<BasketMemberDTO[]>(`/baskets/${id}/members`),

  addBasketMembers: (id: number, tickers: string[]) =>
    request<{ basket_id: number; inserted: number; submitted: number }>(
      `/baskets/${id}/members`,
      { method: "POST", body: JSON.stringify({ tickers }) },
    ),

  removeBasketMember: (id: number, ticker: string) =>
    request<void>(`/baskets/${id}/members/${ticker.toUpperCase()}`, {
      method: "DELETE",
    }),

  getBasketDistribution: (id: number, days = 30) =>
    request<BasketDistributionDTO>(
      `/baskets/${id}/distribution?days=${days}`,
    ),

  // §6.2 FE-061 全局数据状态
  getDataStatus: () =>
    request<DataStatusDTO>(`/data-status`),



  // §3.4 内部人交易
  getInsiderActions: (ticker: string) =>
    request<Array<{
      date: string;
      person_name: string;
      title: string;
      direction: "buy" | "sell";
      shares: number;
      price_per_share: number;
      is_c_level: boolean;
    }>>(`/symbols/${ticker}/insider-actions`),

  // §3.1 V1.5.9 Options Anomaly V2(纯 Redis 读,PCR + Gamma + OTM 刺客)
  getOptionsAnomalyV2: (ticker: string) =>
    request<{
      symbol: string;
      trade_date: string;
      pcr: number;
      pcr_total_put: number;
      pcr_total_call: number;
      pcr_z_score: number | null;
      pcr_extreme: boolean;
      otm_assassin_count: number;
      gamma_clusters: Array<{ strike: number; volume: number; ratio: number; is_cluster: boolean }>;
      signal_strength: "HIGH" | "NORMAL" | "LOW" | "INSUFFICIENT";
      signal_modules: string[];
      _cache: "hit" | "miss";
    }>(`/symbols/${ticker}/options-anomaly-v2`),

  // §3.2 V1.5.9 水位图 V2(合并主源 + ATS fallback)
  getShortIcebergV2: (ticker: string, days = 20) =>
    request<{
      symbol: string;
      series: Array<{
        trade_date: string;
        short_ratio: number;
        ats_short_pct: number | null;
        z_score_60d: number | null;
        data_warmup: boolean;
      }>;
      ats_series: Array<{
        trade_date: string;
        ats_short_volume: number;
        source: string;
        is_fallback: boolean;
      }>;
    }>(`/symbols/${ticker}/short-iceberg-v2?days=${days}`),

  // §8 m6t7 灰度发布(BD-051 / FE-083)
  getAllFeatureFlags: () =>
    request<{
      flags: Record<
        string,
        {
          enabled: boolean;
          reason: "whitelist" | "rollout" | "default-off" | "default-on" | "unknown-flag";
        }
      >;
    }>(`/feature-flags`),

  // ── FE-115: 新增端点 ───────────────────────────────────

  // §3.2.1 威胁分贡献度溯源(attribution 瀑布图数据)
  getAttribution: (ticker: string) =>
    request<{
      symbol: string;
      trade_date: string;
      total_score: number;
      total_raw: number;
      primary_driver: string;
      modules: Array<{
        module: string;
        label: string;
        score: number;
        weight: number;
        contribution: number;
      }>;
      waterfall_data: Array<{
        name: string;
        module: string;
        value: number;
        cumulative: number;
        is_primary: boolean;
      }>;
    }>(`/symbols/${ticker}/attribution`),

  // §3.3 市场体制时间轴(Regime Timeline)
  getRegimeTimeline: (days = 90) =>
    request<
      Array<{
        trade_date: string;
        regime: "normal" | "panic";
        vix: number | null;
        spx_close: number | null;
      }>
    >(`/regime-timeline?days=${days}`),

  // §3.5 预警规则 CRUD
  listAlerts: () =>
    request<
      Array<{
        id: number;
        symbol: string;
        rule_type: string;
        threshold: number;
        operator: string;
        enabled: boolean;
        created_at: string;
      }>
    >(`/alerts`),

  createAlert: (body: {
    symbol: string;
    rule_type: string;
    threshold: number;
    operator: string;
  }) =>
    request<{ id: number }>(`/alerts`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getAlert: (id: number) =>
    request<{
      id: number;
      symbol: string;
      rule_type: string;
      threshold: number;
      operator: string;
      enabled: boolean;
    }>(`/alerts/${id}`),

  updateAlert: (id: number, body: Partial<{
    rule_type: string;
    threshold: number;
    operator: string;
    enabled: boolean;
  }>) =>
    request<void>(`/alerts/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  deleteAlert: (id: number) =>
    request<void>(`/alerts/${id}`, { method: "DELETE" }),

  // §6 预警历史流
  listAlertHistory: (page = 1, pageSize = 20) =>
    request<{
      total: number;
      items: Array<{
        id: number;
        alert_id: number;
        symbol: string;
        triggered_at: string;
        value: number;
        threshold: number;
      }>;
    }>(`/alerts/history?page=${page}&page_size=${pageSize}`),

  // §6 Push 订阅
  getVapidPublicKey: () =>
    request<{ public_key: string }>(`/push/vapid-public-key`),

  createPushSubscription: (body: {
    endpoint: string;
    p256dh: string;
    auth: string;
  }) =>
    request<{ id: number }>(`/push/subscriptions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listPushSubscriptions: () =>
    request<
      Array<{
        id: number;
        endpoint: string;
        created_at: string;
      }>
    >(`/push/subscriptions`),

  deletePushSubscription: (id: number) =>
    request<void>(`/push/subscriptions/${id}`, { method: "DELETE" }),

  // §6 8-K 重大事件流
  listEvents8K: (limit = 50) =>
    request<
      Array<{
        id: number;
        symbol: string;
        filing_date: string;
        item_type: string;
        title: string;
        url: string;
      }>
    >(`/events/8k?limit=${limit}`),

  getEvents8KByTicker: (ticker: string) =>
    request<
      Array<{
        id: number;
        symbol: string;
        filing_date: string;
        item_type: string;
        title: string;
        url: string;
      }>
    >(`/events/8k/${ticker}`),

  // §6 Admin 管理
  adminRunETL: () =>
    request<{ status: string }>(`/admin/etl/run`, { method: "POST" }),

  adminRunBacktest: (body?: { symbol?: string }) =>
    request<{ status: string }>(`/admin/backtest/run`, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  adminGetBacktestResult: () =>
    request<{ results: unknown[] }>(`/admin/backtest/result`),

  // §6 Analytics 前端埋点上报
  reportAnalytics: (events: Array<{
    event: string;
    value?: number;
    meta?: Record<string, unknown>;
  }>) =>
    request<void>(`/analytics/events`, {
      method: "POST",
      body: JSON.stringify({ events }),
    }),
};

/** §3.5 终极警报 DTO（BD-064 / FE-031）—— 与后端 UltimateAlertDTO 字段保持一致。 */
export type UltimateAlertDTO = {
  triggered_at: string;
  trade_date: string;
  symbol: string;
  threat_score: number;
  raw_score: number;
  ema_score: number;
  modules_active: string[];
  regime: "normal" | "panic";
  consecutive_days: number;
};

/** §4 自选篮子 DTO（BD-070）。 */
export type BasketDTO = {
  id: number;
  user_id: string;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
};

/** §4 自选篮子成员 DTO（BD-070）。 */
export type BasketMemberDTO = {
  ticker: string;
  added_at: string;
};

/** §6.2 FE-061 全局数据状态 DTO。 */
export type DataStatusDTO = {
  status: "ready" | "warming" | "stale" | "error";
  reason: string;
  data_warmup: boolean;
  last_data_date: string | null;
  is_stale: boolean;
  db_ok: boolean;
  redis_ok: boolean;
};


export type BasketDistributionDTO = {
  basket_id: number;
  trade_date: string;
  ticker_count: number;
  day_count: number;
  mean: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p99: number;
  min_score: number;
  max_score: number;
  by_ticker: Array<{
    ticker: string;
    latest: number | null;
    mean: number;
    max: number;
    lifecycle: "init" | "red" | "yellow" | "gray" | "green";
  }>;
};

// §6.3 Quota (sandbox default pro)
export interface QuotaDTO {
  tier: "free" | "pro";
  used: number;
  limit: number;
  remaining: number;
  reset_at: string | null;
  is_sandbox: boolean;
  source: string;
}

export async function getQuota(): Promise<QuotaDTO> {
  return request<QuotaDTO>("/auth/quota");
}
