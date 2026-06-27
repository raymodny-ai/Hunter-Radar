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
    request<Array<{ date: string; total: number; total_raw: number }>>(
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
      signal_strength: "HIGH" | "NORMAL" | "LOW";
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
