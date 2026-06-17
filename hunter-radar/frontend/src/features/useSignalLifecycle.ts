import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** OQ-02 严格定义:连续 N 个交易日(EMA 后)≥ 阈值。
 *
 * 严格规则:
 * - 从尾部向前扫,断即停
 * - 数据不足 30 日时返 0(冷启动暖态,不计入连续)
 * - 这只是客户端轻量级镜像,后端 OQ-02 测试守护锁主逻辑(services.threat_score.consecutive_business_days_above)
 */
function consecutiveBusinessDaysAbove(series: number[], threshold: number): number {
  if (!series || series.length < 30) return 0;
  let count = 0;
  for (let i = series.length - 1; i >= 0; i--) {
    if (series[i] >= threshold) {
      count++;
    } else {
      break;
    }
  }
  return count;
}

export type SignalLifecycle = "init" | "red" | "yellow" | "gray" | "green";

interface UseSignalLifecycleOptions {
  threshold: number;
}

interface SignalLifecycleResult {
  lifecycle: SignalLifecycle;
  consecutiveDays: number;
  warmup: boolean;
  emaScore: number;
}

/** 信号生命周期 + 连续天数计算 hook(FE-030 / BD-062 / OQ-02)。
 *
 * 数据流:
 *   1. 调 useThreatHistory 拿 90 日 total
 *   2. 取最后一日 lifecycle 字段(后端 services.threat_score.decide_lifecycle 输出)
 *   3. 客户端镜像 consecutive_business_days_above(等阈值 ≥ 70)
 */
export function useSignalLifecycle(
  ticker: string,
  options: UseSignalLifecycleOptions,
) {
  const { threshold } = options;
  const history = useQuery({
    queryKey: ["threat-history", ticker, 90],
    queryFn: () => api.getThreatHistory(ticker, 90),
    staleTime: 1000 * 60 * 60 * 6,
    retry: 0,
    enabled: !!ticker,
  });

  if (!history.data || history.data.length === 0) {
    return {
      data: null as SignalLifecycleResult | null,
      isLoading: history.isLoading,
      isError: history.isError,
    };
  }

  // 后端威胁分数端点返回 lifecycle 字段
  const todayEma = history.data[history.data.length - 1]?.total ?? 0;
  const series = history.data.map((p) => p.total);
  const consecutiveDays = consecutiveBusinessDaysAbove(series, threshold);

  let lifecycle: SignalLifecycle = "init";
  if (todayEma >= 70) lifecycle = "red";
  else if (todayEma >= 50) lifecycle = "yellow";
  else if (todayEma >= 30) lifecycle = "gray";
  else if (todayEma > 0) lifecycle = "green";

  // 暖启动:历史 < 30 日不计入连续
  const warmup = series.length < 30;

  return {
    data: {
      lifecycle,
      consecutiveDays: warmup ? 0 : consecutiveDays,
      warmup,
      emaScore: todayEma,
    } as SignalLifecycleResult,
    isLoading: history.isLoading,
    isError: history.isError,
  };
}
