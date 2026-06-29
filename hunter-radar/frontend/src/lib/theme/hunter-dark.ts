/**
 * FE-111: ECharts 暗黑主题注册 — hunter-dark
 *
 * PRD §4.1: 深度暗黑主题与色彩编码学
 * - 背景 #131722
 * - 网格线 #363A45
 * - 多头信号 #2196F3(冷蓝)
 * - 威胁红 #FF5252 / 品红 #E040FB
 * - 通过 echarts.registerTheme 全局注册
 *
 * 必须在 ECharts 首次使用前调用 registerHunterTheme()。
 */
import * as echarts from "echarts/core";

/** 全局色彩语义常量,供图表组件直接引用 */
export const HUNTER_COLORS = {
  /** 背景基色 */
  bg: "#131722",
  /** 模块面板背景 */
  panelBg: "#1a1e2e",
  /** 网格线 / 分割线 */
  grid: "#363A45",
  /** 文本主色 */
  textPrimary: "#e2e8f0",
  /** 文本次要色 */
  textSecondary: "#94a3b8",
  /** 文本禁用色 */
  textMuted: "#64748b",

  // ── 数据语义色谱 ──────────────────────────────
  /** 多头 / 安全 / 常态 */
  bullish: "#2196F3",
  /** 绿:健康 */
  green: "#10b981",
  /** 黄:警惕 */
  yellow: "#f59e0b",
  /** 橙:中度威胁 */
  orange: "#fb923c",
  /** 红:高威胁 / 异常 */
  red: "#FF5252",
  /** 品红:极端威胁 / 机构抛售 */
  magenta: "#E040FB",
  /** 深红:暗池做空 */
  atsRed: "#b91c1c",
  /** 浅红:全市场做空 */
  shortRed: "#ef4444",

  // ── 四模块色 ──────────────────────────────────
  /** 期权异常 */
  options: "#f97316",
  /** 做空追踪 */
  short: "#ef4444",
  /** 量价背离 */
  divergence: "#a855f7",
  /** SEC 内部行为 */
  insider: "#06b6d4",
} as const;

export type HunterColorKey = keyof typeof HUNTER_COLORS;

/** 注册 hunter-dark 主题到全局 ECharts */
export function registerHunterTheme(): void {
  echarts.registerTheme("hunter-dark", {
    color: [
      HUNTER_COLORS.bullish,
      HUNTER_COLORS.red,
      HUNTER_COLORS.yellow,
      HUNTER_COLORS.magenta,
      HUNTER_COLORS.green,
      HUNTER_COLORS.orange,
      HUNTER_COLORS.insider,
      HUNTER_COLORS.divergence,
    ],
    backgroundColor: "transparent",
    textStyle: {
      color: HUNTER_COLORS.textSecondary,
    },
    title: {
      textStyle: { color: HUNTER_COLORS.textPrimary },
      subtextStyle: { color: HUNTER_COLORS.textMuted },
    },
    legend: {
      textStyle: { color: HUNTER_COLORS.textSecondary },
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: HUNTER_COLORS.grid } },
      axisTick: { lineStyle: { color: HUNTER_COLORS.grid } },
      axisLabel: { color: HUNTER_COLORS.textMuted },
      splitLine: { lineStyle: { color: HUNTER_COLORS.grid, type: "dashed" as const } },
    },
    valueAxis: {
      axisLine: { lineStyle: { color: HUNTER_COLORS.grid } },
      axisTick: { lineStyle: { color: HUNTER_COLORS.grid } },
      axisLabel: { color: HUNTER_COLORS.textMuted },
      splitLine: { lineStyle: { color: HUNTER_COLORS.grid, type: "dashed" as const } },
    },
    tooltip: {
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: HUNTER_COLORS.grid,
      textStyle: { color: HUNTER_COLORS.textPrimary, fontSize: 12 },
    },
    dataZoom: {
      handleStyle: { color: HUNTER_COLORS.bullish },
      textStyle: { color: HUNTER_COLORS.textMuted },
      borderColor: HUNTER_COLORS.grid,
    },
  });
}

/** 获取 ECharts 实例时必须指定主题 */
export const HUNTER_THEME_NAME = "hunter-dark";
