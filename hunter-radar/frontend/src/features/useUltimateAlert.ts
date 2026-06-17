import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";

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

/** 终极警报查询 hook(FE-031 / BD-064)。
 *
 * 严格规则:
 * - 端点未到位时(后端 M3-t4 才会新增)优雅降级:404 → 返 null,不抛错
 * - 内存 OpenAPI 草案:GET /api/v1/symbols/{ticker}/ultimate-alert
 *   响应:UltimateAlertDTO | null
 *   错误:404(无活跃警报) | 5xx(后端故障)
 *
 * 记忆硬约束(API 契约与数据真实性规范):OpenAPI 变更需先 freeze 再同步 FE-010。
 * 本 hook 在后端端点落地前应只读 null,绝不允许用 mock 伪装实时数据。
 */
export function useUltimateAlert(ticker: string) {
  return useQuery<UltimateAlertDTO | null>({
    queryKey: ["ultimate-alert", ticker],
    queryFn: async () => {
      try {
        return await api.getUltimateAlert(ticker);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          // 端点已就位但当日无警报(后端语义)
          return null;
        }
        if (e instanceof ApiError && e.status === 501) {
          // 端点尚未实现(M3-t4 之前)
          return null;
        }
        throw e; // 5xx 等真实错误向上抛
      }
    },
    staleTime: 1000 * 60 * 5, // 5 分钟
    retry: 0,
    enabled: !!ticker,
  });
}
