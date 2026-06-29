/**
 * FE-110: 骨架屏组件(SkeletonChart / SkeletonTable / SkeletonCard)
 *
 * 三种骨架变体,替代全屏 Spinner。
 * - 微弱呼吸动画
 * - 尊重 prefers-reduced-motion
 * - Tailwind animate-pulse 实现
 */
import { usePrefersReducedMotion } from "@/features/usePrefersReducedMotion";

const PULSE = "animate-pulse";

interface SkeletonBaseProps {
  className?: string;
  /** aria 描述,用于屏幕阅读器 */
  ariaLabel?: string;
}

function useAnimation(): string {
  const prefersReduced = usePrefersReducedMotion();
  return prefersReduced ? "" : PULSE;
}

/** 图表骨架:一个宽矩形 + 底部两条短文本线 */
export function SkeletonChart({
  className = "",
  ariaLabel = "chart-loading",
  height = 200,
}: SkeletonBaseProps & { height?: number }) {
  const anim = useAnimation();
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      className={`rounded border border-slate-800 bg-slate-900 p-4 ${className}`}
    >
      <div
        className={`w-full rounded bg-slate-800 ${anim}`}
        style={{ height }}
      />
      <div className="mt-3 flex gap-2">
        <div className={`h-2.5 w-16 rounded bg-slate-800 ${anim}`} />
        <div className={`h-2.5 w-10 rounded bg-slate-800 ${anim}`} />
      </div>
    </div>
  );
}

/** 表格骨架:N 行 × 4 列 */
export function SkeletonTable({
  className = "",
  ariaLabel = "table-loading",
  rows = 6,
  cols = 4,
}: SkeletonBaseProps & { rows?: number; cols?: number }) {
  const anim = useAnimation();
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      className={`rounded border border-slate-800 bg-slate-900 p-4 ${className}`}
    >
      {/* 表头 */}
      <div className="mb-3 flex gap-4 border-b border-slate-800 pb-2">
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={i}
            className={`h-3 flex-1 rounded bg-slate-700 ${anim}`}
          />
        ))}
      </div>
      {/* 行 */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="mb-2 flex gap-4">
          {Array.from({ length: cols }).map((__, c) => (
            <div
              key={c}
              className={`h-2.5 flex-1 rounded bg-slate-800 ${anim}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** 卡片骨架:图标位 + 标题 + 两行文本 */
export function SkeletonCard({
  className = "",
  ariaLabel = "card-loading",
}: SkeletonBaseProps) {
  const anim = useAnimation();
  return (
    <div
      role="status"
      aria-label={ariaLabel}
      className={`rounded border border-slate-800 bg-slate-900 p-4 ${className}`}
    >
      <div className="mb-3 flex items-center gap-3">
        <div className={`h-8 w-8 rounded-full bg-slate-800 ${anim}`} />
        <div className={`h-3 w-24 rounded bg-slate-800 ${anim}`} />
      </div>
      <div className="space-y-2">
        <div className={`h-2.5 w-full rounded bg-slate-800 ${anim}`} />
        <div className={`h-2.5 w-3/4 rounded bg-slate-800 ${anim}`} />
      </div>
    </div>
  );
}
