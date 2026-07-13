/**
 * FE-140: 预警中心页完整实现
 *
 * - 规则管理区:创建/编辑/删除/启用禁用规则
 * - 历史事件流:无限滚动列表
 * - 集成 AlertRuleForm(FE-141) + Web Push(FE-142)
 * - i18n 全覆盖
 */
import { useState, useCallback, useEffect } from "react";
import { createRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Route as RootRoute } from "./__root";
import { api, ApiError } from "../lib/api";
import { AlertRuleForm, type AlertRuleFormData } from "@/components/common/AlertRuleForm";
import { useWebPush } from "@/features/useWebPush";
import { SkeletonCard } from "@/components/common/Skeleton";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/alerts",
  component: AlertsPage,
});

type AlertRule = {
  id: number;
  symbol: string;
  rule_type: string;
  threshold: number;
  operator: string;
  enabled: boolean;
  created_at: string;
};

type AlertHistoryItem = {
  id: number;
  alert_id: number;
  symbol: string;
  triggered_at: string;
  value: number;
  threshold: number;
};

// ─── Main Page ───────────────────────────────────────────────────

function AlertsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyItems, setHistoryItems] = useState<AlertHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);

  // Web Push
  const { status: pushStatus, subscribe: pushSubscribe, errorMessage: pushError } = useWebPush();

  // Auto-subscribe on first visit
  useEffect(() => {
    if (pushStatus === "unsubscribed") {
      pushSubscribe();
    }
  }, [pushStatus, pushSubscribe]);

  // Fetch rules
  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => api.listAlerts(),
    staleTime: 60_000,
  });

  // Fetch history
  const loadHistory = useCallback(async (page: number, append = false) => {
    setLoadingMore(true);
    try {
      const data = await api.listAlertHistory(page, 20);
      if (append) {
        setHistoryItems((prev) => [...prev, ...data.items]);
      } else {
        setHistoryItems(data.items);
      }
      setHistoryTotal(data.total);
      setHistoryPage(page);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    loadHistory(1);
  }, [loadHistory]);

  // Create rule
  const handleCreate = async (data: AlertRuleFormData) => {
    setError(null);
    try {
      await api.createAlert(data);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  // Update rule
  const handleUpdate = async (data: AlertRuleFormData) => {
    if (!editingRule) return;
    setError(null);
    try {
      await api.updateAlert(editingRule.id, {
        rule_type: data.rule_type,
        threshold: data.threshold,
        operator: data.operator,
      });
      setEditingRule(null);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  // Delete rule
  const handleDelete = async (id: number) => {
    try {
      await api.deleteAlert(id);
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  // Toggle enable/disable
  const handleToggle = async (rule: AlertRule) => {
    try {
      await api.updateAlert(rule.id, { enabled: !rule.enabled });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  const hasMore = historyItems.length < historyTotal;

  return (
    <div className="space-y-4">
      {/* Header */}
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("alerts.title")}</h1>
        <div className="flex items-center gap-2">
          {/* Push status indicator */}
          <PushStatusBadge status={pushStatus} error={pushError} onSubscribe={pushSubscribe} />
          <button
            onClick={() => { setShowForm(true); setEditingRule(null); }}
            className="px-3 py-1 rounded bg-hunter-red text-white text-sm hover:opacity-80"
          >
            + {t("alerts.createRule")}
          </button>
        </div>
      </header>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {/* Form overlay */}
      {(showForm || editingRule) && (
        <AlertRuleForm
          initial={editingRule ? {
            symbol: editingRule.symbol,
            rule_type: editingRule.rule_type as AlertRuleFormData["rule_type"],
            threshold: editingRule.threshold,
            operator: editingRule.operator as AlertRuleFormData["operator"],
          } : undefined}
          onSubmit={editingRule ? handleUpdate : handleCreate}
          onCancel={() => { setShowForm(false); setEditingRule(null); }}
        />
      )}

      {/* Rules section */}
      <section>
        <h2 className="text-lg font-semibold mb-2">{t("alerts.rulesTitle")}</h2>
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

      {/* History section */}
      <section>
        <h2 className="text-lg font-semibold mb-2">{t("alerts.historyTitle")}</h2>
        {historyItems.length === 0 && !loadingMore ? (
          <div className="text-slate-400 text-sm">{t("alerts.noHistory")}</div>
        ) : (
          <div className="space-y-1">
            {historyItems.map((item) => (
              <HistoryRow key={item.id} item={item} />
            ))}
            {hasMore && (
              <button
                onClick={() => loadHistory(historyPage + 1, true)}
                disabled={loadingMore}
                className="w-full py-2 text-sm text-slate-400 hover:text-slate-200 disabled:opacity-50"
              >
                {loadingMore ? t("common.loading") : t("alerts.loadMore")}
              </button>
            )}
          </div>
        )}
      </section>

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}

// ─── Rule Row ────────────────────────────────────────────────────

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
  return (
    <div className="bg-slate-800/80 rounded-lg px-3 py-2 flex items-center justify-between border border-slate-700/50">
      <div className="flex items-center gap-3">
        {/* Enable/Disable toggle */}
        <button
          onClick={onToggle}
          className={`w-8 h-4 rounded-full relative transition-colors ${
            rule.enabled ? "bg-green-600" : "bg-slate-600"
          }`}
          aria-label={rule.enabled ? t("alerts.disable") : t("alerts.enable")}
        >
          <span
            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
              rule.enabled ? "left-4" : "left-0.5"
            }`}
          />
        </button>

        <div>
          <span className="font-mono font-bold text-sm">{rule.symbol}</span>
          <span className="text-xs text-slate-400 ml-2">
            {t(`alerts.ruleTypes.${rule.rule_type}`)} {rule.operator} {rule.threshold}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button onClick={onEdit} className="text-xs text-slate-400 hover:text-slate-200">
          {t("alerts.edit")}
        </button>
        <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-300">
          {t("alerts.delete")}
        </button>
      </div>
    </div>
  );
}

// ─── History Row ─────────────────────────────────────────────────

function HistoryRow({ item }: { item: AlertHistoryItem }) {
  const { t } = useTranslation();
  return (
    <div className="bg-slate-800/50 rounded px-3 py-2 flex items-center justify-between text-sm border border-slate-700/30">
      <div className="flex items-center gap-2">
        <span className="font-mono font-bold">{item.symbol}</span>
        <span className="text-xs text-slate-400">
          {t("alerts.triggered")}: {item.value != null ? item.value.toFixed(1) : "—"} ({t("alerts.threshold")}: {item.threshold})
        </span>
      </div>
      <span className="text-xs text-slate-500">
        {new Date(item.triggered_at).toLocaleString()}
      </span>
    </div>
  );
}

// ─── Push Status Badge ───────────────────────────────────────────

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
    return (
      <span className="text-xs text-slate-500" title={t("alerts.push.unsupported")}>
        {t("alerts.push.unsupported")}
      </span>
    );
  }

  if (status === "subscribed") {
    return (
      <span className="text-xs text-green-400 flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
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
      className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1"
      title={error || t("alerts.push.enable")}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
      {t("alerts.push.enable")}
    </button>
  );
}
