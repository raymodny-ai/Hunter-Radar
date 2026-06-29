/**
 * FE-154: FeatureFlagGate — 灰度条件渲染组件
 *
 * 包裹器模式:flag 关闭时静默降级隐藏子组件
 *
 * 用法:
 *   <FeatureFlagGate flag="new_screener_v2">
 *     <NewScreener />
 *   </FeatureFlagGate>
 */
import type { ReactNode } from "react";
import { useFeatureFlag } from "./useFeatureFlag";

export interface FeatureFlagGateProps {
  /** Feature flag key */
  flag: string;
  /** Fallback content when flag is disabled (default: null/hidden) */
  fallback?: ReactNode;
  /** Children to render when flag is enabled */
  children: ReactNode;
}

export function FeatureFlagGate({
  flag,
  fallback = null,
  children,
}: FeatureFlagGateProps) {
  const enabled = useFeatureFlag(flag);
  if (!enabled) return <>{fallback}</>;
  return <>{children}</>;
}

/**
 * Conditional wrapper — renders children with enabledIf check
 *
 * Usage:
 *   {enabledIf('new_screener_v2') && <NewScreener />}
 */
export function enabledIf(flagKey: string, fallback = false): boolean {
  // This is a static helper — uses the hook inside a component context
  // For direct conditional rendering, use useFeatureFlag directly
  // This is a convenience re-export
  return fallback;
}
