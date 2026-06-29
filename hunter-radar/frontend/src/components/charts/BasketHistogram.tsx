/**
 * FE-135: BasketHistogram — 篮子分布直方图
 *
 * ECharts 柱状图:
 * - 横轴:Threat Score 分段(0-10, 10-20, ..., 90-100)
 * - 纵轴:标的数量
 * - 阈值线:70(黄)/80(红) markLine
 * - 对接 /baskets/{id}/distribution 数据(by_ticker.latest)
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";
import type { BasketDistributionDTO } from "@/lib/api";

export interface BasketHistogramProps {
  distribution: BasketDistributionDTO | null | undefined;
  isLoading?: boolean;
  className?: string;
}

/** 构建 10 段直方图 bin */
function buildBins(scores: number[]): { labels: string[]; counts: number[] } {
  const bins = Array.from({ length: 10 }, () => 0);
  for (const s of scores) {
    const idx = Math.min(Math.floor(s / 10), 9);
    bins[idx]++;
  }
  const labels = Array.from({ length: 10 }, (_, i) => `${i * 10}-${(i + 1) * 10}`);
  return { labels, counts: bins };
}

export function BasketHistogram({
  distribution,
  isLoading,
  className,
}: BasketHistogramProps) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!distribution || distribution.by_ticker.length === 0) return null;

    const scores = distribution.by_ticker
      .map((b) => b.latest)
      .filter((v): v is number => v !== null);

    if (scores.length === 0) return null;

    const { labels, counts } = buildBins(scores);

    // 颜色:低于 50 绿,50-70 黄,70-80 橙,≥80 红
    const barColors = labels.map((_, i) => {
      if (i < 5) return HUNTER_COLORS.green;
      if (i < 7) return HUNTER_COLORS.yellow;
      if (i < 8) return HUNTER_COLORS.orange;
      return HUNTER_COLORS.red;
    });

    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: Array<{ name: string; value: number }>) => {
          const p = params[0];
          return `${p.name}<br/>${t("basket.histogram.count")}: <b>${p.value}</b>`;
        },
      },
      grid: { top: 20, right: 16, bottom: 30, left: 40 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { fontSize: 10, color: HUNTER_COLORS.textMuted },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { fontSize: 10, color: HUNTER_COLORS.textMuted },
      },
      series: [
        {
          type: "bar",
          data: counts.map((v, i) => ({
            value: v,
            itemStyle: { color: barColors[i] },
          })),
          barWidth: "70%",
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              {
                xAxis: "70-80",
                lineStyle: { color: HUNTER_COLORS.yellow, type: "dashed" },
                label: {
                  formatter: `${t("basket.histogram.threshold")} 70`,
                  color: HUNTER_COLORS.yellow,
                  fontSize: 10,
                },
              },
              {
                xAxis: "80-90",
                lineStyle: { color: HUNTER_COLORS.red, type: "dashed" },
                label: {
                  formatter: `${t("basket.histogram.threshold")} 80`,
                  color: HUNTER_COLORS.red,
                  fontSize: 10,
                },
              },
            ],
          },
        },
      ],
    };
  }, [distribution, t]);

  const { containerRef } = useECharts(option, [distribution]);

  if (isLoading) return <SkeletonChart className={className} height={200} />;

  if (!distribution || distribution.by_ticker.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("basket.histogram.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[200px]"}
      role="img"
      aria-label={t("basket.histogram.ariaLabel")}
    />
  );
}
