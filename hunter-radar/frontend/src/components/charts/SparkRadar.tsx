/**
 * FE-134: Spark-Radar — 微缩雷达图(去坐标轴)
 *
 * 4D 雷达图的微缩版,用于自选篮子卡片内嵌:
 * - 无坐标轴文本
 * - 紧凑尺寸(默认 80×80)
 * - 数据从 Threat Score 子模块获取
 */
import { useMemo } from "react";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";

export interface SparkRadarProps {
  moduleOptions: number | undefined;
  moduleShort: number | undefined;
  moduleDivergence: number | undefined;
  moduleInsider: number | undefined;
  /** 尺寸(px),默认 80 */
  size?: number;
  className?: string;
}

export function SparkRadar({
  moduleOptions,
  moduleShort,
  moduleDivergence,
  moduleInsider,
  size = 80,
  className,
}: SparkRadarProps) {
  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (
      moduleOptions === undefined ||
      moduleShort === undefined ||
      moduleDivergence === undefined ||
      moduleInsider === undefined
    )
      return null;

    const values = [moduleOptions, moduleShort, moduleDivergence, moduleInsider];
    const avg = values.reduce((a, b) => a + b, 0) / 4;
    const opacity = Math.min(0.7, avg / 100 * 0.6 + 0.1);

    return {
      // 隐藏 tooltip 节省空间
      tooltip: { show: false },
      radar: {
        indicator: [
          { name: "", max: 100 },
          { name: "", max: 100 },
          { name: "", max: 100 },
          { name: "", max: 100 },
        ],
        shape: "polygon",
        splitNumber: 2,
        center: ["50%", "50%"],
        radius: "75%",
        axisName: { show: false },
        axisLine: { lineStyle: { color: HUNTER_COLORS.grid, opacity: 0.4 } },
        splitLine: { lineStyle: { color: HUNTER_COLORS.grid, opacity: 0.3 } },
        splitArea: { show: false },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: values,
              symbol: "none",
              areaStyle: {
                color: `rgba(255, 82, 82, ${opacity})`,
              },
              lineStyle: {
                color: HUNTER_COLORS.red,
                width: 1.5,
              },
            },
          ],
        },
      ],
    };
  }, [moduleOptions, moduleShort, moduleDivergence, moduleInsider]);

  const { containerRef } = useECharts(option, [
    moduleOptions,
    moduleShort,
    moduleDivergence,
    moduleInsider,
  ]);

  return (
    <div
      ref={containerRef}
      style={{ width: size, height: size }}
      className={className || "shrink-0"}
      role="img"
      aria-label="Spark radar"
    />
  );
}
