/** §6.3 / 4.4 (NEW-02): 用户 API 配额 hook — 对接真实后端 /auth/quota。
 *
 * 原为 no-op(支付功能移除时占位)。4.4 接线后:
 * - 有 token 时调 getQuota() 拉真实 tier/used/limit/remaining
 * - 无 token / 401 / 404(匿名或端点未启用)→ 优雅回落 PRO_STATE(不刷 toast)
 * - 429 已在全局 request() 拦截, 这里只消费数据
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getQuota, type QuotaDTO, ApiError } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

/** 轮询间隔(毫秒) */
export const POLL_INTERVAL_MS = 60_000;

const PRO_STATE: QuotaDTO = {
  tier: "pro",
  used: 0,
  limit: -1,
  remaining: -1,
  reset_at: null,
  is_sandbox: false,
  source: "sandbox_default",
};

export type { QuotaDTO };

export function useApiQuota(): UseQueryResult<QuotaDTO, Error> {
  return useQuery<QuotaDTO, Error>({
    queryKey: ["quota", "current"],
    queryFn: async () => {
      // 无 token(匿名/sandbox)→ 直接返回 pro 占位,不打扰
      if (!isAuthenticated()) return PRO_STATE;
      try {
        const q = await getQuota();
        return q ?? PRO_STATE;
      } catch (e) {
        // 401/404 = 未登录或端点未启用 → 回落 pro,silent
        if (e instanceof ApiError && (e.status === 401 || e.status === 404)) {
          return PRO_STATE;
        }
        throw e; // 其余错误照常抛出(QuotaBanner 可显示 error)
      }
    },
    staleTime: 1000 * 60,
    refetchInterval: POLL_INTERVAL_MS,
    retry: 1,
  });
}

/** 4.4: 一次性读当前配额(非 hook 场景,如 429 后刷新)。 */
export async function peekQuota(): Promise<QuotaDTO> {
  if (!isAuthenticated()) return PRO_STATE;
  try {
    return (await getQuota()) ?? PRO_STATE;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 404)) {
      return PRO_STATE;
    }
    throw e;
  }
}
