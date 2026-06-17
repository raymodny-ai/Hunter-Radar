import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** 90 日 Threat Score 轨迹查询 hook(FE-032 / BD-066)。
 *
 * 严格规则:
 * - 数据缺失时优雅降级(返空数组,不抛错)
 * - staleTime 6 小时(frontend-plan §4.3 端点表)
 */
export function useThreatHistory(ticker: string, days = 90) {
  return useQuery({
    queryKey: ["threat-history", ticker, days],
    queryFn: () => api.getThreatHistory(ticker, days),
    staleTime: 1000 * 60 * 60 * 6,
    retry: 0,
    enabled: !!ticker,
  });
}
