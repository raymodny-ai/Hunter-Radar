/**
 * FE-126: ECharts large 模式 + Data Decimation
 *
 * 提供 large 模式配置辅助:
 * - large: true 默认开启
 * - >5000 数据点时帧率 ≥ 30FPS
 * - sampling: 'lttb'( Largest-Triangle-Three-Buckets 降采样)
 * - animation: false 大数据集禁用动画
 */

export interface LargeModeOptions {
  /** 是否启用 large 模式(默认 true) */
  enabled?: boolean;
  /** 数据点阈值,超过时自动启用(默认 5000) */
  threshold?: number;
  /** 降采样策略(默认 lttb) */
  sampling?: "lttb" | "average" | "max" | "min" | "sum" | "none";
}

const DEFAULTS: Required<LargeModeOptions> = {
  enabled: true,
  threshold: 5000,
  sampling: "lttb",
};

/**
 * 根据数据量返回 ECharts 性能优化配置片段
 * 合并到 series 配置中
 */
export function getLargeModeConfig(
  dataLength: number,
  opts?: LargeModeOptions,
): Record<string, unknown> {
  const config = { ...DEFAULTS, ...opts };

  if (!config.enabled || dataLength < config.threshold) {
    return {};
  }

  return {
    large: true,
    largeThreshold: config.threshold,
    sampling: config.sampling,
    animation: false,
    progressive: 500,
    progressiveThreshold: config.threshold,
  };
}

/**
 * 获取 WebGL renderer 配置(帧率跌破时降级)
 * 需要 echarts-gl 扩展,当前仅返回配置提示
 */
export function getWebGLFallbackHint(): { renderer: "canvas" | "svg" } {
  // 当前使用 Canvas renderer,如果性能不足可切换 SVG
  return { renderer: "canvas" };
}
