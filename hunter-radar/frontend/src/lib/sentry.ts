/**
 * §6.2 FE-069 Sentry 前端接入
 *
 * 设计:
 * - 仅在 VITE_SENTRY_DSN 设置时初始化(沙箱 / dev 不发任何东西)
 * - 必须在 main.tsx 最早处调用,后续错误自动捕获
 * - 不捕获 development 环境的 console.warn(只报 throw + 5xx)
 *
 * 硬约束:
 * - 不上报 email / user_id / 持仓等 PII(只带 release / environment)
 * - 不主动 capture user actions,只让 Sentry 自动捕获 unhandledrejection / error
 * - 在 dev / preview 模式:打印到 console,不真发 Sentry
 */

const DSN: string =
  (import.meta.env.VITE_SENTRY_DSN as string | undefined) ?? "";

const APP_VERSION: string =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "1.4.0";

const MODE: string = import.meta.env.MODE ?? "production";

let _initialized = false;

/** 初始化 Sentry(幂等)。无 DSN 时是 no-op。 */
export function initSentry(): void {
  if (_initialized) return;
  _initialized = true;
  if (!DSN) {
    // 沙箱 / dev:不真发,只标个标记便于 devtools 验证
    if (typeof window !== "undefined") {
      (window as unknown as { __sentry_initialized: boolean }).__sentry_initialized =
        false;
    }
    return;
  }

  // 动态 import(沙箱无 @sentry/react 时,init 仍然 no-op,模块加载失败时静默)
  void import("@sentry/react")
    .then((mod) => {
      const Sentry = mod;
      Sentry.init({
        dsn: DSN,
        environment: MODE,
        release: `hunter-radar@${APP_VERSION}`,
        tracesSampleRate: 0.1,
        replaysSessionSampleRate: 0.05,
        replaysOnErrorSampleRate: 0.5,
        // PII 防护:不收集 user email / id
        sendDefaultPii: false,
        // 沙箱 / 自家域名不进 Sentry
        denyUrls: [/localhost/, /127\.0\.0\.1/],
      });
      if (typeof window !== "undefined") {
        (window as unknown as { __sentry_initialized: boolean }).__sentry_initialized =
          true;
      }
    })
    .catch((e) => {
      // import 失败(沙箱缺 @sentry/react)→ 静默降级
      if (typeof console !== "undefined") {
        console.warn("[sentry] failed to load @sentry/react:", e);
      }
    });
}

/** 上报异常(供 queryClient 错误边界 / 全局 catch 用)。无 DSN 时 no-op。 */
export function captureException(
  err: unknown,
  ctx?: Record<string, unknown>,
): void {
  if (!DSN) return;
  void import("@sentry/react")
    .then((mod) => {
      mod.captureException(err, { extra: ctx });
    })
    .catch(() => {
      // 静默
    });
}

/** 加 breadcrumb(供 API 错误前后的上下文关联)。无 DSN 时 no-op。 */
export function addBreadcrumb(
  msg: string,
  data?: Record<string, unknown>,
): void {
  if (!DSN) return;
  void import("@sentry/react")
    .then((mod) => {
      mod.addBreadcrumb({ message: msg, data, level: "info" });
    })
    .catch(() => {
      // 静默
    });
}

/** 是否初始化成功(便于 e2e / Storybook 验证)。 */
export function isSentryEnabled(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(
    (window as unknown as { __sentry_initialized?: boolean }).__sentry_initialized,
  );
}

/** 当前 DSN(只读,供诊断)。 */
export function getSentryDsn(): string {
  return DSN;
}

export const __test__ = { APP_VERSION, MODE, DSN };
