/**
 * FE-120: Options Anomaly Heatmap — 期权异常合约热力表
 *
 * 表格形式(非 ECharts 热力图,更适合合约明细展示):
 * - 仅展示活跃合约(零交易量已过滤)
 * - DTE≤3 且 OTM>10% 的末日 Put 红色高亮
 * - Vol/OI ≥ 5x 闪烁光晕
 * - 按 Vol/OI 排序
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { SkeletonTable } from "@/components/common/Skeleton";

export interface OptionsContract {
  contract: string;
  dte: number;
  oi_increase_pct: number;
  volume_oi_ratio: number;
  notional: number;
  is_top10_notional: boolean;
  oi_5d_series: number[];
  has_known_catalyst: boolean;
}

export interface OptionsHeatmapProps {
  contracts: OptionsContract[] | undefined;
  isLoading?: boolean;
  className?: string;
}

type SortKey = "volume_oi_ratio" | "dte" | "notional" | "oi_increase_pct";

export function OptionsHeatmap({
  contracts,
  isLoading,
  className,
}: OptionsHeatmapProps) {
  const { t } = useTranslation();
  const [sortKey, setSortKey] = useState<SortKey>("volume_oi_ratio");
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    if (!contracts) return [];
    return [...contracts].sort((a, b) => {
      const diff = a[sortKey] - b[sortKey];
      return sortAsc ? diff : -diff;
    });
  }, [contracts, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  if (isLoading) return <SkeletonTable className={className} rows={5} />;
  if (!contracts || contracts.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.options.noData")}
      </div>
    );
  }

  const SortIcon = ({ active, asc }: { active: boolean; asc: boolean }) => (
    <span className="text-[10px] ml-0.5 opacity-50">
      {active ? (asc ? "▲" : "▼") : "⇅"}
    </span>
  );

  return (
    <div className={`overflow-x-auto ${className || ""}`}>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800 text-left">
            <th className="py-1.5 px-2">{t("charts.options.contract")}</th>
            <th
              className="py-1.5 px-2 cursor-pointer select-none"
              onClick={() => toggleSort("dte")}
            >
              DTE <SortIcon active={sortKey === "dte"} asc={sortAsc} />
            </th>
            <th className="py-1.5 px-2">OI Δ%</th>
            <th
              className="py-1.5 px-2 cursor-pointer select-none"
              onClick={() => toggleSort("volume_oi_ratio")}
            >
              Vol/OI <SortIcon active={sortKey === "volume_oi_ratio"} asc={sortAsc} />
            </th>
            <th
              className="py-1.5 px-2 cursor-pointer select-none"
              onClick={() => toggleSort("notional")}
            >
              {t("charts.options.notional")} <SortIcon active={sortKey === "notional"} asc={sortAsc} />
            </th>
            <th className="py-1.5 px-2">{t("charts.options.flags")}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const isDoomPut = c.dte <= 3 && c.oi_increase_pct > 10;
            const isHighVolOi = c.volume_oi_ratio >= 5;
            const rowClass = isDoomPut
              ? "bg-red-950/30 border-l-2 border-l-red-500"
              : "";

            return (
              <tr
                key={c.contract}
                className={`border-b border-slate-800/30 hover:bg-slate-800/30 ${rowClass}`}
              >
                <td className="py-1.5 px-2 font-mono text-slate-300 truncate max-w-[140px]">
                  {c.contract}
                </td>
                <td
                  className={`py-1.5 px-2 font-mono ${isDoomPut ? "text-red-400 font-bold" : "text-slate-400"}`}
                >
                  {c.dte}
                </td>
                <td className="py-1.5 px-2 font-mono text-slate-400">
                  {c.oi_increase_pct > 0 ? "+" : ""}
                  {c.oi_increase_pct.toFixed(0)}%
                </td>
                <td
                  className={`py-1.5 px-2 font-mono font-bold ${
                    isHighVolOi
                      ? "text-amber-300 animate-pulse"
                      : "text-slate-300"
                  }`}
                >
                  {c.volume_oi_ratio.toFixed(1)}x
                </td>
                <td className="py-1.5 px-2 font-mono text-slate-400">
                  ${(c.notional / 1e6).toFixed(1)}M
                </td>
                <td className="py-1.5 px-2">
                  <div className="flex gap-1">
                    {c.is_top10_notional && (
                      <span className="px-1 py-0.5 rounded bg-amber-900/30 border border-amber-800/50 text-amber-400 text-[10px]">
                        Top10
                      </span>
                    )}
                    {isDoomPut && (
                      <span className="px-1 py-0.5 rounded bg-red-900/30 border border-red-800/50 text-red-400 text-[10px]">
                        {t("charts.options.doomPut")}
                      </span>
                    )}
                    {c.has_known_catalyst && (
                      <span className="px-1 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 text-[10px]">
                        {t("charts.options.catalyst")}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
