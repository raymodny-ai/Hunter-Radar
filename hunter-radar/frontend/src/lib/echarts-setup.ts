/**
 * M2 共享 ECharts 依赖注册(tree-shaking)
 *
 * 所有图表组件通过此文件引入 echarts,
 * 确保仅打包使用到的模块,避免全量引入(~800KB)。
 *
 * 使用方式:
 *   import { echarts } from "@/lib/echarts-setup";
 */
import * as echarts from "echarts/core";

// ── 图表类型 ──────────────────────────────────
import { BarChart } from "echarts/charts";
import { LineChart } from "echarts/charts";
import { RadarChart } from "echarts/charts";
import { HeatmapChart } from "echarts/charts";
import { ScatterChart } from "echarts/charts";
import { CustomChart } from "echarts/charts";

// ── 组件 ──────────────────────────────────────
import { GridComponent } from "echarts/components";
import { TooltipComponent } from "echarts/components";
import { LegendComponent } from "echarts/components";
import { DataZoomComponent } from "echarts/components";
import { MarkLineComponent } from "echarts/components";
import { MarkAreaComponent } from "echarts/components";
import { MarkPointComponent } from "echarts/components";
import { VisualMapComponent } from "echarts/components";
import { AxisPointerComponent } from "echarts/components";
import { ToolboxComponent } from "echarts/components";
import { TitleComponent } from "echarts/components";

// ── 渲染器 ────────────────────────────────────
import { CanvasRenderer } from "echarts/renderers";

// 批量注册
echarts.use([
  BarChart,
  LineChart,
  RadarChart,
  HeatmapChart,
  ScatterChart,
  CustomChart,

  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
  MarkPointComponent,
  VisualMapComponent,
  AxisPointerComponent,
  ToolboxComponent,
  TitleComponent,

  CanvasRenderer,
]);

export { echarts };
