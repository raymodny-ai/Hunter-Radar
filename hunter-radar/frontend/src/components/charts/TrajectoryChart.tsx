/**
 * FE-119: 90-Day Trajectory ECharts 折线图
 *
 * 替换现有 ThreatHistoryChart(SVG)为 ECharts 实现:
 * - smooth: true 平滑曲线
 * - Hover Tooltip 同时展示 EMA 后分 + 原始分 + lifecycle 颜色
 * - 阈值标线(markLine)
 * - lifecycle 颜色编码通过 visualMap 或 scatter 叠加
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";

export type ThreatHistoryPoint = {
  date: string;
  total: number;
  total_raw: number;
  lifecycle?: "init" | "red" | "yellow" | "gray" | "green";
};

export interface TrajectoryChartProps {
  data: ThreatHistoryPoint[] | undefined;
  threshold: number;
  isLoading?: boolean;
  className?: string;
  days?: number;
}

const LIFECYCLE_COLOR: Record<string, string> = {
  init: HUNTER_COLORS.textMuted,
  red: HUNTER_COLORS.red,
  yellow: HUNTER_COLORS.yellow,
  gray: HUNTER_COLORS.textSecondary,
  green: HUNTER_COLORS.green,
};

export function TrajectoryChart({
  data,
  threshold,
  isLoading,
  className,
  days = 90,
}: TrajectoryChartProps) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!data || data.length < 2) return null;

    const sorted = [...data]
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-days);

    const dates = sorted.map((p) => p.date.slice(5)); // MM-DD
    const emaValues = sorted.map((p) => p.total);
    const rawValues = sorted.map((p) => p.total_raw);

    // lifecycle scatter 数据点
    const scatterData = sorted.map((p, i) => ({
      value: [i, p.total],
      itemStyle: { color: LIFECYCLE_COLOR[p.lifecycle || "init"] },
    }));

    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const arr = params as Array<{
            dataIndex: number;
            seriesName: string;
            value: number;
          }>;
          if (!arr || arr.length === 0) return "";
          const idx = arr[0].dataIndex;
          const p = sorted[idx];
          if (!p) return "";
          const lcColor = LIFECYCLE_COLOR[p.lifecycle || "init"];
          return [
            `<b>${p.date}</b>`,
            `EMA: <b>${p.total.toFixed(1)}</b>`,
            `${t("charts.trajectory.raw")}: ${p.total_raw.toFixed(1)}`,
            `${t("charts.trajectory.lifecycle")}: <span style="color:${lcColor}">${p.lifecycle || "—"}</span>`,
          ].join("<br/>");
        },
      },
      legend: {
        data: [
          t("charts.trajectory.ema"),
          t("charts.trajectory.raw"),
        ],
        top: 0,
      },
      grid: { left: 40, right: 15, top: 30, bottom: 25 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: {
          interval: Math.floor(sorted.length / 4),
          fontSize: 9,
        },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
      },
      series: [
        {
          name: t("charts.trajectory.ema"),
          type: "line",
          smooth: true,
          data: emaValues,
          lineStyle: { width: 2, color: HUNTER_COLORS.textPrimary },
          itemStyle: { color: HUNTER_COLORS.textPrimary },
          showSymbol: false,
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { type: "dashed", color: HUNTER_COLORS.textMuted },
            data: [{ yAxis: threshold, label: { formatter: `${t("charts.trajectory.threshold")} ${threshold}`, fontSize: 9 } }],
          },
        },
        {
          name: t("charts.trajectory.raw"),
          type: "line",
          smooth: true,
          data: rawValues,
          lineStyle: { width: 1, type: "dotted", color: HUNTER_COLORS.textMuted },
          itemStyle: { color: HUNTER_COLORS.textMuted },
          showSymbol: false,
        },
        {
          name: "lifecycle",
          type: "scatter",
          data: scatterData,
          symbolSize: 5,
          z: 10,
          tooltip: { show: false },
        },
      ],
    };
  }, [data, threshold, days, t]);

  const { containerRef } = useECharts(option, [data, threshold]);

  if (isLoading) return <SkeletonChart className={className} height={220} />;
  if (!data || data.length < 2) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.trajectory.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[220px]"}
      role="img"
      aria-label={t("charts.trajectory.ariaLabel")}
    />
  );
}
