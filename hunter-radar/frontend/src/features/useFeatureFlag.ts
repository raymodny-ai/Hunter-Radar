/** M6 灰度发布 hook(按 flag_key 订阅)。

数据源:GET /api/v1/feature-flags → {flags: {flag_key: {enabled, reason}}}
- 沙箱降级:无 api 返回时按 `fallback` 参数返(默认 false)
- 自动 5 分钟 refetch,React Query 缓存

典型用法:
- const showNewCheckout = useFeatureFlag('subscribe_v2', false);
- const is8kEnabled = useFeatureFlag('8k_feed');
*/
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type FlagReason = "whitelist" | "rollout" | "default-off" | "default-on" | "unknown-flag";

export interface FlagSnapshot {
  enabled: boolean;
  reason: FlagReason;
}

export function useFeatureFlag(flagKey: string, fallback = false): boolean {
  const q = useQuery({
    queryKey: ["feature-flags"],
    queryFn: () => api.getAllFeatureFlags(),
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const flags = (q.data?.flags ?? {}) as Record<string, FlagSnapshot>;
  const snap = flags[flagKey];
  return snap?.enabled ?? fallback;
}

/** 批量取 flag(返回原始快照)。 */
export function useFeatureFlagSnapshot(flagKey: string): FlagSnapshot | null {
  const q = useQuery({
    queryKey: ["feature-flags"],
    queryFn: () => api.getAllFeatureFlags(),
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const flags = (q.data?.flags ?? {}) as Record<string, FlagSnapshot>;
  return flags[flagKey] ?? null;
}

/** 沙箱纯函数:从快照字典中取 flag 启用态(single source of truth)。 */
export function pickFlag(
  flags: Record<string, FlagSnapshot>,
  flagKey: string,
  fallback = false,
): boolean {
  return flags[flagKey]?.enabled ?? fallback;
}