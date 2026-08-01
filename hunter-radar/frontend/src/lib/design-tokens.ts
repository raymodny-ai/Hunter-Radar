/**
 * PRD Appendix A: Design Token Reference
 *
 * 威胁分色阶 / Regime 色彩 / 模块色彩 — 全局统一引用点。
 */

// ── Threat score severity ───────────────────────────────
export const THREAT_COLORS = {
  low: "#22c55e", // 0-30
  medium: "#eab308", // 31-60
  high: "#f97316", // 61-80
  critical: "#ef4444", // 81-100
} as const;

/** 根据 threat score 返回对应色阶颜色 */
export function threatScoreColor(score: number): string {
  if (score >= 81) return THREAT_COLORS.critical;
  if (score >= 61) return THREAT_COLORS.high;
  if (score >= 31) return THREAT_COLORS.medium;
  return THREAT_COLORS.low;
}

/** 返回色阶级别名称 */
export function threatScoreLevel(score: number): "low" | "medium" | "high" | "critical" {
  if (score >= 81) return "critical";
  if (score >= 61) return "high";
  if (score >= 31) return "medium";
  return "low";
}

// ── Regime ──────────────────────────────────────────────
export const REGIME_COLORS = {
  riskOn: "#22c55e",
  neutral: "#eab308",
  riskOff: "#ef4444",
} as const;

// ── Module colors (PRD Appendix A) ─────────────────────
export const MODULE_COLORS = {
  options: "#8b5cf6",
  short: "#06b6d4",
  divergence: "#f59e0b",
  insider: "#ec4899",
} as const;

export type ModuleKey = keyof typeof MODULE_COLORS;

export const MODULE_KEYS: ModuleKey[] = ["options", "short", "divergence", "insider"];
