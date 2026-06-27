import { createRoute } from "@tanstack/react-router";
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";
import { ThreatScoreGauge } from "@/components/radar/ThreatScoreGauge";
import { ModuleSignalLight } from "@/components/radar/ModuleSignalLight";
import { SignalLifecycleBadge } from "@/components/radar/SignalLifecycleBadge";
import { ThreatHistoryChart } from "@/components/radar/ThreatHistoryChart";
import {
  UltimateAlertOverlay,
  type UltimateAlertDTO,
} from "@/components/radar/UltimateAlertOverlay";
import { useSignalLifecycle } from "@/features/useSignalLifecycle";
import { useThreatHistory } from "@/features/useThreatHistory";
import { useUltimateAlert } from "@/features/useUltimateAlert";
import { LlmPanel } from "@/components/common/LlmPanel";

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

  // V1.5.9: Options Anomaly V2(PCR + Gamma + OTM 刺客)
  const optionsV2 = useQuery({
    queryKey: ["options-v2", ticker],
    queryFn: () => api.getOptionsAnomalyV2(ticker),
    retry: 0,
    staleTime: 1000 * 60 * 5,
  });

  // M3 联锁:信号生命周期 / 90 日轨迹 / 终极警报 三个新 hooks
  const redThreshold = 70; // 与后端 settings.threat_red_threshold 同步
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

  // UltimateAlertOverlay 状态:1 弹一次 + 用户主动关闭后才能再弹
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [dismissedAlertId, setDismissedAlertId] = useState<string | null>(null);
  const alertId = ultimateAlert.data
    ? `${ultimateAlert.data.trade_date}:${ultimateAlert.data.triggered_at}`
    : null;
  // 端点返回新警报 → 打开 overlay(useEffect 避免 render 中 setState)
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

  if (threat.isLoading) return <div className="text-slate-500">{t("common.loading")}</div>;

  if (threat.isError || !threat.data) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold font-mono">{ticker}</h1>
        <div className="bg-slate-900 border border-slate-800 rounded-md p-4 text-slate-400 text-sm">
          {ticker} 的 Threat Score 暂未生成(数据积累中)。
          <br />
          <span className="text-slate-500">
            完整数据需要 EOD 流水线对至少 30 个交易日完成 Threat Score 计算后展示。
          </span>
        </div>
        <button
          onClick={() => setLlmOpen(true)}
          className="text-xs px-3 py-1.5 rounded bg-indigo-700/60 hover:bg-indigo-600 border border-indigo-600/50 text-indigo-100 flex items-center gap-1.5"
        >
          <span>🧠</span> LLM 分析
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
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-mono">
          {d.symbol}{" "}
          <span className="text-slate-500 text-sm ml-2">
            {d.symbol_type === "etf" ? "ETF" : "个股"} · {d.trade_date}
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
            <span>🧠</span> LLM 分析
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 主仪表盘 */}
        <div className="bg-slate-900 border border-slate-800 rounded-md p-6 flex flex-col items-center">
          <ThreatScoreGauge
            value={d.total}
            raw={d.total_raw}
            lifecycle={d.signal_lifecycle}
            threshold={70}
          />
          {d.nl_summary && (
            <p className="mt-4 text-sm text-slate-300 text-center max-w-xs">{d.nl_summary}</p>
          )}
        </div>

        {/* 模块信号灯 */}
        <div className="bg-slate-900 border border-slate-800 rounded-md p-6 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">模块信号灯</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ModuleSignalLight name={t("modules.options")} value={d.module_options} />
            <ModuleSignalLight name={t("modules.short")} value={d.module_short} />
            <ModuleSignalLight name={t("modules.divergence")} value={d.module_divergence} />
            <ModuleSignalLight name={t("modules.insider")} value={d.module_insider} />
          </div>
          <div className="mt-6 text-xs text-slate-500">
            EMA 半衰期 {d.ema_halflife} 个交易日 · 权重 {JSON.stringify(d.weights)} · 状态机 {d.signal_lifecycle}
          </div>
        </div>
      </div>

      <ThreatHistoryChart data={history.data ?? []} threshold={redThreshold} />

      {/* V1.5.9: Options Anomaly V2 指标卡片 */}
      {optionsV2.data && optionsV2.data.signal_strength !== "LOW" && (
        <div className="bg-slate-900 border border-slate-800 rounded-md p-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
            期权异动 V2
            {optionsV2.data.signal_strength === "HIGH" && (
              <span className="text-xs px-1.5 py-0.5 rounded border text-red-400 bg-red-950/30 border-red-800/50">
                HIGH
              </span>
            )}
            {optionsV2.data.signal_strength === "NORMAL" && (
              <span className="text-xs px-1.5 py-0.5 rounded border text-slate-400 bg-slate-800 border-slate-700">
                NORMAL
              </span>
            )}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-slate-500 text-xs mb-1">PCR</div>
              <div className="font-mono font-bold text-slate-200">
                {optionsV2.data.pcr.toFixed(2)}
              </div>
              {optionsV2.data.pcr_z_score !== null && (
                <div className={`text-xs mt-0.5 ${optionsV2.data.pcr_extreme ? "text-red-400" : "text-slate-500"}`}>
                  z={optionsV2.data.pcr_z_score.toFixed(2)}
                  {optionsV2.data.pcr_extreme && " 极值"}
                </div>
              )}
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Put / Call 成交量</div>
              <div className="font-mono text-slate-300">
                {optionsV2.data.pcr_total_put.toLocaleString()} / {optionsV2.data.pcr_total_call.toLocaleString()}
              </div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">OTM 刺客合约</div>
              <div className={`font-mono font-bold ${
                optionsV2.data.otm_assassin_count >= 2 ? "text-red-400" : "text-slate-300"
              }`}>
                {optionsV2.data.otm_assassin_count}
              </div>
            </div>
            <div>
              <div className="text-slate-500 text-xs mb-1">Gamma 聚集</div>
              <div className="font-mono text-slate-300">
                {optionsV2.data.gamma_clusters.filter(g => g.is_cluster).length > 0 ? (
                  <span className="text-amber-300">
                    {optionsV2.data.gamma_clusters.filter(g => g.is_cluster).map(g => `$${g.strike.toFixed(0)}`).join(", ")}
                  </span>
                ) : (
                  <span className="text-slate-500">无</span>
                )}
              </div>
            </div>
          </div>
          {optionsV2.data.signal_modules.length > 0 && (
            <div className="mt-3 text-xs text-slate-500">
              触发模块: {optionsV2.data.signal_modules.join(" / ")}
            </div>
          )}
          {optionsV2.data._cache === "miss" && (
            <div className="mt-2 text-xs text-amber-500/60">缓存未命中,数据可能延迟</div>
          )}
        </div>
      )}

      <div className="text-xs text-slate-500">
        数据来源:FINRA + SEC EDGAR + Yahoo Finance。统计异常现象,仅供参考。
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
