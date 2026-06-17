type Lifecycle = "init" | "red" | "yellow" | "gray" | "green";

interface SignalLifecycleBadgeProps {
  lifecycle: Lifecycle;
  consecutiveDays?: number;
  emaScore: number;
  threshold: number;
}

const lifecycleText: Record<Lifecycle, string> = {
  init: "数据初始化中",
  red: "红灯 — 终极警报",
  yellow: "黄灯 — 警惕",
  gray: "灰灯 — 中性",
  green: "绿灯 — 健康",
};

const lifecycleColor: Record<Lifecycle, string> = {
  init: "bg-slate-700 text-slate-300",
  red: "bg-hunter-red/20 text-hunter-red border-hunter-red/40",
  yellow: "bg-hunter-yellow/20 text-hunter-yellow border-hunter-yellow/40",
  gray: "bg-hunter-gray/20 text-hunter-gray border-hunter-gray/40",
  green: "bg-hunter-green/20 text-hunter-green border-hunter-green/40",
};

/** 信号生命周期徽章(FE-030 / BD-062 / OQ-02)。
 *
 * 严格规则:
 * 1. 连续 ≥2 交易日高分(OQ-02 决策)才升级到 red
 * 2. 显示 EMA 后总分(不是 raw)
 * 3. 5 态(init/red/yellow/gray/green)严格按 services.threat_score.decide_lifecycle
 */
export function SignalLifecycleBadge({
  lifecycle,
  consecutiveDays = 0,
  emaScore,
  threshold,
}: SignalLifecycleBadgeProps) {
  const aboveThreshold = emaScore >= threshold;
  const daysText =
    consecutiveDays > 0
      ? `连续 ${consecutiveDays} 个交易日${aboveThreshold ? "高于阈值" : ""}`
      : "无连续触发";

  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1 rounded border ${lifecycleColor[lifecycle]}`}
      role="status"
      aria-label={`信号状态 ${lifecycleText[lifecycle]},${daysText}`}
    >
      <span className="text-xs font-medium">{lifecycleText[lifecycle]}</span>
      <span className="text-xs font-mono opacity-75">
        {emaScore.toFixed(0)} / {threshold}
      </span>
      {consecutiveDays >= 2 && (
        <span className="text-xs font-mono bg-slate-900/40 px-1.5 py-0.5 rounded">
          ×{consecutiveDays}d
        </span>
      )}
    </div>
  );
}
