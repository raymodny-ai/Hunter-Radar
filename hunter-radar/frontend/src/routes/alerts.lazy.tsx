/**
 * P2-03: Alerts 三 Tab 重构 (PRD §3.4)
 *
 * Tabs:
 * 1. Active Alerts — 按日期分组, Alert Card 设计 (§3.4)
 * 2. History — 分页历史 + outcome 注释
 * 3. Settings — push 偏好 + 规则 CRUD (AlertRuleForm)
 *
 * Alert Card: 🔴 ticker + score + consecutive days + modules + regime + actions
 */
import { useState, useCallback, useEffect, useMemo } from "react";
import { createLazyRoute, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { api, ApiError, type UltimateAlertDTO } from "../lib/api";
import { AlertRuleForm, type AlertRuleFormData } from "@/components/common/AlertRuleForm";
import { useWebPush } from "@/features/useWebPush";
import { SkeletonCard } from "@/components/common/Skeleton";
import { toast } from "@/components/common/Toast";
import { threatScoreColor, MODULE_COLORS, type ModuleKey } from "@/lib/design-tokens";

export const Route = createLazyRoute("/alerts")({
  component: AlertsPage,
});

// ── Types ──────────────────────────────────────────────
type TabKey = "active" | "history" | "settings";

type AlertRule = {
  id: number;
  user_id: string;
  name: string;
  dsl: { when: Array<{ metric: string; op: string; value: unknown }>; then: string };
  channels: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

// ── DSL 翻译层 (保留现有逻辑) ────────────────────────────
const METRIC_TO_RULE_TYPE: Record<string, string> = {
  "score.ema": "threat_score",
  "score.raw": "threat_score",
  lifecycle: "threat_score",
  modules: "divergence",
};

function ruleToFormInit(rule: AlertRule): AlertRuleFormData | undefined {
  const first = rule.dsl.when[0];
  if (!first) return undefined;
  return {
    symbol: rule.name,
    rule_type: (METRIC_TO_RULE_TYPE[first.metric] ?? "threat_score") as AlertRuleFormData["rule_type"],
    threshold: Number(first.value) || 70,
    operator: first.op as AlertRuleFormData["operator"],
  };
}

function formToCreatePayload(data: AlertRuleFormData) {
  return {
    name: data.symbol,
    dsl: { when: [{ metric: "score.ema", op: data.operator, value: data.threshold }], then: "push" as const },
    channels: ["email"],
  };
}

function formToUpdatePayload(data: AlertRuleFormData) {
  return {
    name: data.symbol,
    dsl: { when: [{ metric: "score.ema", op: data.operator, value: data.threshold }], then: "push" as const },
  };
}

// ── Main Page ──────────────────────────────────────────
function AlertsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>("active");

  const TABS: Array<{ key: TabKey; label: string }> = [
    { key: "active", label: t("alerts.tabActive") },
    { key: "history", label: t("alerts.tabHistory") },
    { key: "settings", label: t("alerts.tabSettings") },
  ];

  return (
    <div className="space-y-4 max-w-4xl">
      <header>
        <h1 className="text-2xl font-bold">{t("alerts.title")}</h1>
        <p className="text-slate-400 text-sm mt-1">{t("alerts.subtitle")}</p>
      </header>

      {/* Tab bar (PRD §3.4) */}
      <div role="tablist" aria-label={t("alerts.title")} className="flex gap-1 border-b border-slate-800">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 rounded-t ${
              activeTab === tab.key
                ? "border-red-500 text-slate-100"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <div role="tabpanel" aria-label={TABS.find((tb) => tb.key === activeTab)?.label}>
        {activeTab === "active" && <ActiveAlertsTab />}
        {activeTab === "history" && <HistoryTab />}
        {activeTab === "settings" && <SettingsTab />}
      </div>

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}

// ── Tab 1: Active Alerts (按日期分组 + Alert Card) ──────
function ActiveAlertsTab() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const queryClient = useQueryClient();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const feed = useQuery({
    queryKey: ["alerts", "ultimate-feed"],
    queryFn: async () => {
      try {
        return await api.getUltimateAlertsFeed(50);
      } catch (e) {
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          return { trade_date: "", alerts: [] as UltimateAlertDTO[] };
        }
        throw e;
      }
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  });

  // Add to Basket
  const baskets = useQuery({ queryKey: ["baskets"], queryFn: () => api.listBaskets(), staleTime: 300_000 });
  const addToBasket = useMutation({
    mutationFn: ({ basketId, ticker }: { basketId: number; ticker: string }) =>
      api.addBasketMembers(basketId, [ticker]),
    onSuccess: () => {
      toast.success(t("alerts.addedToBasket"));
      queryClient.invalidateQueries({ queryKey: ["baskets"] });
    },
    onError: () => toast.error(t("common.error")),
  });

  // 按日期分组
  const grouped = useMemo(() => {
    const alerts = (feed.data?.alerts ?? []).filter(
      (a) => !dismissed.has(`${a.symbol}-${a.trade_date}`),
    );
    const map = new Map<string, UltimateAlertDTO[]>();
    for (const a of alerts) {
      const key = a.trade_date || "unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(a);
    }
    return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  }, [feed.data, dismissed]);

  if (feed.isLoading) {
    return (
      <div className="space-y-2 pt-2">
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (feed.isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <span className="text-sm text-slate-400">{t("common.error")}</span>
        <button onClick={() => feed.refetch()} className="px-4 py-1.5 rounded bg-slate-700 text-sm hover:bg-slate-600 focus:outline-none focus:ring-1 focus:ring-slate-400">
          {t("common.retry")}
        </button>
      </div>
    );
  }

  if (grouped.length === 0) {
    return <div className="text-slate-500 text-sm py-12 text-center">{t("alerts.noActiveAlerts")}</div>;
  }

  return (
    <div className="space-y-5 pt-2" aria-live="polite">
      {grouped.map(([date, alerts]) => (
        <section key={date} aria-label={date}>
          <h3 className="text-xs font-semibold text-slate-500 font-mono mb-2">{date}</h3>
          <div className="space-y-2">
            {alerts.map((alert) => (
              <AlertCard
                key={`${alert.symbol}-${alert.triggered_at}`}
                alert={alert}
                baskets={baskets.data ?? []}
                onViewDetail={() => nav({ to: "/symbol/$ticker", params: { ticker: alert.symbol } })}
                onAddToBasket={(basketId) => addToBasket.mutate({ basketId, ticker: alert.symbol })}
                onDismiss={() =>
                  setDismissed((prev) => new Set(prev).add(`${alert.symbol}-${alert.trade_date}`))
                }
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ── Alert Card (PRD §3.4 设计) ─────────────────────────
function AlertCard({
  alert,
  baskets,
  onViewDetail,
  onAddToBasket,
  onDismiss,
}: {
  alert: UltimateAlertDTO;
  baskets: Array<{ id: number; name: string }>;
  onViewDetail: () => void;
  onAddToBasket: (basketId: number) => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const color = threatScoreColor(alert.threat_score);
  const [basketSel, setBasketSel] = useState<number | null>(null);

  return (
    <article className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-2.5">
      {/* Row 1: indicator + ticker + score + consecutive */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} aria-hidden="true" />
        <span className="font-mono text-base font-bold text-slate-100">{alert.symbol}</span>
        <span className="text-sm text-slate-400">
          {t("alerts.score")}: <strong className="font-mono" style={{ color }}>{alert.threat_score.toFixed(1)}</strong>
        </span>
        <span className="text-sm text-slate-400">
          {t("alerts.consecutiveDays")}: <strong className="font-mono text-slate-200">{alert.consecutive_days}d</strong>
        </span>
      </div>

      {/* Row 2: modules */}
      <div className="flex flex-wrap gap-1.5">
        <span className="text-[11px] text-slate-500 self-center">{t("alerts.modules")}:</span>
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

      {/* Row 3: regime + triggered date */}
      <div className="text-[11px] text-slate-500">
        {t("alerts.regime")}:{" "}
        <span className={alert.regime === "panic" ? "text-red-400" : "text-green-400"}>
          {alert.regime === "panic" ? t("dashboard.regimePanic") : t("dashboard.regimeNormal")}
        </span>
        {" | "}
        {t("alerts.triggeredAt")}: <span className="font-mono">{alert.triggered_at.slice(0, 16).replace("T", " ")}</span>
      </div>

      {/* Row 4: actions */}
      <div className="flex items-center gap-2 flex-wrap pt-1">
        <button
          onClick={onViewDetail}
          className="px-3 py-1.5 rounded bg-slate-700 text-[11px] text-slate-100 hover:bg-slate-600 focus:outline-none focus:ring-1 focus:ring-slate-400"
        >
          {t("dashboard.viewDetail")}
        </button>
        <select
          value={basketSel ?? ""}
          onChange={(e) => setBasketSel(e.target.value ? Number(e.target.value) : null)}
          aria-label={t("screener.targetBasket")}
          className="text-[11px] bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-400"
        >
          <option value="">{t("screener.targetBasket")}</option>
          {baskets.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
        <button
          onClick={() => basketSel && onAddToBasket(basketSel)}
          disabled={!basketSel}
          className="px-3 py-1.5 rounded border border-slate-600 text-[11px] text-slate-200 hover:bg-slate-700 disabled:opacity-40 focus:outline-none focus:ring-1 focus:ring-slate-400"
        >
          {t("symbol.addToBasket")}
        </button>
        <button
          onClick={onDismiss}
          className="ml-auto px-3 py-1.5 rounded text-[11px] text-slate-500 hover:text-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-400"
        >
          {t("alerts.dismiss")}
        </button>
      </div>
    </article>
  );
}

// ── Tab 2: History (分页 + outcome 注释) ───────────────
function HistoryTab() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 10;

  const feed = useQuery({
    queryKey: ["alerts", "ultimate-feed"],
    queryFn: async () => {
      try {
        return await api.getUltimateAlertsFeed(50);
      } catch (e) {
        if (e instanceof ApiError && (e.status === 404 || e.status === 501)) {
          return { trade_date: "", alerts: [] as UltimateAlertDTO[] };
        }
        throw e;
      }
    },
    staleTime: 30_000,
    retry: 1,
  });

  const alerts = feed.data?.alerts ?? [];
  const totalPages = Math.max(1, Math.ceil(alerts.length / PAGE_SIZE));
  const pageItems = alerts.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (feed.isLoading) return <SkeletonCard className="mt-2" />;

  if (alerts.length === 0) {
    return <div className="text-slate-500 text-sm py-12 text-center">{t("alerts.noHistory")}</div>;
  }

  return (
    <div className="space-y-2 pt-2">
      {pageItems.map((alert, idx) => (
        <button
          key={`${alert.symbol}-${alert.trade_date}-${idx}`}
          onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: alert.symbol } })}
          className="w-full text-left rounded-md border border-slate-700/40 bg-slate-800/30 px-4 py-3 flex items-center gap-3 hover:bg-slate-800/60 transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400"
        >
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ backgroundColor: threatScoreColor(alert.threat_score) }}
            aria-hidden="true"
          />
          <span className="font-mono text-sm font-bold text-slate-100 w-16">{alert.symbol}</span>
          <span className="font-mono text-sm" style={{ color: threatScoreColor(alert.threat_score) }}>
            {alert.threat_score.toFixed(1)}
          </span>
          {/* Outcome 注释: 基于 regime + consecutive */}
          <span className="text-[11px] text-slate-500 flex-1 truncate">
            {alert.regime === "panic" ? t("alerts.outcomePanic") : t("alerts.outcomeNormal")}
            {" · "}{t("alerts.consecutiveDays")} {alert.consecutive_days}d
          </span>
          <span className="text-[11px] text-slate-500 font-mono shrink-0">{alert.trade_date}</span>
        </button>
      ))}

      {/* 分页 */}
      <div className="flex items-center justify-center gap-3 pt-2">
        <button
          onClick={() => setPage(Math.max(0, page - 1))}
          disabled={page === 0}
          className="px-3 py-1 rounded text-xs border border-slate-700/50 text-slate-300 disabled:opacity-30 hover:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
          aria-label={t("screener.prevPage")}
        >
          ←
        </button>
        <span className="text-xs text-slate-400 font-mono">{page + 1} / {totalPages}</span>
        <button
          onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
          disabled={page >= totalPages - 1}
          className="px-3 py-1 rounded text-xs border border-slate-700/50 text-slate-300 disabled:opacity-30 hover:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
          aria-label={t("screener.nextPage")}
        >
          →
        </button>
      </div>
    </div>
  );
}

// ── Tab 3: Settings (push 偏好 + 规则 CRUD) ────────────
function SettingsTab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);

  // Web Push
  const { status: pushStatus, subscribe: pushSubscribe, errorMessage: pushError } = useWebPush();

  useEffect(() => {
    if (pushStatus === "unsubscribed") pushSubscribe();
  }, [pushStatus, pushSubscribe]);

  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.listAlerts(),
    staleTime: 60_000,
  });

  const handleCreate = useCallback(async (data: AlertRuleFormData) => {
    try {
      await api.createAlert(formToCreatePayload(data));
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success(t("alerts.ruleSaved"));
    } catch (e) {
      toast.error(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  }, [queryClient, t]);

  const handleUpdate = useCallback(async (data: AlertRuleFormData) => {
    if (!editingRule) return;
    try {
      await api.updateAlert(editingRule.id, formToUpdatePayload(data));
      setEditingRule(null);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast.success(t("alerts.ruleSaved"));
    } catch (e) {
      toast.error(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  }, [editingRule, queryClient, t]);

  const handleDelete = useCallback(async (id: number) => {
    try {
      await api.deleteAlert(id);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  }, [queryClient]);

  const handleToggle = useCallback(async (rule: AlertRule) => {
    try {
      await api.updateAlert(rule.id, { is_active: !rule.is_active });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  }, [queryClient]);

  return (
    <div className="space-y-6 pt-2">
      {/* Push 偏好 */}
      <section className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">{t("alerts.pushPrefs")}</h2>
        <div className="flex items-center gap-3">
          <PushStatusBadge status={pushStatus} error={pushError} onSubscribe={pushSubscribe} />
        </div>
        <p className="text-[11px] text-slate-500 mt-2">{t("alerts.pushHint")}</p>
      </section>

      {/* 规则管理 */}
      <section className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-300">{t("alerts.rulesTitle")}</h2>
          <button
            onClick={() => { setShowForm(true); setEditingRule(null); }}
            className="px-3 py-1.5 rounded bg-hunter-red text-white text-xs hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-red-400"
          >
            + {t("alerts.createRule")}
          </button>
        </div>

        {(showForm || editingRule) && (
          <AlertRuleForm
            initial={editingRule ? ruleToFormInit(editingRule) : undefined}
            onSubmit={editingRule ? handleUpdate : handleCreate}
            onCancel={() => { setShowForm(false); setEditingRule(null); }}
          />
        )}

        {rulesLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : !rules || rules.length === 0 ? (
          <div className="text-slate-400 text-sm">{t("alerts.noRules")}</div>
        ) : (
          <div className="space-y-2">
            {rules.map((rule) => (
              <RuleRow
                key={rule.id}
                rule={rule}
                onEdit={() => setEditingRule(rule)}
                onDelete={() => handleDelete(rule.id)}
                onToggle={() => handleToggle(rule)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Rule Row (保留现有) ────────────────────────────────
function RuleRow({
  rule,
  onEdit,
  onDelete,
  onToggle,
}: {
  rule: AlertRule;
  onEdit: () => void;
  onDelete: () => void;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const firstCond = rule.dsl.when[0];
  const metric = firstCond?.metric ?? "";
  const op = firstCond?.op ?? "";
  const value = firstCond?.value != null ? String(firstCond.value) : "—";
  const ruleType = METRIC_TO_RULE_TYPE[metric] ?? metric;

  return (
    <div className="bg-slate-800/80 rounded-lg px-3 py-2 flex items-center justify-between border border-slate-700/50">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggle}
          className={`w-8 h-4 rounded-full relative transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 ${
            rule.is_active ? "bg-green-600" : "bg-slate-600"
          }`}
          aria-label={rule.is_active ? t("alerts.disable") : t("alerts.enable")}
        >
          <span
            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
              rule.is_active ? "left-4" : "left-0.5"
            }`}
          />
        </button>
        <div>
          <span className="font-mono font-bold text-sm">{rule.name}</span>
          <span className="text-xs text-slate-400 ml-2">
            {t(`alerts.ruleTypes.${ruleType}`, ruleType)} {op} {value}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onEdit} className="text-xs text-slate-400 hover:text-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-400 rounded">
          {t("alerts.edit")}
        </button>
        <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300 focus:outline-none focus:ring-1 focus:ring-red-400 rounded">
          {t("alerts.delete")}
        </button>
      </div>
    </div>
  );
}

// ── Push Status Badge ──────────────────────────────────
function PushStatusBadge({
  status,
  error,
  onSubscribe,
}: {
  status: string;
  error: string | null;
  onSubscribe: () => void;
}) {
  const { t } = useTranslation();

  if (status === "unsupported") {
    return <span className="text-xs text-slate-500">{t("alerts.push.unsupported")}</span>;
  }
  if (status === "subscribed") {
    return (
      <span className="text-xs text-green-400 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-green-400" aria-hidden="true" />
        {t("alerts.push.subscribed")}
      </span>
    );
  }
  if (status === "subscribing") {
    return <span className="text-xs text-yellow-400">{t("alerts.push.subscribing")}</span>;
  }
  return (
    <button
      onClick={onSubscribe}
      className="text-xs px-3 py-1.5 rounded bg-slate-700 text-slate-200 hover:bg-slate-600 flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-slate-400"
      title={error || t("alerts.push.enable")}
    >
      <span className="w-2 h-2 rounded-full bg-slate-500" aria-hidden="true" />
      {t("alerts.push.enable")}
    </button>
  );
}
