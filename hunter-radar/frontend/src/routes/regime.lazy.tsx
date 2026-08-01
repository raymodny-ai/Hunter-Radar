/**
 * FE-130/131/132: 宏观环境总览页(Regime Overview)
 *
 * - FE-130: 路由 + 页面骨架
 * - FE-131: VIX/SPX 门控状态指示灯
 * - FE-132: Regime 切换时间轴(状态转移色块图, ECharts)
 */
import { createLazyRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { useECharts, type EChartsOptionLoose } from "@/components/charts/useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart, SkeletonCard } from "@/components/common/Skeleton";

export const Route = createLazyRoute("/regime")({
  component: RegimePage,
});

function RegimePage() {
  const { t } = useTranslation();

  const regime = useQuery({
    queryKey: ["regime"],
    queryFn: () => api.getRegime(),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  const timeline = useQuery({
    queryKey: ["regime-timeline"],
    queryFn: () => api.getRegimeTimeline(90),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // P3-02: Regime periods (consecutive runs) → duration + history table
  const periods = useMemo<RegimePeriod[]>(() => {
    const pts = timeline.data?.points ?? [];
    if (pts.length === 0) return [];
    const sorted = [...pts].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    const runs: RegimePeriod[] = [];
    let runStart = 0;
    for (let i = 1; i <= sorted.length; i++) {
      if (i === sorted.length || sorted[i].regime !== sorted[runStart].regime) {
        const slice = sorted.slice(runStart, i);
        const vixVals = slice
          .map((p) => p.vix)
          .filter((v): v is number => v !== null);
        runs.push({
          regime: sorted[runStart].regime,
          start: slice[0].trade_date,
          end: slice[slice.length - 1].trade_date,
          days: slice.length,
          avgVix: vixVals.length > 0 ? vixVals.reduce((a, b) => a + b, 0) / vixVals.length : null,
        });
        runStart = i;
      }
    }
    return runs.reverse(); // latest first
  }, [timeline.data]);
  const currentDuration = periods.length > 0 ? periods[0].days : null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{t("regime.page")}</h1>
        <p className="text-slate-400 text-sm mt-1">
          {t("regime.subtitle")}
        </p>
      </header>

      {/* FE-131: VIX/SPX 门控状态指示灯 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GatingCard
          title={t("regime.marketStatus")}
          regime={regime.data?.regime}
          isLoading={regime.isLoading}
        />
        <VixCard
          vix={regime.data?.vix}
          isLoading={regime.isLoading}
        />
        <SpxCard
          spxClose={regime.data?.spx_close}
          spxMa20={regime.data?.spx_ma20}
          isLoading={regime.isLoading}
        />
      </div>

      {/* P3-02: Current Regime card (label + confidence + duration + key drivers) */}
      {regime.data && (
        <CurrentRegimeCard regime={regime.data} duration={currentDuration} />
      )}

      {/* FE-132: Regime 时间轴 (P3-02: 含转换注释) */}
      <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300">
            {t("regime.timeline90d")}
          </h2>
          {timeline.data && (
            <span className="text-xs text-slate-500">
              {t("regime.transitions")}:{" "}
              <strong className="font-mono text-slate-300">{timeline.data.transitions}</strong>
            </span>
          )}
        </div>
        <RegimeTimeline data={timeline.data?.points} isLoading={timeline.isLoading} />
      </div>

      {/* P3-02: 历史 regime 表格 */}
      <RegimeHistoryTable periods={periods} isLoading={timeline.isLoading} />
    </div>
  );
}

// ── FE-131: Gating Cards ──────────────────────────

function GatingCard({
  title,
  regime,
  isLoading,
}: {
  title: string;
  regime: "normal" | "panic" | undefined;
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  if (isLoading) return <SkeletonCard />;

  const isPanic = regime === "panic";
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
      <div className="text-xs text-slate-500 mb-2">{title}</div>
      <div className="flex items-center gap-3">
        <div
          className={`w-4 h-4 rounded-full ${isPanic ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`}
        />
        <span className={`text-lg font-bold ${isPanic ? "text-red-400" : "text-emerald-400"}`}>
          {isPanic ? t("regime.panicLabel") : t("regime.normalLabel")}
        </span>
      </div>
    </div>
  );
}

function VixCard({
  vix,
  isLoading,
}: {
  vix: number | null | undefined;
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  if (isLoading) return <SkeletonCard />;

  const vixVal = vix ?? 0;
  const color =
    vixVal >= 30
      ? "text-red-400"
      : vixVal >= 20
        ? "text-amber-300"
        : "text-emerald-400";
  const barWidth = Math.min(100, (vixVal / 50) * 100);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
      <div className="text-xs text-slate-500 mb-2">{t("regime.vix")}</div>
      <div className={`text-2xl font-mono font-bold ${color}`}>
        {vix !== null && vix !== undefined ? vix.toFixed(2) : "—"}
      </div>
      {/* 水位标尺 */}
      <div className="mt-2 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            vixVal >= 30 ? "bg-red-500" : vixVal >= 20 ? "bg-amber-400" : "bg-emerald-500"
          }`}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
        <span>0</span>
        <span>20</span>
        <span>30</span>
        <span>50</span>
      </div>
    </div>
  );
}

function SpxCard({
  spxClose,
  spxMa20,
  isLoading,
}: {
  spxClose: number | null | undefined;
  spxMa20: number | null | undefined;
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  if (isLoading) return <SkeletonCard />;

  const aboveMa20 = spxClose && spxMa20 ? spxClose > spxMa20 : null;
  const pctDiff =
    spxClose && spxMa20 ? ((spxClose - spxMa20) / spxMa20) * 100 : null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
      <div className="text-xs text-slate-500 mb-2">{t("regime.spx")}</div>
      <div className="text-2xl font-mono font-bold text-slate-200">
        {spxClose !== null && spxClose !== undefined ? spxClose.toFixed(0) : "—"}
      </div>
      {pctDiff !== null && (
        <div className={`text-xs mt-1 ${aboveMa20 ? "text-emerald-400" : "text-red-400"}`}>
          {aboveMa20 ? "▲" : "▼"} {Math.abs(pctDiff).toFixed(2)}% vs {t("regime.spxMa20")}{" "}
          ({spxMa20?.toFixed(0)})
        </div>
      )}
    </div>
  );
}

// ── FE-132: Regime Timeline ECharts ──────────────

function RegimeTimeline({
  data,
  isLoading,
}: {
  data: Array<{ trade_date: string; regime: "normal" | "panic"; vix: number | null; spx_close: number | null; spx_ma20?: number | null; is_transition?: boolean }> | undefined;
  isLoading: boolean;
}) {
  const { t } = useTranslation();

  const option = useMemo<EChartsOptionLoose | null>(() => {
    if (!data || data.length === 0) return null;

    const sorted = [...data].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    const dates = sorted.map((d) => d.trade_date.slice(5));

    // VIX line data
    const vixData = sorted.map((d) => d.vix);

    // Regime background areas
    const regimeAreas: Array<Array<{ xAxis: string; itemStyle?: { color: string } }>> = [];
    let areaStart: number | null = null;
    let currentRegime: string | null = null;

    for (let i = 0; i < sorted.length; i++) {
      if (sorted[i].regime !== currentRegime) {
        if (areaStart !== null) {
          regimeAreas.push([
            {
              xAxis: sorted[areaStart].trade_date.slice(5),
              itemStyle: { color: currentRegime === "panic" ? "rgba(255, 82, 82, 0.1)" : "rgba(33, 150, 243, 0.05)" },
            },
            { xAxis: sorted[i - 1].trade_date.slice(5) },
          ]);
        }
        areaStart = i;
        currentRegime = sorted[i].regime;
      }
    }
    if (areaStart !== null) {
      regimeAreas.push([
        {
          xAxis: sorted[areaStart].trade_date.slice(5),
          itemStyle: { color: currentRegime === "panic" ? "rgba(255, 82, 82, 0.1)" : "rgba(33, 150, 243, 0.05)" },
        },
        { xAxis: sorted[sorted.length - 1].trade_date.slice(5) },
      ]);
    }

    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const arr = params as Array<{ dataIndex: number }>;
          if (!arr || arr.length === 0) return "";
          const idx = arr[0].dataIndex;
          const d = sorted[idx];
          if (!d) return "";
          return [
            `<b>${d.trade_date}</b>`,
            `${t("regime.vix")}: <b>${d.vix !== null ? d.vix.toFixed(2) : "—"}</b>`,
            `${t("regime.spx")}: <b>${d.spx_close !== null ? d.spx_close.toFixed(0) : "—"}</b>`,
            `${t("regime.status")}: <b>${d.regime === "panic" ? t("regime.panicLabel") : t("regime.normalLabel")}</b>`,
            ...(d.is_transition ? [`⚡ ${t("regime.transitionPoint")}`] : []),
          ].join("<br/>");
        },
      },
      grid: { left: 40, right: 15, top: 10, bottom: 25 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { interval: Math.floor(sorted.length / 5), fontSize: 9 },
      },
      yAxis: {
        type: "value",
        name: "VIX",
        nameTextStyle: { fontSize: 9, color: HUNTER_COLORS.textMuted },
        axisLabel: { fontSize: 9 },
      },
      series: [
        {
          type: "line",
          smooth: true,
          data: vixData,
          showSymbol: false,
          lineStyle: { width: 1.5, color: HUNTER_COLORS.yellow },
          itemStyle: { color: HUNTER_COLORS.yellow },
          areaStyle: { color: "rgba(245, 158, 11, 0.08)" },
          markArea: regimeAreas.length > 0 ? { data: regimeAreas, silent: true } : undefined,
          // P3-02: Regime transition annotations (event markers)
          markPoint: {
            silent: true,
            symbol: "diamond",
            symbolSize: 8,
            label: { show: false },
            data: sorted
              .filter((d) => d.is_transition)
              .map((d) => ({
                coord: [d.trade_date.slice(5), d.vix ?? 0],
                itemStyle: { color: d.regime === "panic" ? "#ef4444" : "#22c55e" },
              })),
          },
        },
      ],
    };
  }, [data, t]);

  const { containerRef } = useECharts(option, [data]);

  if (isLoading) return <SkeletonChart height={200} />;
  if (!data || data.length === 0) {
    return (
      <div className="text-xs text-slate-500 text-center py-4">
        {t("regime.noTimeline")}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-[200px]"
      role="img"
      aria-label={t("regime.timelineAria")}
    />
  );
}

// ── P3-02: Current Regime Card (label + confidence + duration + drivers) ──

type RegimeSnapshot = {
  trade_date: string;
  regime: "normal" | "panic";
  vix: number | null;
  spx_close: number | null;
  spx_ma20: number | null;
  threshold_red: number;
  banner_text: string;
};

function CurrentRegimeCard({
  regime,
  duration,
}: {
  regime: RegimeSnapshot;
  duration: number | null;
}) {
  const { t } = useTranslation();
  const isPanic = regime.regime === "panic";

  // Heuristic confidence: VIX distance from gating threshold (±30)
  const confidence = useMemo(() => {
    if (regime.vix === null || regime.vix === undefined) return null;
    const dist = isPanic ? regime.vix - 30 : 30 - regime.vix;
    return Math.max(50, Math.min(95, Math.round(50 + dist * 2.5)));
  }, [regime.vix, isPanic]);

  const spxAboveMa20 =
    regime.spx_close !== null &&
    regime.spx_ma20 !== null &&
    regime.spx_close > regime.spx_ma20;

  return (
    <div
      className={`rounded-md border p-4 ${
        isPanic ? "bg-red-950/30 border-red-800/50" : "bg-slate-900 border-slate-800"
      }`}
    >
      <div className="flex items-center gap-3 flex-wrap">
        <span
          className={`w-3 h-3 rounded-full shrink-0 ${isPanic ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`}
          aria-hidden="true"
        />
        <h2 className={`text-lg font-bold ${isPanic ? "text-red-400" : "text-emerald-400"}`}>
          {isPanic ? t("regime.panicLabel") : t("regime.normalLabel")}
        </h2>
        {confidence !== null && (
          <span className="text-xs text-slate-400">
            {t("regime.confidence")}: <strong className="font-mono text-slate-200">{confidence}%</strong>
          </span>
        )}
        {duration !== null && (
          <span className="text-xs text-slate-400">
            {t("regime.duration")}: <strong className="font-mono text-slate-200">{duration} {t("regime.durationDays")}</strong>
          </span>
        )}
      </div>

      {/* Key drivers */}
      <div className="flex flex-wrap gap-2 mt-3">
        <span className="text-[11px] px-2 py-1 rounded bg-slate-800/80 text-slate-300">
          {t("regime.driverVix")}: <strong className="font-mono">{regime.vix !== null ? regime.vix.toFixed(2) : "—"}</strong>
        </span>
        <span className="text-[11px] px-2 py-1 rounded bg-slate-800/80 text-slate-300">
          SPX {spxAboveMa20 ? ">" : "<"} MA20
        </span>
        <span className="text-[11px] px-2 py-1 rounded bg-slate-800/80 text-slate-300">
          {t("regime.thresholdRed")}: <strong className="font-mono">{regime.threshold_red}</strong>
        </span>
      </div>

      <div className="text-xs text-slate-500 mt-3">
        {t("regime.tradeDate")}: {regime.trade_date} · {regime.banner_text}
      </div>
    </div>
  );
}

// ── P3-02: Historical Regime Table ────────────────

interface RegimePeriod {
  regime: "normal" | "panic";
  start: string;
  end: string;
  days: number;
  avgVix: number | null;
}

function RegimeHistoryTable({
  periods,
  isLoading,
}: {
  periods: RegimePeriod[];
  isLoading: boolean;
}) {
  const { t } = useTranslation();
  if (isLoading) return <SkeletonCard />;
  if (periods.length === 0) return null;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">{t("regime.historyTitle")}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 border-b border-slate-800">
              <th className="py-2 pr-4 font-medium">{t("regime.colPeriod")}</th>
              <th className="py-2 pr-4 font-medium">{t("regime.colRegime")}</th>
              <th className="py-2 pr-4 font-medium text-right">{t("regime.colDays")}</th>
              <th className="py-2 font-medium text-right">{t("regime.colAvgVix")}</th>
            </tr>
          </thead>
          <tbody>
            {periods.map((p, i) => (
              <tr key={`${p.start}-${p.regime}`} className="border-b border-slate-800/50 last:border-0">
                <td className="py-2 pr-4 font-mono text-xs text-slate-400 whitespace-nowrap">
                  {p.start} ~ {p.end}
                  {i === 0 && (
                    <span className="ml-2 text-[10px] text-slate-500">({t("regime.current")})</span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      p.regime === "panic" ? "text-red-400" : "text-emerald-400"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${p.regime === "panic" ? "bg-red-500" : "bg-emerald-500"}`}
                      aria-hidden="true"
                    />
                    {p.regime === "panic" ? t("regime.panicLabel") : t("regime.normalLabel")}
                  </span>
                </td>
                <td className="py-2 pr-4 font-mono text-right text-slate-300">{p.days}</td>
                <td className="py-2 font-mono text-right text-slate-300">
                  {p.avgVix !== null ? p.avgVix.toFixed(2) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
