/**
 * FE-118: 4D Signal Radar — 四维信号雷达图
 *
 * ECharts 极坐标雷达图:
 * - 四顶点:期权/做空/背离/内部人
 * - 半透明多边形面积填充
 * - 安全时收缩(分数低→面积小),风险时扩张
 * - 模块色与 LeftToolbar 一致
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";

export interface SignalRadarProps {
  moduleOptions: number | null | undefined;
  moduleShort: number | null | undefined;
  moduleDivergence: number | null | undefined;
  moduleInsider: number | null | undefined;
  isLoading?: boolean;
  className?: string;
}

export function SignalRadar({
  moduleOptions,
  moduleShort,
  moduleDivergence,
  moduleInsider,
  isLoading,
  className,
}: SignalRadarProps) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (
      moduleOptions == null ||
      moduleShort == null ||
      moduleDivergence == null ||
      moduleInsider == null
    )
      return null;

    const values = [moduleOptions, moduleShort, moduleDivergence, moduleInsider];
    const maxVal = 100;

    return {
      tooltip: {
        trigger: "item",
        formatter: () => {
          const labels = [
            t("modules.options"),
            t("modules.short"),
            t("modules.divergence"),
            t("modules.insider"),
          ];
          return labels
            .map((l, i) => `${l}: <b>${values[i].toFixed(1)}</b>`)
            .join("<br/>");
        },
      },
      radar: {
        indicator: [
          { name: t("modules.options"), max: maxVal, color: HUNTER_COLORS.options },
          { name: t("modules.short"), max: maxVal, color: HUNTER_COLORS.short },
          { name: t("modules.divergence"), max: maxVal, color: HUNTER_COLORS.divergence },
          { name: t("modules.insider"), max: maxVal, color: HUNTER_COLORS.insider },
        ],
        shape: "polygon",
        splitNumber: 4,
        axisName: { fontSize: 11 },
        splitLine: { lineStyle: { color: HUNTER_COLORS.grid } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: HUNTER_COLORS.grid } },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: values,
              name: t("charts.radar.signalArea"),
              areaStyle: {
                color: `rgba(255, 82, 82, ${Math.min(0.6, (values.reduce((a, b) => a + b, 0) / (4 * maxVal)) * 0.8 + 0.05)})`,
              },
              lineStyle: {
                color: HUNTER_COLORS.red,
                width: 2,
              },
              itemStyle: { color: HUNTER_COLORS.red },
              symbol: "circle",
              symbolSize: 5,
            },
          ],
        },
      ],
    };
  }, [moduleOptions, moduleShort, moduleDivergence, moduleInsider, t]);

  const { containerRef } = useECharts(option, [
    moduleOptions,
    moduleShort,
    moduleDivergence,
    moduleInsider,
  ]);

  if (isLoading) return <SkeletonChart className={className} height={260} />;
  if (moduleOptions === undefined) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.radar.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[260px]"}
      role="img"
      aria-label={t("charts.radar.ariaLabel")}
    />
  );
}
