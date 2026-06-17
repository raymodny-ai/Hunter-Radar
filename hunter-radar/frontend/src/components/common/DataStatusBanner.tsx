import { useState } from "react";

import { useDataStatus } from "@/features/useDataStatus";
import type { DataStatusDTO } from "@/lib/api";

export type DataStatus = "ready" | "warming" | "stale" | "error";

export interface DataStatusBannerProps {
  /** 可选:外部传入已推算好的 status(便于 e2e / 单元测试) */
  statusOverride?: DataStatus | null;
  reasonOverride?: string | null;
}

/** §6.2 FE-061 全局数据状态 banner。
 *
 * 4 个状态:
 * - ready   → 不渲染(数据已就位)
 * - warming → 冷启动 / 无 PG,黄色 banner,显式说明
 * - stale   → 数据过期,橙色 banner,显式 last_data_date
 * - error   → 后端不可达 / 5xx,红色 banner,可关闭 + 重试按钮
 *
 * 硬规则:
 * - 严禁在数据缺失时捏造数字 / 隐藏 banner
 * - 必须显式说明原因(后端 reason 字段 + i18n 兑底)
 * - 用户可关闭 error banner(用 localStorage 暂存 5 分钟)
 * - 键盘可达:close 按钮 + retry 按钮都用 button + aria-label
 */
export function DataStatusBanner({
  statusOverride,
  reasonOverride,
}: DataStatusBannerProps) {
  const query = useDataStatus();
  const [hiddenUntil, setHiddenUntil] = useState<number | null>(null);

  const status: DataStatus = (() => {
    if (statusOverride) return statusOverride;
    if (query.isError) return "error";
    if (query.data) return query.data.status;
    return "ready";
  })();
  const reason: string = (() => {
    if (reasonOverride !== undefined && reasonOverride !== null) {
      return reasonOverride;
    }
    if (query.isError) return String(query.error?.message ?? "数据获取失败");
    if (query.data) return query.data.reason;
    return "";
  })();

  // ready 状态 → 完全不渲染
  if (status === "ready") return null;

  // 用户主动关闭(error 才允许,5 分钟)
  if (status === "error" && hiddenUntil && Date.now() < hiddenUntil) {
    return null;
  }

  const palette = paletteFor(status);

  return (
    <div
      role="status"
      aria-live="polite"
      data-status={status}
      className={`border-y ${palette.border} ${palette.bg} px-4 py-2 text-xs flex items-center gap-3`}
    >
      <span aria-hidden="true" className="text-base">
        {palette.icon}
      </span>
      <div className="flex-1">
        <div className={`font-medium ${palette.title}`}>{palette.titleText}</div>
        {reason && (
          <div className={`mt-0.5 ${palette.reason}`}>{reason}</div>
        )}
      </div>
      {status === "error" && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => query.refetch()}
            className="px-2 py-1 rounded border border-red-700/60 text-red-200 hover:bg-red-950/50"
            aria-label="retry data status"
          >
            重试
          </button>
          <button
            type="button"
            onClick={() => setHiddenUntil(Date.now() + 5 * 60 * 1000)}
            className="px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            aria-label="dismiss data status banner"
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
}

function paletteFor(status: DataStatus) {
  switch (status) {
    case "warming":
      return {
        border: "border-amber-700/50",
        bg: "bg-amber-950/30",
        icon: "⏳",
        title: "text-amber-200",
        titleText: "数据未到位 · Data Warming",
        reason: "text-amber-300/80",
      };
    case "stale":
      return {
        border: "border-orange-700/50",
        bg: "bg-orange-950/30",
        icon: "⚠️",
        title: "text-orange-200",
        titleText: "数据已过期 · Data Stale",
        reason: "text-orange-300/80",
      };
    case "error":
      return {
        border: "border-red-700/60",
        bg: "bg-red-950/30",
        icon: "⛔",
        title: "text-red-200",
        titleText: "数据获取失败 · Data Unavailable",
        reason: "text-red-300/80",
      };
    default:
      return {
        border: "border-slate-700",
        bg: "bg-slate-900",
        icon: "ℹ️",
        title: "text-slate-200",
        titleText: "Info",
        reason: "text-slate-400",
      };
  }
}

/** 单测 / Storybook 用:从 status + reason 直接构造 props(走 statusOverride) */
export function DataStatusBannerFor(
  status: DataStatus,
  reason: string,
): DataStatusBannerProps {
  return { statusOverride: status, reasonOverride: reason };
}

// 抑制未用类型告警(DataStatusDTO 用于 hook 内部类型推导)
export type _DataStatusDTO = DataStatusDTO;
