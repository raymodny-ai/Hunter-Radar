import { useEffect, useState } from "react";

/** §6.2 FE-070 检测 prefers-reduced-motion 用户偏好。
 *
 * 返回 true 时,前端应:
 * - 减少或省略装饰性动画(弹窗 fade-in、Threat History 补间)
 * - backdrop-blur/scale 动效改为静态
 * - 滚动 banner 不自动滚(用户主动滚)
 * - 图表/数字直接显示最终值,不做 tween
 *
 * 硬约束:
 * - SSR 友好:window 不存在时返 false(不影响 SSR 首屏)
 * - 监听 matchMedia change 事件,用户切换系统偏好后立即生效
 * - 静态导出函数(reduced)用于 Storybook / 单元测试 mock
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => readPrefers());

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    // 现代浏览器:addEventListener;老 fallback:addListener
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    // 兼容老 Safari
    const legacy = mq as unknown as {
      addListener: (cb: (e: MediaQueryListEvent) => void) => void;
      removeListener: (cb: (e: MediaQueryListEvent) => void) => void;
    };
    legacy.addListener(onChange);
    return () => legacy.removeListener(onChange);
  }, []);

  return reduced;
}

/** 同步读取(非 hook),供非组件上下文使用。 */
export function readPrefersReducedMotion(): boolean {
  return readPrefers();
}

function readPrefers(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/** 装饰器:把一个动画 class 字符串按 reduced 模式过滤掉 animate-* / transition-* */
export function reduceMotionClasses(
  classes: string,
  reduced: boolean,
): string {
  if (!reduced) return classes;
  return classes
    .split(/\s+/)
    .filter((c) => c && !/^(animate-|transition-)/.test(c))
    .join(" ");
}
