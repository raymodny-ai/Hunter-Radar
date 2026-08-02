import type { JSX } from "react";

/**
 * 4.3 模块贡献分解 (ModuleBreakdown)
 *
 * 展示 threat score 的 4 个模块贡献条 + 权重 + 质量标记 ⚠。
 * 数据来自 explain 端点 (module_scores / weights / module_quality)。
 *
 * 规则:
 * - 质量非 complete 的模块显示 ⚠ (degraded / missing)
 * - score 为 null 显示 "—" 且不渲染进度条
 * - 严禁捏造缺失模块的分值
 */

export interface ModuleInfo {
  score: number | null;
  weight: number;
  quality?: string; // complete | degraded | missing
}

const LABELS: Record<string, string> = {
  options: "期权异常",
  short: "做空压力",
  divergence: "量价背离",
  insider: "内部人交易",
};

/** 模块分 → 进度条颜色 (与 ThreatScoreGauge 一致的语义) */
function scoreColor(score: number): string {
  if (score >= 75) return "bg-red-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-slate-500";
}

export function ModuleBreakdown({
  modules,
}: {
  modules: Record<string, ModuleInfo>;
}): JSX.Element {
  return (
    <div className="space-y-2">
      {Object.entries(modules).map(([key, m]) => {
        const label = LABELS[key] ?? key;
        const width = m.score != null ? Math.min(100, m.score * m.weight) : 0;
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="w-20 text-sm text-slate-400">{label}</span>
            <div className="flex-1 h-3 bg-slate-800 rounded overflow-hidden">
              {m.score != null && (
                <div
                  className={`h-full rounded ${scoreColor(m.score)}`}
                  style={{ width: `${width}%` }}
                  title={`${label}: ${m.score.toFixed(0)} (权重 ${(m.weight * 100).toFixed(0)}%)`}
                />
              )}
            </div>
            <span className="w-10 text-right text-sm text-slate-200">
              {m.score != null ? m.score.toFixed(0) : "—"}
            </span>
            {m.quality && m.quality !== "complete" && (
              <span
                className={`text-xs ${m.quality === "missing" ? "text-red-400" : "text-amber-400"}`}
                title={m.quality === "missing" ? "该模块数据缺失" : "该模块数据降级"}
              >
                ⚠
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
