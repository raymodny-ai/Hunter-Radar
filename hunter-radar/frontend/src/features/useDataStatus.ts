import { useQuery } from "@tanstack/react-query";

import { api, type DataStatusDTO } from "@/lib/api";

/** §6.2 FE-061 全局数据状态 hook。
 *
 * 严格规则:
 * - 30s 轮询(后端 staleTime 较短,但前端不应频繁查)
 * - 后端不可达 → isError=true,status="error"
 * - 5xx 显式抛错,让 DataStatusBanner 走 error 状态
 * - 严禁 mock 伪装 ready
 */
export function useDataStatus() {
  return useQuery<DataStatusDTO, Error>({
    queryKey: ["data-status"],
    queryFn: () => api.getDataStatus(),
    refetchInterval: 1000 * 30,
    staleTime: 1000 * 15,
    retry: 1,
  });
}
