import { useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** V1.7.4 自动 ETL 触发 hook(用户输入新标的时, 前端自动 upsert + 后台 ETL)。
 *
 * 触发链:
 *   user 输入 JPM → 路由 /symbol/JPM
 *   → threat query 返回 null (404 → null by notFoundToNull)
 *   → useSymbolAutoWarmup 看到 threat 为 null 时 fire-and-forget POST /symbols
 *   → 后台 warmup task 跑 90 天 deep backfill (5-7 分钟)
 *   → 同时启动 polling /symbols/{t}/warmup state 和 threat query
 *   → 数据 ready 后, 整页自动 render
 *
 * 设计规则:
 * - 并发 dedupe: 同一 ticker 同一时间只触发一次, 用 query state 守住
 * - 失败也 silent: warmup 触发失败不能 blocking UI (用户只看进度)
 * - 24 小时内不重复 upsert: 已有 warmup_started_at 时不重复触发
 */

export type WarmupProgress = {
  status: "idle" | "queued" | "running" | "ready" | "failed" | "skipped";
  /** 0-100, 整体 ETL 进度(rough) */
  progress: number;
  /** 具体步骤名 */
  currentStep: string;
  /** 该步骤涉及的 row 数 */
  rows?: number;
  /** 错误信息(只在 status=failed 时填) */
  error?: string;
};

export function useSymbolAutoWarmup(
  ticker: string,
  threatIsNull: boolean,
) {
  const t = ticker.toUpperCase();

  // 1) trigger mutation
  const trigger = useMutation({
    mutationFn: () => api.createSymbol(t),
    onError: (e) => {
      // silent — UI already shows "正在拉取", 用户会 retry via page reload
      console.warn(`[auto-warmup] trigger failed for ${t}:`, e);
    },
  });

  // 2) warmup-state polling (3s interval)
  const state = useQuery({
    queryKey: ["warmup-state", t],
    queryFn: () => api.getWarmupState(t),
    enabled: threatIsNull && !!t,
    refetchInterval: (q) => {
      const data = q.state.data as
        | { metadata?: { warmup_status?: string } }
        | undefined;
      const s = data?.metadata?.warmup_status;
      // running/queued 时每 3s 拉一次, ready/failed 时停止 polling
      if (s === "running" || s === "queued" || !s) return 3000;
      return false;
    },
    retry: 0,
  });

  // 3) auto-fire-and-forget on threat-null
  const startedAt = (state.data as any)?.warmup_started_at as string | null | undefined;

  useEffect(() => {
    if (!threatIsNull || !t) return;

    // 已有 metadata / warmup_started_at 时跳过(24h 内已跑过)
    if (startedAt) {
      const ageMs = Date.now() - new Date(startedAt).getTime();
      if (ageMs < 24 * 3600 * 1000) {
        // 24h 内已跑过, 不再触发
        return;
      }
    }

    // avoid duplicate trigger
    if (trigger.isPending || trigger.isSuccess) return;

    trigger.mutate();
  }, [threatIsNull, t]); // eslint-disable-line react-hooks/exhaustive-deps

  // 4) map to UI-friendly progress
  const md = (state.data as any)?.metadata as Record<string, any> | undefined;
  const status = (md?.warmup_status ?? trigger.status ?? "idle") as WarmupProgress["status"];
  const stepIdx = Number(md?.warmup_step ?? 0);
  const totalSteps = Number(md?.warmup_steps_total ?? 7);
  const stepRows = Number(md?.warmup_step_rows ?? 0);
  const steps = [
    "fetch_daily_bars",
    "load_short_volume",
    "compute_short_ratio",
    "compute_divergence",
    "compute_threat_scores",
    "ultimate_alert",
    "options_chain",
  ];
  const currentStep = steps[Math.min(stepIdx, steps.length - 1)] ?? "queued";

  const progress: WarmupProgress = {
    status,
    progress: status === "ready" ? 100 : Math.round((stepIdx / totalSteps) * 100),
    currentStep,
    rows: stepRows,
    error: typeof md?.warmup_error === "string" ? md.warmup_error : undefined,
  };

  return { progress, triggered: trigger.isSuccess || !!startedAt };
}
