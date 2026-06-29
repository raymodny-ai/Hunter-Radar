/**
 * FE-117: Attribution Waterfall — 威胁分贡献度瀑布图
 *
 * ECharts 水平瀑布图:
 * - 正向贡献(增风险):红色柱
 * - 负向贡献(降风险):绿色柱
 * - 总计:蓝色粗柱
 * - Tooltip 显示各模块绝对数值 + 权重 + 加权分
 *
 * 对接 /symbols/{ticker}/attribution 端点。
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";

export interface AttributionContribution {
  module: string;
  score: number;
  weight: number;
  weighted_score: number;
}

export interface AttributionWaterfallProps {
  contributions: AttributionContribution[] | undefined;
  total: number;
  isLoading?: boolean;
  className?: string;
}

const MODULE_I18N: Record<string, string> = {
  options: "modules.options",
  short: "modules.short",
  divergence: "modules.divergence",
  insider: "modules.insider",
};

const MODULE_COLOR: Record<string, string> = {
  options: HUNTER_COLORS.options,
  short: HUNTER_COLORS.short,
  divergence: HUNTER_COLORS.divergence,
  insider: HUNTER_COLORS.insider,
};

export function AttributionWaterfall({
  contributions,
  total,
  isLoading,
  className,
}: AttributionWaterfallProps) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!contributions || contributions.length === 0) return null;

    const sorted = [...contributions].sort(
      (a, b) => b.weighted_score - a.weighted_score,
    );

    const categories = [
      t("charts.attribution.total"),
      ...sorted.map((c) => t(MODULE_I18N[c.module] || c.module)),
    ];
    const values = [total, ...sorted.map((c) => c.weighted_score)];

    // 瀑布:透明基底 + 可见柱
    // 基底:使柱子从 0 开始向正/负延伸
    const baseData = values.map(() => 0);

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const p = (params as Array<{ dataIndex: number }>)[0];
          if (!p) return "";
          const idx = p.dataIndex;
          if (idx === 0) {
            return `<b>${t("charts.attribution.total")}</b><br/>${t("charts.attribution.threatScore")}: ${total.toFixed(1)}`;
          }
          const c = sorted[idx - 1];
          return [
            `<b>${t(MODULE_I18N[c.module] || c.module)}</b>`,
            `${t("charts.attribution.rawScore")}: ${c.score.toFixed(1)}`,
            `${t("charts.attribution.weight")}: ${(c.weight * 100).toFixed(0)}%`,
            `${t("charts.attribution.weighted")}: ${c.weighted_score.toFixed(1)}`,
          ].join("<br/>");
        },
      },
      grid: { left: 90, right: 20, top: 10, bottom: 20 },
      xAxis: {
        type: "value",
        axisLabel: { formatter: "{value}" },
      },
      yAxis: {
        type: "category",
        data: categories,
        inverse: true,
        axisLabel: { fontSize: 11 },
      },
      series: [
        {
          name: "base",
          type: "bar",
          stack: "waterfall",
          itemStyle: { color: "transparent" },
          emphasis: { itemStyle: { color: "transparent" } },
          data: baseData,
        },
        {
          name: "value",
          type: "bar",
          stack: "waterfall",
          barWidth: 20,
          data: values.map((v, i) => ({
            value: v,
            itemStyle: {
              color:
                i === 0
                  ? HUNTER_COLORS.bullish
                  : v > 0
                    ? MODULE_COLOR[sorted[i - 1]?.module] || HUNTER_COLORS.red
                    : HUNTER_COLORS.green,
              borderRadius: i === 0 ? 0 : v > 0 ? [0, 3, 3, 0] : [3, 0, 0, 3],
            },
          })),
          label: {
            show: true,
            position: "right",
            formatter: (p: { value: number }) => (p.value > 0 ? "+" : "") + p.value.toFixed(1),
            color: HUNTER_COLORS.textSecondary,
            fontSize: 10,
          },
        },
      ],
    };
  }, [contributions, total, t]);

  const { containerRef } = useECharts(option, [contributions, total]);

  if (isLoading) return <SkeletonChart className={className} height={220} />;
  if (!contributions || contributions.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.attribution.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[220px]"}
      role="img"
      aria-label={t("charts.attribution.ariaLabel")}
    />
  );
}
