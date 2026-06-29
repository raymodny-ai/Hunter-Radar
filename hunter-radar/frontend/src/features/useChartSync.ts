/**
 * FE-125: 跨图表十字光标同步
 *
 * 通过 echarts.connect(groupName) 实现:
 * - 所有同组图表共享 axisPointer
 * - dataZoom + highlight 事件 16ms 内同步
 * - Zustand 消息总线作为备选方案
 *
 * 使用方式:
 *   useChartSync(chartRef, "symbol-detail");
 */
import { useEffect, useRef } from "react";
import type { EChartsType } from "echarts/core";
import { echarts } from "@/lib/echarts-setup";

/**
 * 将 ECharts 实例加入同步组
 * @param chartRef ECharts 实例 ref
 * @param group 组名(同一页面共享同一组名)
 */
export function useChartSync(
  chartRef: React.RefObject<EChartsType | null>,
  group: string,
): void {
  const groupRef = useRef(group);
  groupRef.current = group;

  useEffect(() => {
    const instance = chartRef.current;
    if (!instance) return;

    // 加入 connect 组
    instance.group = groupRef.current;
    echarts.connect(groupRef.current);

    return () => {
      // 清理:取消连接(实例 dispose 时自动清理)
      try {
        echarts.disconnect(groupRef.current);
      } catch {
        // 忽略:实例可能已 dispose
      }
    };
  }, [chartRef]);
}

/**
 * 批量同步多个图表实例(非 Hook 版本,用于 imperative 场景)
 */
export function syncChartGroup(instances: (EChartsType | null | undefined)[], group: string): void {
  for (const inst of instances) {
    if (inst) {
      inst.group = group;
    }
  }
  echarts.connect(group);
}
