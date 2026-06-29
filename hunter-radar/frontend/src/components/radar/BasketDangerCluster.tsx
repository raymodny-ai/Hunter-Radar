/**
 * FE-136: BasketDangerCluster — 危险聚集提示
 *
 * 当连续 ≥3 个成员 Threat Score ≥ 70 时,自动弹出红色警告横幅。
 * 显示高危成员列表和平均分。
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { BasketDistributionDTO } from "@/lib/api";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";

export interface BasketDangerClusterProps {
  distribution: BasketDistributionDTO | null | undefined;
  /** 阈值,默认 70 */
  threshold?: number;
  /** 最少连续个数,默认 3 */
  minCount?: number;
  className?: string;
}

export function BasketDangerCluster({
  distribution,
  threshold = 70,
  minCount = 3,
  className,
}: BasketDangerClusterProps) {
  const { t } = useTranslation();

  const cluster = useMemo(() => {
    if (!distribution || distribution.by_ticker.length === 0) return null;

    const highRisk = distribution.by_ticker
      .filter((b) => b.latest !== null && b.latest >= threshold)
      .sort((a, b) => (b.latest ?? 0) - (a.latest ?? 0));

    if (highRisk.length < minCount) return null;

    const avgScore =
      highRisk.reduce((sum, b) => sum + (b.latest ?? 0), 0) / highRisk.length;

    return { members: highRisk, avgScore };
  }, [distribution, threshold, minCount]);

  if (!cluster) return null;

  return (
    <div
      className={`rounded-lg border p-3 ${className || ""}`}
      style={{
        borderColor: HUNTER_COLORS.red,
        backgroundColor: "rgba(255, 82, 82, 0.08)",
      }}
      role="alert"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">⚠</span>
        <span className="font-semibold text-sm" style={{ color: HUNTER_COLORS.red }}>
          {t("basket.dangerCluster.title")}
        </span>
        <span className="text-xs text-slate-400">
          ({cluster.members.length} {t("basket.dangerCluster.membersAbove", { threshold })})
        </span>
      </div>
      <div className="text-xs text-slate-300 mb-2">
        {t("basket.dangerCluster.avgScore")}:{" "}
        <span className="font-mono font-bold" style={{ color: HUNTER_COLORS.red }}>
          {cluster.avgScore.toFixed(1)}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {cluster.members.map((m) => (
          <span
            key={m.ticker}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-mono"
            style={{ backgroundColor: "rgba(255, 82, 82, 0.15)", color: HUNTER_COLORS.red }}
          >
            {m.ticker}
            <span className="text-[10px] opacity-70">{m.latest?.toFixed(0)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
