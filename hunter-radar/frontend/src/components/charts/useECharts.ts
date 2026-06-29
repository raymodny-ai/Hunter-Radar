/**
 * M2 共享 ECharts Hook — useECharts
 *
 * 封装 ECharts 实例生命周期:
 * - useRef 持有 DOM 容器
 * - useEffect init → setOption → cleanup dispose()
 * - window resize 自适应
 * - 主题固定 hunter-dark
 *
 * 使用方式:
 *   const { chartRef, containerRef } = useECharts(option);
 */
import { useRef, useEffect, type RefObject, type MutableRefObject } from "react";
import type { EChartsType } from "echarts/core";
import type { SetOptionOpts } from "echarts";
import { echarts } from "@/lib/echarts-setup";
import { HUNTER_THEME_NAME } from "@/lib/theme/hunter-dark";

/** ECharts option 宽松类型,避免严格类型推断问题 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type EChartsOptionLoose = Record<string, any>;

export interface UseEChartsReturn {
  /** 挂载到图表容器 div */
  containerRef: MutableRefObject<HTMLDivElement | null>;
  /** ECharts 实例(可能为 null) */
  chartRef: MutableRefObject<EChartsType | null>;
}

/**
 * 初始化并管理 ECharts 实例
 * @param option 图表配置(变化时自动 setOption)
 * @param deps 额外依赖数组,变化时重新 setOption
 */
export function useECharts(
  option: EChartsOptionLoose | null | undefined,
  deps: unknown[] = [],
): UseEChartsReturn {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);

  // 初始化 + resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const instance = echarts.init(el, HUNTER_THEME_NAME, {
      renderer: "canvas",
    });
    chartRef.current = instance;

    const onResize = () => instance.resize();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      instance.dispose();
      chartRef.current = null;
    };
  }, []);

  // option 变更时更新
  useEffect(() => {
    if (!chartRef.current || !option) return;
    const opts: SetOptionOpts = { notMerge: true };
    chartRef.current.setOption(option, opts);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [option, ...deps]);

  return { containerRef, chartRef };
}
