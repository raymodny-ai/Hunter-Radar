/**
 * P1-05: Auth 层 (PRD §5.1)
 *
 * - JWT Bearer token 存取 (localStorage)
 * - getAuthHeader(): 供 api.ts request() 注入
 * - 401 全局拦截 → 清除 token + toast 通知
 * - X-RateLimit-Remaining < 10% → quota warning 事件
 * - 向后兼容: 无 token 时不注入 header (sandbox 模式)
 */

const TOKEN_KEY = "hunter_access_token";
const REFRESH_KEY = "hunter_refresh_token";

// ── Token CRUD ──────────────────────────────────────────

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setTokens(access: string, refresh?: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  } catch {
    /* storage unavailable — sandbox mode */
  }
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* noop */
  }
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

/** 构造 Authorization header；无 token 时返回空对象(向后兼容 sandbox)。 */
export function getAuthHeader(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Auth 事件总线 (401 / rate-limit) ────────────────────

export type AuthEventType = "unauthorized" | "rate-limit-warning" | "quota-exceeded";

export interface AuthEvent {
  type: AuthEventType;
  message: string;
  /** rate-limit 剩余百分比 (0-1) */
  remainingRatio?: number;
}

type AuthEventListener = (event: AuthEvent) => void;

const listeners = new Set<AuthEventListener>();

export function onAuthEvent(listener: AuthEventListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function emitAuthEvent(event: AuthEvent): void {
  listeners.forEach((fn) => {
    try {
      fn(event);
    } catch {
      /* listener error — ignore */
    }
  });
}

/** 401 处理: 清除 token + 广播事件 (UI 层显示 toast)。 */
export function handleUnauthorized(): void {
  clearTokens();
  emitAuthEvent({
    type: "unauthorized",
    message: "登录已过期，请重新登录",
  });
}

/** Rate limit 感知: X-RateLimit-Remaining < 10% 时广播警告。 */
export function checkRateLimit(response: Response): void {
  const remaining = response.headers.get("X-RateLimit-Remaining");
  const limit = response.headers.get("X-RateLimit-Limit");
  if (remaining === null || limit === null) return;

  const remainingNum = Number(remaining);
  const limitNum = Number(limit);
  if (Number.isNaN(remainingNum) || Number.isNaN(limitNum) || limitNum <= 0) return;

  const ratio = remainingNum / limitNum;
  if (ratio < 0.1) {
    emitAuthEvent({
      type: "rate-limit-warning",
      message: `API 配额即将耗尽 (剩余 ${remainingNum}/${limitNum})`,
      remainingRatio: ratio,
    });
  }
}

/** 4.4 (NEW-02): HTTP 429 配额耗尽 → 广播事件 + DOM 事件(QuotaBanner 消费)。 */
export function handleQuotaExceeded(): void {
  emitAuthEvent({ type: "quota-exceeded", message: "每日配额已用完" });
  // 兼容方案 4.4 的 window event 语义
  try {
    window.dispatchEvent(new CustomEvent("quota-exceeded"));
  } catch {
    /* SSR/旧浏览器 | ignore */
  }
}
