/**
 * FE-130/131/132: 宏观环境总览页(Regime Overview)
 *
 * - FE-130: 路由 + 页面骨架
 * - FE-131: VIX/SPX 门控状态指示灯
 * - FE-132: Regime 切换时间轴(状态转移色块图, ECharts)
 */
import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";
import { useECharts, type EChartsOptionLoose } from "@/components/charts/useECharts";
import { HUNTER_COLORS } from "@/lib/theme/hunter-dark";
import { SkeletonChart, SkeletonCard } from "@/components/common/Skeleton";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/regime",
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

      {/* 当前 regime 详情 */}
      {regime.data && (
        <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
          <div className="text-sm text-slate-300">
            {regime.data.regime === "panic"
              ? t("regime.panic")
              : t("regime.normal")}
          </div>
          <div className="text-xs text-slate-500 mt-2">
            {t("regime.tradeDate")}: {regime.data.trade_date} · {regime.data.banner_text}
          </div>
        </div>
      )}

      {/* FE-132: Regime 时间轴 */}
      <div className="bg-slate-900 border border-slate-800 rounded-md p-4">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">
          {t("regime.timeline90d")}
        </h2>
        <RegimeTimeline data={timeline.data?.points} isLoading={timeline.isLoading} />
      </div>
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
