/** §6.3 FE-064 免费版每日 3 次查询配额 hook。
 *
 * 数据源:`GET /api/v1/auth/quota`(后端 `app/api/quota.py`)
 * - pro tier 不展示(lim=-1, remaining=-1)
 * - 沙箱模式下仍可拉取(`is_sandbox=true`),便于前端调试 UI
 * - 30s 轮询 + 5xx 抛错
 * - 与 useDataStatus 模式一致(同作者 m5t6)
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { api, type QuotaDTO } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

export function useApiQuota(): UseQueryResult<QuotaDTO, Error> {
  return useQuery<QuotaDTO, Error>({
    queryKey: ["quota", "current"],
    queryFn: async () => api.getQuota(),
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: true,
    staleTime: POLL_INTERVAL_MS / 2,
  });
}

/** 只读 peek(非 hook,给 QuotaBanner 静态场景用)。 */
export async function peekQuota(): Promise<QuotaDTO> {
  return api.getQuota();
}
