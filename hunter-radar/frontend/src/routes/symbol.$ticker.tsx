import { createRoute } from "@tanstack/react-router";
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
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
import { useSymbolAutoWarmup } from "@/features/useSymbolAutoWarmup";
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

  // 辅助: 404 吞掉返 null, 不让 isError 触发 整个页 error 状态
  const notFoundToNull = async <T,>(p: Promise<T>): Promise<T | null> => {
    try {
      return await p;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  };
  // 辅助: 同上, 返 undefined (避免 strict null check 在 prop type 'T | undefined' 上报错)
  const notFoundToUndefined = async <T,>(p: Promise<T>): Promise<T | undefined> => {
    try {
      return await p;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return undefined;
      throw e;
    }
  };

  const threat = useQuery({
    queryKey: ["threat", ticker],
    queryFn: () => notFoundToNull(api.getThreatScore(ticker)),
    retry: 0,
  });

  // M2: Attribution 瀑布图数据
  const attribution = useQuery({
    queryKey: ["attribution", ticker],
    queryFn: () => notFoundToNull(api.getAttribution(ticker)),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Short Iceberg V2
  const shortIceberg = useQuery({
    queryKey: ["short-iceberg-v2", ticker],
    queryFn: () => notFoundToUndefined(api.getShortIcebergV2(ticker, 30)),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Divergence
  const divergence = useQuery({
    queryKey: ["divergence", ticker],
    queryFn: () => notFoundToUndefined(api.getDivergence(ticker, 30)),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // M2: Insider Actions (SEC form4 endpoint 未接,404 返 [] 不报错)
  const insiderActions = useQuery({
    queryKey: ["insider-actions", ticker],
    queryFn: async () => {
      try {
        const r = await api.getInsiderActions(ticker);
        return r ?? [];
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return [];
        throw e;
      }
    },
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // V1.5.9: Options Anomaly V2 (404 返 null)
  const optionsV2 = useQuery({
    queryKey: ["options-v2", ticker],
    queryFn: () => notFoundToNull(api.getOptionsAnomalyV2(ticker)),
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
    // V1.7.4: 新标的自动 ETL — 用户输入不被动的等 30 天
    return <NoDataOrWarmingUp ticker={ticker} />;
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
            contributions={attribution.data?.modules?.map((m) => ({
              module: m.module,
              score: m.score,
              weight: m.weight,
              weighted_score: m.contribution,
            }))}
            total={attribution.data?.total_score ?? d.total}
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
              {optionsV2.data.signal_strength === "INSUFFICIENT" && (
                <span className="text-[10px] px-1.5 py-0.5 rounded border text-amber-400 bg-amber-950/30 border-amber-800/50" title="options history < 14 days, Z-Score / cluster detection not yet meaningful">数据积累中</span>
              )}
            </div>
            {/* V2 指标卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
              <div>
                <div className="text-slate-500 mb-0.5">PCR</div>
                <div className="font-mono font-bold text-slate-200">
                  {optionsV2.data.pcr != null ? optionsV2.data.pcr.toFixed(2) : "—"}
                </div>
                {optionsV2.data.pcr_z_score !== null && optionsV2.data.pcr_z_score !== undefined && (
                  <div className={`text-[10px] ${optionsV2.data.pcr_extreme ? "text-red-400" : "text-slate-500"}`}>
                    z={optionsV2.data.pcr_z_score.toFixed(2)}{optionsV2.data.pcr_extreme && ` ${t("symbol.extreme")}`}
                  </div>
                )}
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.putCallVolume")}</div>
                <div className="font-mono text-slate-300">
                  {(optionsV2.data.pcr ?? 0).toFixed(3)}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.otmAssassin")}</div>
                <div className={`font-mono font-bold ${(optionsV2.data.otm_assassin_count ?? 0) >= 2 ? "text-red-400" : "text-slate-300"}`}>
                  {optionsV2.data.otm_assassin_count ?? 0}
                </div>
              </div>
              <div>
                <div className="text-slate-500 mb-0.5">{t("symbol.gammaCluster")}</div>
                <div className="font-mono text-slate-300">
                  {(optionsV2.data.gamma_clusters ?? []).filter(g => g.is_cluster).length > 0 ? (
                    <span className="text-amber-300">
                      {(optionsV2.data.gamma_clusters ?? []).filter(g => g.is_cluster).map(g => `$${g.strike.toFixed(0)}`).join(", ")}
                    </span>
                  ) : (
                    <span className="text-slate-500">{t("symbol.none")}</span>
                  )}
                </div>
              </div>
            </div>
            {/* 合约热力表 */}
            {(optionsV2.data.signal_modules ?? []).length > 0 && (
              <div className="text-[10px] text-slate-500 mb-2">
                {t("symbol.triggerModules")}: {(optionsV2.data.signal_modules ?? []).join(" / ")}
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

// V1.7.4 — 新标的自动 ETL 拉动器
function NoDataOrWarmingUp({ ticker }: { ticker: string }) {
  const { t } = useTranslation();
  // threat 还未到时 404 → null, 我们主动触发 upsert + warmup, 后台跑 90 天 deep backfill
  // 完成后页面会自动重新 render(threat query 重新 refetch)
  const { progress } = useSymbolAutoWarmup(ticker, true);

  return (
    <div className="space-y-4 max-w-xl">
      <h1 className="text-2xl font-bold font-mono">{ticker}</h1>

      <div className="bg-slate-900 border border-indigo-800/40 rounded-md p-5">
        <div className="flex items-center gap-2 text-indigo-300 text-sm">
          {progress.status === "ready" ? (
            <span className="text-emerald-400">●</span>
          ) : progress.status === "failed" ? (
            <span className="text-red-400">●</span>
          ) : (
            <span className="animate-pulse">●</span>
          )}
          <span className="font-mono font-semibold">
            {progress.status === "ready"
              ? `${ticker} Threat Score 已就绪, 页面即将刷新`
              : progress.status === "failed"
              ? `${ticker} 自动拉数失败, 请稍后重试`
              : `正在为 ${ticker} 抓取 90 天历史数据…`}
          </span>
        </div>

        {progress.status !== "ready" && progress.status !== "failed" && (
          <>
            <div className="mt-3 h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all duration-500"
                style={{ width: `${progress.progress}%` }}
              />
            </div>
            <div className="mt-2 flex items-center justify-between text-xs text-slate-500 font-mono">
              <span>
                步骤 {Math.floor((progress.progress / 100) * 7) + 1}/7 · {progress.currentStep}
              </span>
              {progress.rows !== undefined && progress.rows > 0 && (
                <span>{progress.rows.toLocaleString()} rows</span>
              )}
            </div>
            <div className="mt-3 text-xs text-slate-500 leading-relaxed">
              {progress.status === "queued" || progress.status === "running"
                ? "首次入库需 5–8 分钟, 系统同时拉取 yfinance 日线 + FINRA 周报告 + 期权链 + 计算 Threat Score。"
                : "检测到该标的尚未在数据库内, 正在自动入库并启动 ETL 拉数。"}
            </div>
          </>
        )}

        {progress.status === "failed" && progress.error && (
          <div className="mt-3 text-xs text-red-400 font-mono break-all">
            {progress.error}
          </div>
        )}

        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={() => {
              // 手动 retry: window.location.reload() 重新触发
              window.location.reload();
            }}
            className="text-xs px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 border border-slate-600 text-slate-200"
          >
            🔄 强制刷新
          </button>
          <LlmPanelButton ticker={ticker} />
        </div>
      </div>

      <div className="text-xs text-slate-600 leading-relaxed">
        ● Hunter Radar V1.7.4: 用户输入新标的时, 系统自动触发后台 ETL 拉取 90 天 deep backfill 数据。
        同时拉取 yfinance 日线 / FINRA 短仓周报 / 期权链, 计算 Threat Score。
        通常 5–8 分钟完成, 完成后页面将自动刷新。
      </div>
    </div>
  );
}

function LlmPanelButton({ ticker }: { ticker: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-3 py-1.5 rounded bg-indigo-700/60 hover:bg-indigo-600 border border-indigo-600/50 text-indigo-100 flex items-center gap-1.5"
      >
        <span>🧠</span> {t("symbol.llmAnalyze")}
      </button>
      <LlmPanel
        ticker={ticker}
        visible={open}
        onClose={() => setOpen(false)}
        context={undefined}
      />
    </>
  );
}
