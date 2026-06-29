/**
 * FE-122: Volume-Price Divergence Dual-track — 量价背离双轨图
 *
 * ECharts 双 Y 轴:
 * - 左 Y:价格归一化(明线)
 * - 右 Y:做空量回归(暗线)
 * - 背离段 markArea 血红色遮罩
 * - 共用 X 轴(日期)
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";

export interface DivergencePoint {
  trade_date: string;
  p_price: number;
  p_short: number;
  state: "none" | "rising" | "confirmed";
}

export interface DivergenceChartProps {
  data: DivergencePoint[] | undefined;
  isLoading?: boolean;
  className?: string;
}

export function DivergenceChart({
  data,
  isLoading,
  className,
}: DivergenceChartProps) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!data || data.length < 2) return null;

    const sorted = [...data].sort((a, b) =>
      a.trade_date.localeCompare(b.trade_date),
    );

    const dates = sorted.map((d) => d.trade_date.slice(5));
    const priceData = sorted.map((d) => d.p_price);
    const shortData = sorted.map((d) => d.p_short);

    // 找背离段(state !== "none")生成 markArea
    const divergenceAreas: Array<Array<{ xAxis: string; itemStyle?: { color: string } }>> = [];
    let areaStart: number | null = null;
    for (let i = 0; i < sorted.length; i++) {
      if (sorted[i].state !== "none" && areaStart === null) {
        areaStart = i;
      } else if (sorted[i].state === "none" && areaStart !== null) {
        divergenceAreas.push([
          { xAxis: sorted[areaStart].trade_date.slice(5), itemStyle: { color: "rgba(255, 82, 82, 0.12)" } },
          { xAxis: sorted[i - 1].trade_date.slice(5) },
        ]);
        areaStart = null;
      }
    }
    if (areaStart !== null) {
      divergenceAreas.push([
        { xAxis: sorted[areaStart].trade_date.slice(5), itemStyle: { color: "rgba(255, 82, 82, 0.12)" } },
        { xAxis: sorted[sorted.length - 1].trade_date.slice(5) },
      ]);
    }

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
          const d = sorted[idx];
          if (!d) return "";
          const stateLabel =
            d.state === "confirmed"
              ? `<span style="color:${HUNTER_COLORS.red}">⚠ ${t("charts.divergence.confirmed")}</span>`
              : d.state === "rising"
                ? `<span style="color:${HUNTER_COLORS.yellow}">${t("charts.divergence.rising")}</span>`
                : t("charts.divergence.none");
          return [
            `<b>${d.trade_date}</b>`,
            `${t("charts.divergence.price")}: <b>${d.p_price.toFixed(3)}</b>`,
            `${t("charts.divergence.short")}: <b>${d.p_short.toFixed(3)}</b>`,
            `${t("charts.divergence.state")}: ${stateLabel}`,
          ].join("<br/>");
        },
      },
      legend: {
        data: [
          t("charts.divergence.price"),
          t("charts.divergence.short"),
        ],
        top: 0,
      },
      grid: { left: 50, right: 50, top: 30, bottom: 25 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: {
          interval: Math.floor(sorted.length / 4),
          fontSize: 9,
        },
      },
      yAxis: [
        {
          type: "value",
          name: t("charts.divergence.price"),
          nameTextStyle: { fontSize: 9, color: HUNTER_COLORS.textMuted },
          position: "left",
          axisLabel: { fontSize: 9 },
          splitLine: { lineStyle: { color: HUNTER_COLORS.grid, type: "dashed" } },
        },
        {
          type: "value",
          name: t("charts.divergence.short"),
          nameTextStyle: { fontSize: 9, color: HUNTER_COLORS.textMuted },
          position: "right",
          axisLabel: { fontSize: 9 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: t("charts.divergence.price"),
          type: "line",
          smooth: true,
          yAxisIndex: 0,
          data: priceData,
          lineStyle: { width: 2, color: HUNTER_COLORS.bullish },
          itemStyle: { color: HUNTER_COLORS.bullish },
          showSymbol: false,
          markArea: divergenceAreas.length > 0 ? { data: divergenceAreas, silent: true } : undefined,
        },
        {
          name: t("charts.divergence.short"),
          type: "line",
          smooth: true,
          yAxisIndex: 1,
          data: shortData,
          lineStyle: {
            width: 1.5,
            type: "dashed",
            color: HUNTER_COLORS.divergence,
          },
          itemStyle: { color: HUNTER_COLORS.divergence },
          showSymbol: false,
        },
      ],
    };
  }, [data, t]);

  const { containerRef } = useECharts(option, [data]);

  if (isLoading) return <SkeletonChart className={className} height={240} />;
  if (!data || data.length < 2) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.divergence.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[240px]"}
      role="img"
      aria-label={t("charts.divergence.ariaLabel")}
    />
  );
}
