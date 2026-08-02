/** §6.3 FE-064 / 4.4 (NEW-02): Quota banner。
 *
 * 原为 always-null(支付功能移除时占位)。4.4 后:
 * - 监听 429 "quota-exceeded" 事件(全局 request 拦截触发)→ 显示红色 exhausted banner
 * - 可选消费 useApiQuota 拉真实 tier(剩余配额)
 * - 事件不触发时维持静默(null),避免打扰正常使用
 */
import { useEffect, useState } from "react";

import { onAuthEvent } from "@/lib/auth";

export interface QuotaBannerProps {
  stateOverride?: unknown;
  silent?: boolean;
}

/** Quota state palette — returns CSS color for a given quota tier/state. */
export function paletteFor(state: string | null | undefined): string {
  switch (state) {
    case "free":
      return "#94a3b8"; // slate-400
    case "pro":
      return "#22d3ee"; // cyan-400
    case "exhausted":
      return "#f87171"; // red-400
    default:
      return "#64748b"; // slate-500
  }
}

/** 4.4: 429 触发后短暂显示 exhausted banner(5 分钟冷却,避免刷屏)。 */
export function QuotaBanner(_props: QuotaBannerProps): null | JSX.Element {
  const [exhausted, setExhausted] = useState(false);

  useEffect(() => {
    const off = onAuthEvent((ev) => {
      if (ev.type === "quota-exceeded") {
        setExhausted(true);
        // 5 分钟后自动复位,期间不重复弹
        window.setTimeout(() => setExhausted(false), 5 * 60 * 1000);
      }
    });
    return off;
  }, []);

  if (!exhausted) return null;
  return (
    <div
      role="status"
      data-quota-state="exhausted"
      className="border-y border-red-700/60 bg-red-950/30 px-4 py-2 text-xs flex items-center gap-3"
      style={{ color: paletteFor("exhausted") }}
    >
      <span aria-hidden="true">🚫</span>
      <span className="font-medium">API 每日配额已用完</span>
      <span className="text-red-300/70">部分数据请求将被拒绝,请明日重试</span>
    </div>
  );
}

/** Placeholder DOM hooks for accessibility audit (m5t8/m8t2). */
export const QUOTA_STATE_ATTR = "data-quota-state";
export const QUOTA_STATE_VALUE_PRO = "pro";

export function describeQuotaState(): string {
  return "pro";
}
