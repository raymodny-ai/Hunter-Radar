/** §6.3 no-op: always returns Pro state (payment features removed).
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

/** 轮询间隔(毫秒) — 沙箱不实跑,但保留常量供 hooks 复用。 */
export const POLL_INTERVAL_MS = 60_000;

const PRO_STATE = {
  tier: "pro" as const,
  used: 0,
  limit: -1,
  remaining: -1,
  reset_at: "2038-01-01T00:00:00+00:00",
  is_sandbox: false,
  source: "sandbox_default" as const,
};

export type QuotaDTO = typeof PRO_STATE;

export function useApiQuota(): UseQueryResult<QuotaDTO, Error> {
  return useQuery<QuotaDTO, Error>({
    queryKey: ["quota", "current"],
    queryFn: async () => PRO_STATE,
    staleTime: Infinity,
    refetchInterval: POLL_INTERVAL_MS,
  });
}

/** Always returns pro state. */
export async function peekQuota(): Promise<QuotaDTO> {
  return PRO_STATE;
}
