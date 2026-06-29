/**
 * FE-121: Short Iceberg V2 — 做空水位冰山图(双层堆叠面积图)
 *
 * ECharts stacked area:
 * - 上层浅红:全市场 Short Ratio
 * - 下层深红:ATS 暗池占比
 * - Tooltip 含 Z-Score
 * - 对接 short-iceberg-v2 端点
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useECharts, type EChartsOptionLoose } from "./useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart } from "@/components/common/Skeleton";

export interface ShortIcebergPoint {
  trade_date: string;
  short_ratio: number;
  ats_short_pct: number | null;
  z_score_60d: number | null;
  data_warmup: boolean;
}

export interface ShortIcebergV2Props {
  series: ShortIcebergPoint[] | undefined;
  isLoading?: boolean;
  className?: string;
}

export function ShortIcebergV2({
  series,
  isLoading,
  className,
}: ShortIcebergV2Props) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!series || series.length < 2) return null;

    const sorted = [...series].sort((a, b) =>
      a.trade_date.localeCompare(b.trade_date),
    );

    const dates = sorted.map((s) => s.trade_date.slice(5));
    const shortData = sorted.map((s) => s.short_ratio);
    const atsData = sorted.map((s) => s.ats_short_pct ?? 0);

    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const arr = params as Array<{
            dataIndex: number;
            seriesName: string;
            value: number;
          }>;
          if (!arr || arr.length === 0) return "";
          const idx = arr[0].dataIndex;
          const s = sorted[idx];
          if (!s) return "";
          return [
            `<b>${s.trade_date}</b>`,
            `${t("charts.iceberg.shortRatio")}: <b>${(s.short_ratio * 100).toFixed(2)}%</b>`,
            `${t("charts.iceberg.atsPct")}: <b>${s.ats_short_pct !== null ? (s.ats_short_pct * 100).toFixed(2) + "%" : "—"}</b>`,
            `Z-Score: <b>${s.z_score_60d !== null ? s.z_score_60d.toFixed(2) : "—"}</b>`,
            s.data_warmup ? `<span style="color:${HUNTER_COLORS.yellow}">${t("common.warmup")}</span>` : "",
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      legend: {
        data: [
          t("charts.iceberg.shortRatio"),
          t("charts.iceberg.atsPct"),
        ],
        top: 0,
      },
      grid: { left: 50, right: 15, top: 30, bottom: 25 },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLabel: {
          interval: Math.floor(sorted.length / 4),
          fontSize: 9,
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: (v: number) => (v * 100).toFixed(0) + "%",
          fontSize: 9,
        },
      },
      series: [
        {
          name: t("charts.iceberg.shortRatio"),
          type: "line",
          stack: "iceberg",
          smooth: true,
          data: shortData,
          areaStyle: {
            color: `rgba(${hexToRgb(HUNTER_COLORS.shortRed)}, 0.3)`,
          },
          lineStyle: { color: HUNTER_COLORS.shortRed, width: 1.5 },
          itemStyle: { color: HUNTER_COLORS.shortRed },
          showSymbol: false,
        },
        {
          name: t("charts.iceberg.atsPct"),
          type: "line",
          stack: "iceberg",
          smooth: true,
          data: atsData,
          areaStyle: {
            color: `rgba(${hexToRgb(HUNTER_COLORS.atsRed)}, 0.5)`,
          },
          lineStyle: { color: HUNTER_COLORS.atsRed, width: 1.5 },
          itemStyle: { color: HUNTER_COLORS.atsRed },
          showSymbol: false,
        },
      ],
    };
  }, [series, t]);

  const { containerRef } = useECharts(option, [series]);

  if (isLoading) return <SkeletonChart className={className} height={240} />;
  if (!series || series.length < 2) {
    return (
      <div className={`flex items-center justify-center text-xs text-slate-500 bg-slate-900/50 rounded p-4 ${className || ""}`}>
        {t("charts.iceberg.noData")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className || "w-full h-[240px]"}
      role="img"
      aria-label={t("charts.iceberg.ariaLabel")}
    />
  );
}

/** #RRGGBB → "R, G, B" for rgba() */
function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r}, ${g}, ${b}`;
}
