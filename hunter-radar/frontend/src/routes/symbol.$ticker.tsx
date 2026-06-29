import { createRoute } from "@tanstack/react-router";
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";
import { ThreatScoreGauge } from "@/components/radar/ThreatScoreGauge";
import { ModuleSignalLight } from "@/components/radar/ModuleSignalLight";
import { SignalLifecycleBadge } from "@/components/radar/SignalLifecycleBadge";
import {
  UltimateAlertOverlay,
  type UltimateAlertDTO,
} from "@/components/radar/UltimateAlertOverlay";
import { useSignalLifecycle } from "@/features/useSignalLifecycle";
import { useThreatHistory } from "@/features/useThreatHistory";
import { useUltimateAlert } from "@/features/useUltimateAlert";
import { LlmPanel } from "@/components/common/LlmPanel";

// M2 图表组件
import {
  AttributionWaterfall,
  SignalRadar,
  TrajectoryChart,
  OptionsHeatmap,
  ShortIcebergV2,
  DivergenceChart,
  InsiderTimeline,
} from "@/components/charts";

// react-grid-layout CSS
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/symbol/$ticker",
  component: SymbolPage,
});

function SymbolPage() {
  const { ticker } = Route.useParams();
  const { t } = useTranslation();

  const threat = useQuery({
    queryKey: ["threat", ticker],
    queryFn: () => api.getThreatScore(ticker),
    retry: 0,
  });

  // M2: Attribution 瀑布图数据
  const attribution = useQuery({
    queryKey: ["attribution", ticker],
    queryFn: () => api.getAttribution(ticker),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Short Iceberg V2
  const shortIceberg = useQuery({
    queryKey: ["short-iceberg-v2", ticker],
    queryFn: () => api.getShortIcebergV2(ticker, 30),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Divergence
  const divergence = useQuery({
    queryKey: ["divergence", ticker],
    queryFn: () => api.getDivergence(ticker, 30),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Insider Actions
  const insiderActions = useQuery({
    queryKey: ["insider-actions", ticker],
    queryFn: () => api.getInsiderActions(ticker),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // V1.5.9: Options Anomaly V2
  const optionsV2 = useQuery({
    queryKey: ["options-v2", ticker],
    queryFn: () => api.getOptionsAnomalyV2(ticker),
    retry: 0,
    staleTime: 1000 * 60 * 5,
  });

  const redThreshold = 70;
  const lifecycle = useSignalLifecycle(ticker, { threshold: redThreshold });
  const history = useThreatHistory(ticker, 90);
  const ultimateAlert = useUltimateAlert(ticker);

  // LLM 分析面板
  const [llmOpen, setLlmOpen] = useState(false);
  const llmContext = useMemo(() => {
    if (!threat.data) return undefined;
    const dd = threat.data;
    return JSON.stringify({
      symbol: dd.symbol,
      type: dd.symbol_type,
      trade_date: dd.trade_date,
      threat_score: dd.total,
      module_options: dd.module_options,
      module_short: dd.module_short,
      module_divergence: dd.module_divergence,
      module_insider: dd.module_insider,
      weights: dd.weights,
      signal_lifecycle: dd.signal_lifecycle,
      regime: dd.regime,
    }, null, 2);
  }, [threat.data]);

  // UltimateAlertOverlay 状态
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [dismissedAlertId, setDismissedAlertId] = useState<string | null>(null);
  const alertId = ultimateAlert.data
    ? `${ultimateAlert.data.trade_date}:${ultimateAlert.data.triggered_at}`
    : null;
  useEffect(() => {
    if (
      ultimateAlert.data &&
      !overlayOpen &&
      alertId !== null &&
      alertId !== dismissedAlertId
    ) {
      setOverlayOpen(true);
    }
  }, [ultimateAlert.data, alertId, overlayOpen, dismissedAlertId]);

  if (threat.isLoading) {
    return <div className="text-slate-500">{t("common.loading")}</div>;
  }

  if (threat.isError || !threat.data) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
        <div className="bg-slate-900 border border-slate-800 rounded-md p-4 text-slate-400 text-sm">
          {ticker} {t("symbol.noData")}
          <br />
          <span className="text-slate-500">
            {t("symbol.noDataHint")}
          </span>
        </div>
        <button
          onClick={() => setLlmOpen(true)}
          className="text-xs px-3 py-1.5 rounded bg-indigo-700/60 hover:bg-indigo-600 border border-indigo-600/50 text-indigo-100 flex items-center gap-1.5"
        >
          <span>🧠</span> {t("symbol.llmAnalyze")}
        </button>
        <LlmPanel
          ticker={ticker}
          visible={llmOpen}
          onClose={() => setLlmOpen(false)}
          context={undefined}
        />
      </div>
    );
  }

  const d = threat.data;
  const isEtf = d.symbol_type === "etf";

  return (
    <div className="space-y-4">
      {/* ── 页头 ─────────────────────────────────── */}
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-mono">
          {d.symbol}{" "}
          <span className="text-slate-500 text-sm ml-2">
            {isEtf ? "ETF" : t("symbol.stock")} · {d.trade_date}
          </span>
        </h1>
        <div className="flex items-center gap-2">
          {d.data_warmup && (
            <span className="text-xs text-amber-400 bg-amber-900/20 border border-amber-800/50 px-2 py-1 rounded">
              {t("common.warmup")}
            </span>
          )}
          <button
            onClick={() => setLlmOpen(true)}
            className="text-xs px-3 py-1.5 rounded bg-indigo-700/60 hover:bg-indigo-600 border border-indigo-600/50 text-indigo-100 flex items-center gap-1.5 transition-colors"
          >
            <span>🧠</span> {t("symbol.llmAnalyze")}
          </button>
          {lifecycle.data && (
            <SignalLifecycleBadge
              lifecycle={lifecycle.data.lifecycle}
              consecutiveDays={lifecycle.data.consecutiveDays}
              emaScore={lifecycle.data.emaScore}
              threshold={redThreshold}
            />
          )}
        </div>
      </header>

      {/* ── FE-124: 多图表网格容器 ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

        {/* 第一行: Gauge + 模块信号灯 + 4D Radar */}
        <div className="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-md p-4 flex flex-col items-center">
          <ThreatScoreGauge
            value={d.total}
            raw={d.total_raw}
            lifecycle={d.signal_lifecycle}
            threshold={70}
          />
          {d.nl_summary && (
            <p className="mt-3 text-xs text-slate-300 text-center max-w-xs">{d.nl_summary}</p>
          )}
        </div>

        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-3">{t("symbol.moduleSignals")}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <ModuleSignalLight name={t("modules.options")} value={d.module_options} />
            <ModuleSignalLight name={t("modules.short")} value={d.module_short} />
            <ModuleSignalLight name={t("modules.divergence")} value={d.module_divergence} />
            <ModuleSignalLight name={t("modules.insider")} value={d.module_insider} />
          </div>
          <div className="mt-3 text-[10px] text-slate-600">
            EMA {t("symbol.emaHalflife")} {d.ema_halflife} · {t("symbol.weights")} {JSON.stringify(d.weights)} · {d.signal_lifecycle}
          </div>
        </div>

        <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-2">{t("symbol.signalRadar")}</h2>
          <SignalRadar
            moduleOptions={d.module_options}
            moduleShort={d.module_short}
            moduleDivergence={d.module_divergence}
            moduleInsider={d.module_insider}
            isLoading={threat.isLoading}
          />
        </div>

        {/* 第二行: Attribution + 90d Trajectory */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-2">{t("symbol.attribution")}</h2>
          <AttributionWaterfall
            contributions={attribution.data?.contributions}
            total={attribution.data?.total ?? d.total}
            isLoading={attribution.isLoading}
          />
        </div>

        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-2">{t("symbol.trajectory90d")}</h2>
          <TrajectoryChart
            data={history.data}
            threshold={redThreshold}
            isLoading={history.isLoading}
          />
        </div>

        {/* 第三行: Short Iceberg V2 + Divergence */}
        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-2">{t("symbol.shortIceberg")}</h2>
          <ShortIcebergV2
            series={shortIceberg.data?.series}
            isLoading={shortIceberg.isLoading}
          />
        </div>

        <div className="lg:col-span-6 bg-slate-900 border border-slate-800 rounded-md p-4">
          <h2 className="text-xs font-semibold text-slate-400 mb-2">{t("symbol.divergence")}</h2>
          <DivergenceChart
            data={divergence.data}
            isLoading={divergence.isLoading}
          />
        </div>

        {/* 第四行: Options Heatmap (全宽) */}
        {optionsV2.data && optionsV2.data.signal_strength !== "LOW" && (
          <div className="lg:col-span-12 bg-slate-900 border border-slate-800 rounded-md p-4">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-xs font-semibold text-slate-400">{t("symbol.optionsAnomaly")}</h2>
              {optionsV2.data.signal_strength === "HIGH" && (
                <span className="text-[10px] px-1.5 py-0.5 rounded border text-red-400 bg-red-950/30 border-red-800/50">HIGH</span>
              )}
              {optionsV2.data.signal_strength === "NORMAL" && (
                <span className="text-[10px] px-1.5 py-0.5 rounded border text-slate-400 bg-slate-800 border-slate-700">NORMAL</span>
              )}
            </div>
            {/* V2 指标卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
              <div>
                <div className="text-slate-500 mb-0.5">PCR</div>
                <div className="font-mono font-bold text-slate-200">{optionsV2.data.pcr.toFixed(2)}</div>
                {optionsV2.data.pcr_z_score !== null && (
                  <div className={`text-[10px] ${optionsV2.data.pcr_extreme ? "text-red-400" : "text-slate-500"}`}>
                    z={optionsV2.data.pcr_z_score.toFixed(2)}{optionsV2.data.pcr_extreme && ` ${t("symbol.extreme")}`}
                  </div>
                )}
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.putCallVolume")}</div>
                <div className="font-mono text-slate-300">
                  {optionsV2.data.pcr_total_put.toLocaleString()} / {optionsV2.data.pcr_total_call.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.otmAssassin")}</div>
                <div className={`font-mono font-bold ${optionsV2.data.otm_assassin_count >= 2 ? "text-red-400" : "text-slate-300"}`}>
                  {optionsV2.data.otm_assassin_count}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.gammaCluster")}</div>
                <div className="font-mono text-slate-300">
                  {optionsV2.data.gamma_clusters.filter(g => g.is_cluster).length > 0 ? (
                    <span className="text-amber-300">
                      {optionsV2.data.gamma_clusters.filter(g => g.is_cluster).map(g => `$${g.strike.toFixed(0)}`).join(", ")}
                    </span>
                  ) : (
                    <span className="text-slate-500">{t("symbol.none")}</span>
                  )}
                </div>
              </div>
            </div>
            {/* 合约热力表 */}
            {optionsV2.data.signal_modules.length > 0 && (
              <div className="text-[10px] text-slate-500 mb-2">
                {t("symbol.triggerModules")}: {optionsV2.data.signal_modules.join(" / ")}
              </div>
            )}
          </div>
        )}

        {/* 第五行: Insider Timeline (全宽) */}
        <div className="lg:col-span-12 bg-slate-900 border border-slate-800 rounded-md p-4">
          <InsiderTimeline
            actions={insiderActions.data}
            isEtf={isEtf}
          />
        </div>
      </div>

      <div className="text-[10px] text-slate-600">
        {t("symbol.dataSourceDisclaimer")}
      </div>

      <LlmPanel
        ticker={ticker}
        visible={llmOpen}
        onClose={() => setLlmOpen(false)}
        context={llmContext}
      />

      <UltimateAlertOverlay
        open={overlayOpen}
        alert={ultimateAlert.data ?? null}
        onClose={() => {
          setOverlayOpen(false);
          setDismissedAlertId(alertId);
        }}
      />
    </div>
  );
}
