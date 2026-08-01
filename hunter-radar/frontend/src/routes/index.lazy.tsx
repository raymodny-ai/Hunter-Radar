/**
 * P1-01 / P1-02: Radar Dashboard 重写 (PRD §3.1)
 *
 * Layout (desktop ≥1024px):
 * - Left Panel 320px: Threat Score Ranking Top 20 + Module Signal Lights
 * - Main Area: Signal Radar (4-axis) + Ultimate Alert Feed (30s poll) + Data Freshness
 *
 * Key Interactions:
 * - Ranking: sortable by total score, filterable by lifecycle + module
 * - Radar: hover ranking → highlight; click → drill into detail
 * - Alert Feed: timeline cards, expandable module breakdown
 *
 * States: skeleton / empty "No signals today" / error toast + retry
 */
import { useMemo, useState, useCallback } from "react";
import { createLazyRoute, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { SignalRadar } from "@/components/charts/SignalRadar";
import { Sparkline } from "@/components/common/Sparkline";
import { SkeletonChart, SkeletonTable } from "@/components/common/Skeleton";
import { toast } from "@/components/common/Toast";
import { useDataStatus } from "@/features/useDataStatus";
import {
  threatScoreColor,
  MODULE_COLORS,
  MODULE_KEYS,
  type ModuleKey,
} from "@/lib/design-tokens";

export const Route = createLazyRoute("/")({
  component: DashboardPage,
});

// ── Lifecycle 筛选选项 ─────────────────────────────────
const LIFECYCLE_OPTIONS = ["red", "yellow", "gray", "green", "init"] as const;
type Lifecycle = (typeof LIFECYCLE_OPTIONS)[number];

const LIFECYCLE_DOT: Record<Lifecycle, string> = {
  red: "bg-[#ef4444]",
  yellow: "bg-[#eab308]",
  gray: "bg-slate-400",
  green: "bg-[#22c55e]",
  init: "bg-slate-600",
};

// ── 主页面 ─────────────────────────────────────────────
function DashboardPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const queryClient = useQueryClient();

  // 排名面板状态
  const [lifecycleFilter, setLifecycleFilter] = useState<Set<Lifecycle>>(new Set());
  const [moduleFilter, setModuleFilter] = useState<ModuleKey | null>(null);
  // 雷达聚焦标的 (默认 null → 使用排名第一)
  const [focusedSymbol, setFocusedSymbol] = useState<string | null>(null);

  // ── 数据查询 ─────────────────────────────────────────
  const screener = useQuery({
    queryKey: ["screener", "top20"],
    queryFn: () => api.getScreener(20),
    retry: 1,
  });

  // Ultimate Alert Feed — 30s 轮询 (PRD §3.1 / §5.2)
  const alertFeed = useQuery({
    queryKey: ["alerts", "ultimate-feed"],
    queryFn: async () => {
      try {
        return await api.getUltimateAlertsFeed(20);
      } catch (e) {
        // 404/501: 后端 feed 端点未就位时优雅降级
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          return { trade_date: "", alerts: [] };
        }
        throw e;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  });

  // 聚焦标的的 threat 详情 (雷达图用)
  const rows = screener.data?.rows ?? [];
  const effectiveFocused = focusedSymbol ?? rows[0]?.symbol ?? null;

  const focusedThreat = useQuery({
    queryKey: ["symbols", effectiveFocused, "threat"],
    queryFn: () => api.getThreatScore(effectiveFocused!),
    enabled: !!effectiveFocused,
    staleTime: 1000 * 60 * 60,
    retry: 0,
  });

  // ── 筛选逻辑 ─────────────────────────────────────────
  const filteredRows = useMemo(() => {
    let result = rows;
    if (lifecycleFilter.size > 0) {
      result = result.filter((r) => lifecycleFilter.has(r.signal_lifecycle as Lifecycle));
    }
    if (moduleFilter) {
      result = result.filter((r) => r.modules_active.includes(moduleFilter));
    }
    return result;
  }, [rows, lifecycleFilter, moduleFilter]);

  // ── 交互回调 ─────────────────────────────────────────
  const handleRowHover = useCallback(
    (symbol: string) => {
      setFocusedSymbol(symbol);
      // PRD §6.1: prefetch on hover
      queryClient.prefetchQuery({
        queryKey: ["symbols", symbol, "threat"],
        queryFn: () => api.getThreatScore(symbol),
        staleTime: 1000 * 60 * 60,
      });
    },
    [queryClient],
  );

  const handleRowClick = useCallback(
    (symbol: string) => {
      nav({ to: "/symbol/$ticker", params: { ticker: symbol } });
    },
    [nav],
  );

  const toggleLifecycle = (lc: Lifecycle) => {
    setLifecycleFilter((prev) => {
      const next = new Set(prev);
      if (next.has(lc)) next.delete(lc);
      else next.add(lc);
      return next;
    });
  };

  // ── 错误处理 ─────────────────────────────────────────
  if (screener.isError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <p className="text-slate-400 text-sm">{t("common.error")}</p>
        <button
          onClick={() => {
            screener.refetch();
            toast.info(t("common.retry"));
          }}
          className="px-4 py-2 rounded bg-slate-700 text-sm hover:bg-slate-600 focus:outline-none focus:ring-2 focus:ring-slate-400"
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full min-h-0">
      {/* ═══ Left Panel: Threat Score Ranking (320px) ═══ */}
      <aside
        className="w-full lg:w-80 shrink-0 flex flex-col gap-3 lg:border-r lg:border-slate-800/60 lg:pr-4"
        aria-label={t("dashboard.rankingPanel")}
      >
        {/* 标题 + 交易日 */}
        <div className="flex items-baseline justify-between">
          <h1 className="text-lg font-bold tracking-tight">
            {t("dashboard.rankingTitle")}
          </h1>
          {screener.data && (
            <span className="text-[11px] text-slate-500 font-mono">
              {screener.data.trade_date}
            </span>
          )}
        </div>

        {/* Module Signal Lights — 4-dim toggle (PRD §3.1) */}
        <div
          className="flex gap-1.5"
          role="group"
          aria-label={t("dashboard.moduleFilter")}
        >
          {MODULE_KEYS.map((mod) => {
            const active = moduleFilter === mod;
            return (
              <button
                key={mod}
                onClick={() => setModuleFilter(active ? null : mod)}
                aria-pressed={active}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium border transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 ${
                  active
                    ? "border-slate-500 bg-slate-700/80 text-slate-100"
                    : "border-slate-700/60 bg-slate-800/40 text-slate-400 hover:text-slate-200"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: MODULE_COLORS[mod] }}
                  aria-hidden="true"
                />
                {t(`modules.${mod}`)}
              </button>
            );
          })}
        </div>

        {/* Lifecycle 筛选 chips */}
        <div className="flex gap-1 flex-wrap" role="group" aria-label={t("dashboard.lifecycleFilter")}>
          {LIFECYCLE_OPTIONS.map((lc) => {
            const active = lifecycleFilter.has(lc);
            return (
              <button
                key={lc}
                onClick={() => toggleLifecycle(lc)}
                aria-pressed={active}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 ${
                  active
                    ? "border-slate-400 bg-slate-700 text-slate-100"
                    : "border-slate-700/50 text-slate-500 hover:text-slate-300"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${LIFECYCLE_DOT[lc]}`} aria-hidden="true" />
                {t(`lifecycle.${lc}`)}
              </button>
            );
          })}
        </div>

        {/* 排名列表 */}
        <div className="flex-1 min-h-0 overflow-y-auto rounded-lg border border-slate-800/60 bg-slate-900/40">
          {screener.isLoading ? (
            <SkeletonTable rows={10} cols={4} className="border-0" />
          ) : filteredRows.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-sm text-slate-500">
              {rows.length === 0 ? t("dashboard.noSignals") : t("dashboard.noMatches")}
            </div>
          ) : (
            <ul role="list" className="divide-y divide-slate-800/40">
              {filteredRows.map((r) => (
                <RankingRow
                  key={r.symbol}
                  rank={r.rank}
                  symbol={r.symbol}
                  name={r.name}
                  score={r.threat_score}
                  lifecycle={r.signal_lifecycle as Lifecycle}
                  isFocused={effectiveFocused === r.symbol}
                  onHover={handleRowHover}
                  onClick={handleRowClick}
                />
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* ═══ Main Area ═══ */}
      <main className="flex-1 min-w-0 flex flex-col gap-4" aria-label={t("dashboard.mainArea")}>
        {/* Signal Radar (PRD §3.1 Main) */}
        <section
          className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4"
          aria-label={t("dashboard.radarSection")}
        >
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-slate-300">
              {t("dashboard.radarTitle")}
            </h2>
            {effectiveFocused && (
              <button
                onClick={() => handleRowClick(effectiveFocused)}
                className="font-mono text-sm font-bold text-slate-100 hover:text-white underline decoration-slate-600 underline-offset-4 focus:outline-none focus:ring-2 focus:ring-slate-400 rounded"
                aria-label={`${effectiveFocused} — ${t("dashboard.viewDetail")}`}
              >
                {effectiveFocused}
                {focusedThreat.data && (
                  <span
                    className="ml-2 text-base"
                    style={{ color: threatScoreColor(focusedThreat.data.total) }}
                  >
                    {focusedThreat.data.total.toFixed(1)}
                  </span>
                )}
              </button>
            )}
          </div>
          {screener.isLoading ? (
            <SkeletonChart height={260} />
          ) : focusedThreat.data ? (
            <SignalRadar
              moduleOptions={focusedThreat.data.module_options}
              moduleShort={focusedThreat.data.module_short}
              moduleDivergence={focusedThreat.data.module_divergence}
              moduleInsider={focusedThreat.data.module_insider}
              className="w-full h-[260px]"
            />
          ) : (
            <div className="flex items-center justify-center h-[260px] text-sm text-slate-500">
              {effectiveFocused ? t("common.loading") : t("dashboard.noSignals")}
            </div>
          )}
        </section>

        {/* Ultimate Alert Feed (PRD §3.1: 30s polling timeline) */}
        <section
          className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 flex-1 min-h-0 flex flex-col"
          aria-label={t("dashboard.alertFeed")}
        >
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-300">
              {t("dashboard.alertFeedTitle")}
            </h2>
            <span className="text-[10px] text-slate-500 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" aria-hidden="true" />
              30s
            </span>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto space-y-2" aria-live="polite">
            {alertFeed.isLoading ? (
              <SkeletonTable rows={3} cols={3} className="border-0" />
            ) : (alertFeed.data?.alerts ?? []).length === 0 ? (
              <div className="flex items-center justify-center h-24 text-sm text-slate-500">
                {t("dashboard.noAlerts")}
              </div>
            ) : (
              alertFeed.data!.alerts.map((alert, idx) => (
                <AlertFeedCard
                  key={`${alert.symbol}-${alert.triggered_at}-${idx}`}
                  alert={alert}
                  onViewDetail={handleRowClick}
                />
              ))
            )}
          </div>
        </section>

        {/* Data Freshness Status (PRD §3.1) */}
        <DataFreshnessCard />
      </main>
    </div>
  );
}

// ── 排名行 ─────────────────────────────────────────────
interface RankingRowProps {
  rank: number;
  symbol: string;
  name: string;
  score: number;
  lifecycle: Lifecycle;
  isFocused: boolean;
  onHover: (symbol: string) => void;
  onClick: (symbol: string) => void;
}

function RankingRow({ rank, symbol, name, score, lifecycle, isFocused, onHover, onClick }: RankingRowProps) {
  const color = threatScoreColor(score);

  return (
    <li>
      <button
        onMouseEnter={() => onHover(symbol)}
        onFocus={() => onHover(symbol)}
        onClick={() => onClick(symbol)}
        className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-colors focus:outline-none focus:ring-1 focus:ring-inset focus:ring-slate-400 ${
          isFocused ? "bg-slate-700/40" : "hover:bg-slate-800/50"
        }`}
        aria-label={`${symbol} ${name}, threat score ${score.toFixed(0)}, ${lifecycle}`}
      >
        {/* Rank */}
        <span className="w-5 text-[11px] font-mono text-slate-500 shrink-0">
          {rank}
        </span>
        {/* Ticker + Name */}
        <span className="flex-1 min-w-0">
          <span className="block font-mono text-sm font-bold text-slate-100 truncate">
            {symbol}
          </span>
          <span className="block text-[10px] text-slate-500 truncate">{name}</span>
        </span>
        {/* Sparkline */}
        <Sparkline ticker={symbol} width={56} height={18} className="shrink-0" />
        {/* Lifecycle dot */}
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${LIFECYCLE_DOT[lifecycle]}`}
          aria-hidden="true"
          title={lifecycle}
        />
        {/* Score */}
        <span
          className="w-9 text-right font-mono text-sm font-bold shrink-0"
          style={{ color }}
        >
          {score.toFixed(0)}
        </span>
      </button>
    </li>
  );
}

// ── Alert Feed 卡片 (PRD §3.4 Alert Card 设计) ─────────
interface AlertFeedCardProps {
  alert: {
    symbol: string;
    threat_score: number;
    modules_active: string[];
    regime: "normal" | "panic";
    consecutive_days: number;
    triggered_at: string;
    trade_date: string;
  };
  onViewDetail: (symbol: string) => void;
}

function AlertFeedCard({ alert, onViewDetail }: AlertFeedCardProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const color = threatScoreColor(alert.threat_score);

  return (
    <div className="rounded-md border border-slate-700/50 bg-slate-800/40 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left focus:outline-none focus:ring-1 focus:ring-inset focus:ring-slate-400"
      >
        {/* 红色指示器 */}
        <span
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ backgroundColor: color }}
          aria-hidden="true"
        />
        <span className="font-mono text-sm font-bold text-slate-100">
          {alert.symbol}
        </span>
        <span className="font-mono text-sm font-bold" style={{ color }}>
          {alert.threat_score.toFixed(1)}
        </span>
        <span className="text-[10px] text-slate-400">
          {t("dashboard.consecutive", { days: alert.consecutive_days })}
        </span>
        <span className="ml-auto text-[10px] text-slate-500 font-mono">
          {alert.trade_date}
        </span>
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded ${
            alert.regime === "panic"
              ? "bg-red-900/40 text-red-300"
              : "bg-slate-700/50 text-slate-400"
          }`}
        >
          {alert.regime === "panic" ? t("dashboard.regimePanic") : t("dashboard.regimeNormal")}
        </span>
        <span className="text-slate-500 text-xs" aria-hidden="true">
          {expanded ? "▾" : "▸"}
        </span>
      </button>

      {/* 展开: 模块分解 */}
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-700/40">
          <div className="flex flex-wrap gap-1.5 mb-2">
            {alert.modules_active.map((mod) => (
              <span
                key={mod}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-700/60 text-slate-200"
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: MODULE_COLORS[mod as ModuleKey] ?? "#94a3b8" }}
                  aria-hidden="true"
                />
                {t(`modules.${mod}`)}
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onViewDetail(alert.symbol)}
              className="px-3 py-1 rounded bg-slate-700 text-[11px] text-slate-100 hover:bg-slate-600 focus:outline-none focus:ring-1 focus:ring-slate-400"
            >
              {t("dashboard.viewDetail")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Data Freshness Status (PRD §3.1) ───────────────────
function DataFreshnessCard() {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useDataStatus();

  const statusConfig = (() => {
    if (isError) return { dot: "bg-red-500", text: t("dashboard.freshnessError"), cls: "text-red-300" };
    if (isLoading || !data) return { dot: "bg-slate-500 animate-pulse", text: t("common.loading"), cls: "text-slate-400" };
    switch (data.status) {
      case "ready":
        return { dot: "bg-green-500", text: t("dashboard.freshnessReady"), cls: "text-green-300" };
      case "warming":
        return { dot: "bg-yellow-500", text: t("dashboard.freshnessWarming"), cls: "text-yellow-300" };
      case "stale":
        return { dot: "bg-orange-500", text: t("dashboard.freshnessStale"), cls: "text-orange-300" };
      default:
        return { dot: "bg-red-500", text: t("dashboard.freshnessError"), cls: "text-red-300" };
    }
  })();

  return (
    <section
      className="rounded-lg border border-slate-800/60 bg-slate-900/40 px-4 py-3 flex items-center gap-3"
      aria-label={t("dashboard.freshnessLabel")}
    >
      <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${statusConfig.dot}`} aria-hidden="true" />
      <span className={`text-xs font-medium ${statusConfig.cls}`}>{statusConfig.text}</span>
      {data?.last_data_date && (
        <span className="text-[10px] text-slate-500 font-mono ml-auto">
          {t("dashboard.lastData")}: {data.last_data_date}
        </span>
      )}
    </section>
  );
}
