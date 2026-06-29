/**
 * FE-144: useLongPress — 移动端图表触控长按唤醒十字光标
 *
 * < 768px 时禁用鼠标悬停,改为 long-press 激活十字光标:
 * - 长按 500ms 后触发
 * - 避免与页面滚动手势冲突
 * - 松手后自动关闭
 */
import { useRef, useCallback, useEffect } from "react";

export interface UseLongPressOptions {
  /** Long press duration in ms, default 500 */
  threshold?: number;
  /** Callback on long press start */
  onPress: (x: number, y: number) => void;
  /** Callback on long press end */
  onRelease?: () => void;
}

export function useLongPress({
  threshold = 500,
  onPress,
  onRelease,
}: UseLongPressOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLongPressRef = useRef(false);

  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      const touch = e.touches[0];
      const x = touch.clientX;
      const y = touch.clientY;

      timerRef.current = setTimeout(() => {
        isLongPressRef.current = true;
        onPress(x, y);
      }, threshold);
    },
    [onPress, threshold],
  );

  const handleTouchMove = useCallback(() => {
    // Cancel if finger moves (scrolling)
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (isLongPressRef.current) {
      isLongPressRef.current = false;
      onRelease?.();
    }
  }, [onRelease]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return {
    onTouchStart: handleTouchStart,
    onTouchMove: handleTouchMove,
    onTouchEnd: handleTouchEnd,
  };
}

/**
 * Check if current viewport is mobile (< 768px)
 */
export function isMobileViewport(): boolean {
  if (typeof window === "undefined") return false;
  return window.innerWidth < 768;
}
