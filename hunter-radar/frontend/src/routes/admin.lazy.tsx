/**
 * P4-01: Admin 管理面板 — 5-Tab 重构 (PRD §3.8)
 *
 * Tabs:
 * 1. ETL Controls — 触发 DAG + 回测 + 状态
 * 2. Feature Flags — 开关 + 灰度百分比
 * 3. Users & Quota — tier 编辑 + quota 覆盖
 * 4. Audit Log — 可搜索操作日志 (actor/timestamp/diff)
 * 5. Attribution — 事件仪表盘 + funnel
 *
 * Access: 403 → 权限不足提示 (role-gated)
 */
import { useState, useMemo } from "react";
import { createLazyRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";
import { toast } from "@/components/common/Toast";

export const Route = createLazyRoute("/admin")({
  component: AdminPage,
});

// ── Types ─────────────────────────────────────────

type AdminTab = "etl" | "flags" | "users" | "audit" | "attribution";

/** 统一 403/404 降级:返回 null 表示服务不可用 */
function degrade<T>(e: unknown): T | null | never {
  if (e instanceof ApiError && (e.status === 403 || e.status === 404 || e.status === 501)) {
    return null;
  }
  throw e;
}

// ── Main Page ─────────────────────────────────────

function AdminPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<AdminTab>("etl");

  const TABS: Array<{ key: AdminTab; label: string }> = [
    { key: "etl", label: t("admin.tabEtl") },
    { key: "flags", label: t("admin.tabFlags") },
    { key: "users", label: t("admin.tabUsers") },
    { key: "audit", label: t("admin.tabAudit") },
    { key: "attribution", label: t("admin.tabAttribution") },
  ];

  return (
    <div className="space-y-4 max-w-4xl">
      <header>
        <h1 className="text-2xl font-bold">{t("admin.title")}</h1>
        <p className="text-sm text-slate-400 mt-1">{t("admin.subtitle")}</p>
      </header>

      {/* Tab bar (PRD §3.8) */}
      <div role="tablist" aria-label={t("admin.title")} className="flex gap-1 border-b border-slate-800 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap focus:outline-none focus:ring-1 focus:ring-slate-400 rounded-t ${
              activeTab === tab.key
                ? "border-red-500 text-slate-100"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={TABS.find((tb) => tb.key === activeTab)?.label}>
        {activeTab === "etl" && <EtlTab />}
        {activeTab === "flags" && <FeatureFlagsTab />}
        {activeTab === "users" && <UsersQuotaTab />}
        {activeTab === "audit" && <AuditLogTab />}
        {activeTab === "attribution" && <AttributionTab />}
      </div>

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}

// ── Tab 1: ETL Controls ───────────────────────────

function EtlTab() {
  const { t } = useTranslation();
  const [etlStatus, setEtlStatus] = useState<string | null>(null);
  const [etlLoading, setEtlLoading] = useState(false);
  const [btStatus, setBtStatus] = useState<string | null>(null);
  const [btLoading, setBtLoading] = useState(false);
  const [btSymbol, setBtSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);

  const runETL = async () => {
    setEtlLoading(true);
    setEtlStatus(null);
    setError(null);
    try {
      const result = await api.adminRunETL();
      setEtlStatus(result.status);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError(t("admin.forbidden"));
      else setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setEtlLoading(false);
    }
  };

  const runBacktest = async () => {
    setBtLoading(true);
    setBtStatus(null);
    setError(null);
    try {
      const body = btSymbol.trim() ? { symbol: btSymbol.trim().toUpperCase() } : undefined;
      const result = await api.adminRunBacktest(body);
      setBtStatus(result.status);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError(t("admin.forbidden"));
      else setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setBtLoading(false);
    }
  };

  return (
    <div className="space-y-4 pt-2">
      {error && (
        <div role="alert" className="text-red-400 text-sm bg-red-900/20 rounded p-3 border border-red-800/30">
          {error}
        </div>
      )}

      {/* ETL trigger */}
      <section className="bg-slate-800/80 rounded-lg p-4 border border-slate-700/50 space-y-3">
        <h2 className="font-semibold text-base">{t("admin.etlTitle")}</h2>
        <p className="text-xs text-slate-400">{t("admin.etlDescription")}</p>
        <button
          onClick={runETL}
          disabled={etlLoading}
          className="px-4 py-2 rounded bg-hunter-red text-white text-sm disabled:opacity-50 hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-red-400"
        >
          {etlLoading ? t("common.loading") : t("admin.runETL")}
        </button>
        {etlStatus && (
          <div className="text-xs text-green-400" role="status">
            {t("admin.etlResult")}: {etlStatus}
          </div>
        )}
      </section>

      {/* Backtest */}
      <section className="bg-slate-800/80 rounded-lg p-4 border border-slate-700/50 space-y-3">
        <h2 className="font-semibold text-base">{t("admin.backtestTitle")}</h2>
        <p className="text-xs text-slate-400">{t("admin.backtestDescription")}</p>
        <div className="flex gap-2">
          <input
            value={btSymbol}
            onChange={(e) => setBtSymbol(e.target.value)}
            placeholder={t("admin.symbolPlaceholder")}
            className="flex-1 px-2 py-1 bg-slate-900 rounded text-slate-100 text-sm uppercase"
            aria-label={t("admin.symbolPlaceholder")}
          />
          <button
            onClick={runBacktest}
            disabled={btLoading}
            className="px-4 py-2 rounded bg-hunter-red text-white text-sm disabled:opacity-50 hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-red-400"
          >
            {btLoading ? t("common.loading") : t("admin.runBacktest")}
          </button>
        </div>
        {btStatus && (
          <div className="text-xs text-green-400" role="status">
            {t("admin.backtestResult")}: {btStatus}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Tab 2: Feature Flags (灰度发布) ────────────────

function FeatureFlagsTab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rolloutDrafts, setRolloutDrafts] = useState<Record<string, number>>({});

  const flags = useQuery({
    queryKey: ["admin", "feature-flags"],
    queryFn: async () => {
      try {
        return await api.getAllFeatureFlags();
      } catch (e) {
        return degrade<Awaited<ReturnType<typeof api.getAllFeatureFlags>>>(e);
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  const updateFlag = useMutation({
    mutationFn: ({ flag, enabled, rollout_pct }: { flag: string; enabled?: boolean; rollout_pct?: number }) =>
      api.updateFeatureFlag(flag, { enabled, rollout_pct }),
    onSuccess: () => {
      toast.success(t("admin.flagUpdated"));
      queryClient.invalidateQueries({ queryKey: ["admin", "feature-flags"] });
    },
    onError: (e) => {
      toast.error(
        e instanceof ApiError && e.status === 403 ? t("admin.forbidden") : t("common.error"),
      );
    },
  });

  if (flags.isLoading) return <div className="text-sm text-slate-400 pt-4">{t("common.loading")}</div>;

  if (!flags.data) {
    return (
      <div className="text-sm text-slate-500 pt-4 bg-slate-900/50 rounded p-4">
        {t("admin.flagsUnavailable")}
      </div>
    );
  }

  const entries = Object.entries(flags.data.flags);

  return (
    <div className="space-y-2 pt-2">
      {entries.length === 0 && (
        <div className="text-sm text-slate-500">{t("admin.noFlags")}</div>
      )}
      {entries.map(([flag, info]) => {
        const draft = rolloutDrafts[flag];
        return (
          <div
            key={flag}
            className="flex items-center gap-3 flex-wrap bg-slate-800/60 rounded-lg px-4 py-3 border border-slate-700/50"
          >
            {/* Toggle switch */}
            <button
              role="switch"
              aria-checked={info.enabled}
              aria-label={`${flag} ${info.enabled ? "ON" : "OFF"}`}
              onClick={() => updateFlag.mutate({ flag, enabled: !info.enabled })}
              className={`relative w-10 h-5 rounded-full transition-colors shrink-0 focus:outline-none focus:ring-2 focus:ring-slate-400 ${
                info.enabled ? "bg-emerald-600" : "bg-slate-600"
              }`}
            >
              <span
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                  info.enabled ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>

            <div className="flex-1 min-w-0">
              <div className="font-mono text-sm text-slate-200 truncate">{flag}</div>
              <div className="text-[11px] text-slate-500">{t(`admin.flagReason.${info.reason}`, info.reason)}</div>
            </div>

            {/* Rollout percentage */}
            <div className="flex items-center gap-2">
              <label className="text-[11px] text-slate-400" htmlFor={`rollout-${flag}`}>
                {t("admin.rolloutPct")}
              </label>
              <input
                id={`rollout-${flag}`}
                type="number"
                min={0}
                max={100}
                value={draft ?? 100}
                onChange={(e) =>
                  setRolloutDrafts((prev) => ({ ...prev, [flag]: Number(e.target.value) }))
                }
                className="w-16 px-1.5 py-0.5 bg-slate-900 rounded text-xs font-mono text-slate-200"
              />
              <button
                onClick={() => updateFlag.mutate({ flag, rollout_pct: draft ?? 100 })}
                disabled={updateFlag.isPending}
                className="px-2 py-1 text-[11px] rounded bg-slate-700 text-slate-200 hover:bg-slate-600 disabled:opacity-50"
              >
                {t("admin.apply")}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Tab 3: Users & Quota ──────────────────────────

function UsersQuotaTab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [quotaDrafts, setQuotaDrafts] = useState<Record<string, number>>({});

  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => {
      try {
        return await api.adminListUsers();
      } catch (e) {
        return degrade<Awaited<ReturnType<typeof api.adminListUsers>>>(e);
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  const updateUser = useMutation({
    mutationFn: ({ id, tier, quota_limit }: { id: string; tier?: "free" | "pro"; quota_limit?: number }) =>
      api.adminUpdateUser(id, { tier, quota_limit }),
    onSuccess: () => {
      toast.success(t("admin.userUpdated"));
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (e) => {
      toast.error(
        e instanceof ApiError && e.status === 403 ? t("admin.forbidden") : t("common.error"),
      );
    },
  });

  if (users.isLoading) return <div className="text-sm text-slate-400 pt-4">{t("common.loading")}</div>;

  if (!users.data) {
    return (
      <div className="text-sm text-slate-500 pt-4 bg-slate-900/50 rounded p-4">
        {t("admin.usersUnavailable")}
      </div>
    );
  }

  return (
    <div className="pt-2 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-slate-500 border-b border-slate-800">
            <th className="py-2 pr-4 font-medium">{t("admin.colUser")}</th>
            <th className="py-2 pr-4 font-medium">{t("admin.colTier")}</th>
            <th className="py-2 pr-4 font-medium text-right">{t("admin.colQuotaUsed")}</th>
            <th className="py-2 pr-4 font-medium text-right">{t("admin.colQuotaLimit")}</th>
            <th className="py-2 font-medium">{t("admin.colActions")}</th>
          </tr>
        </thead>
        <tbody>
          {users.data.map((u) => (
            <tr key={u.id} className="border-b border-slate-800/50 last:border-0">
              <td className="py-2.5 pr-4">
                <div className="font-mono text-slate-200">{u.username}</div>
                <div className="text-[10px] text-slate-500 font-mono">{u.id.slice(0, 8)}…</div>
              </td>
              <td className="py-2.5 pr-4">
                <select
                  value={u.tier}
                  onChange={(e) =>
                    updateUser.mutate({ id: u.id, tier: e.target.value as "free" | "pro" })
                  }
                  className={`px-2 py-1 rounded text-xs font-bold border focus:outline-none focus:ring-1 focus:ring-slate-400 ${
                    u.tier === "pro"
                      ? "bg-red-900/40 text-red-300 border-red-700/50"
                      : "bg-slate-800 text-slate-300 border-slate-700"
                  }`}
                  aria-label={`${u.username} tier`}
                >
                  <option value="free">FREE</option>
                  <option value="pro">PRO</option>
                </select>
              </td>
              <td className="py-2.5 pr-4 font-mono text-right text-slate-300">{u.quota_used}</td>
              <td className="py-2.5 pr-4 text-right">
                <input
                  type="number"
                  min={-1}
                  value={quotaDrafts[u.id] ?? u.quota_limit}
                  onChange={(e) =>
                    setQuotaDrafts((prev) => ({ ...prev, [u.id]: Number(e.target.value) }))
                  }
                  className="w-20 px-1.5 py-0.5 bg-slate-900 rounded text-xs font-mono text-slate-200 text-right"
                  aria-label={`${u.username} quota limit`}
                />
              </td>
              <td className="py-2.5">
                <button
                  onClick={() => updateUser.mutate({ id: u.id, quota_limit: quotaDrafts[u.id] ?? u.quota_limit })}
                  disabled={updateUser.isPending}
                  className="px-2 py-1 text-[11px] rounded bg-slate-700 text-slate-200 hover:bg-slate-600 disabled:opacity-50"
                >
                  {t("admin.apply")}
                </button>
              </td>
            </tr>
          ))}
          {users.data.length === 0 && (
            <tr>
              <td colSpan={5} className="py-6 text-center text-slate-500 text-sm">
                {t("admin.noUsers")}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Tab 4: Audit Log ──────────────────────────────

function AuditLogTab() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");

  // 简单 debounce
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const onSearch = (v: string) => {
    setSearch(v);
    if (timer) clearTimeout(timer);
    setTimer(
      setTimeout(() => setDebouncedQ(v.trim()), 400),
    );
  };

  const audit = useQuery({
    queryKey: ["admin", "audit-log", debouncedQ],
    queryFn: async () => {
      try {
        return await api.adminGetAuditLog({ q: debouncedQ || undefined, limit: 100 });
      } catch (e) {
        return degrade<Awaited<ReturnType<typeof api.adminGetAuditLog>>>(e);
      }
    },
    staleTime: 30_000,
    retry: 0,
  });

  if (!audit.data && !audit.isLoading) {
    return (
      <div className="text-sm text-slate-500 pt-4 bg-slate-900/50 rounded p-4">
        {t("admin.auditUnavailable")}
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-2">
      <input
        type="search"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        placeholder={t("admin.auditSearchPlaceholder")}
        className="w-full max-w-sm px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-400"
        aria-label={t("admin.auditSearchPlaceholder")}
      />

      {audit.isLoading ? (
        <div className="text-sm text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-800">
                <th className="py-2 pr-4 font-medium">{t("admin.colTime")}</th>
                <th className="py-2 pr-4 font-medium">{t("admin.colActor")}</th>
                <th className="py-2 pr-4 font-medium">{t("admin.colAction")}</th>
                <th className="py-2 pr-4 font-medium">{t("admin.colTarget")}</th>
                <th className="py-2 font-medium">{t("admin.colDiff")}</th>
              </tr>
            </thead>
            <tbody>
              {(audit.data ?? []).map((entry) => (
                <tr key={entry.id} className="border-b border-slate-800/50 last:border-0 align-top">
                  <td className="py-2 pr-4 font-mono text-xs text-slate-400 whitespace-nowrap">
                    {entry.created_at.slice(0, 16).replace("T", " ")}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-200">{entry.actor}</td>
                  <td className="py-2 pr-4">
                    <span className="px-1.5 py-0.5 rounded bg-slate-700/60 text-[11px] font-mono text-slate-200">
                      {entry.action}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-400">{entry.target}</td>
                  <td className="py-2 font-mono text-[10px] text-slate-500 max-w-xs">
                    {entry.diff ? (
                      <details>
                        <summary className="cursor-pointer text-slate-400 hover:text-slate-200">
                          {t("admin.viewDiff")}
                        </summary>
                        <pre className="mt-1 bg-slate-900 rounded p-2 overflow-x-auto text-[10px] leading-relaxed">
                          {JSON.stringify(entry.diff, null, 1)}
                        </pre>
                      </details>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
              {(audit.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500 text-sm">
                    {t("admin.noAuditEntries")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tab 5: Attribution (Analytics 仪表盘) ──────────

function AttributionTab() {
  const { t } = useTranslation();

  const summary = useQuery({
    queryKey: ["admin", "analytics-summary"],
    queryFn: async () => {
      try {
        return await api.adminGetAnalyticsSummary();
      } catch (e) {
        return degrade<Awaited<ReturnType<typeof api.adminGetAnalyticsSummary>>>(e);
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  const maxFunnel = useMemo(
    () => Math.max(1, ...(summary.data?.funnel.map((f) => f.count) ?? [1])),
    [summary.data],
  );

  if (summary.isLoading) return <div className="text-sm text-slate-400 pt-4">{t("common.loading")}</div>;

  if (!summary.data) {
    return (
      <div className="text-sm text-slate-500 pt-4 bg-slate-900/50 rounded p-4">
        {t("admin.attributionUnavailable")}
      </div>
    );
  }

  const { total_events, events_by_type, funnel } = summary.data;
  const typeEntries = Object.entries(events_by_type).sort((a, b) => b[1] - a[1]);
  const maxType = Math.max(1, ...typeEntries.map(([, v]) => v));

  return (
    <div className="space-y-5 pt-2">
      {/* Total */}
      <div className="bg-slate-800/60 rounded-lg px-4 py-3 border border-slate-700/50 inline-block">
        <div className="text-xs text-slate-400">{t("admin.totalEvents")}</div>
        <div className="text-2xl font-mono font-bold text-slate-100">
          {total_events.toLocaleString()}
        </div>
      </div>

      {/* Events by type */}
      <section>
        <h2 className="text-sm font-semibold text-slate-300 mb-2">{t("admin.eventsByType")}</h2>
        <div className="space-y-1.5">
          {typeEntries.map(([type, count]) => (
            <div key={type} className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400 w-40 truncate shrink-0">{type}</span>
              <div className="flex-1 h-4 bg-slate-800 rounded overflow-hidden">
                <div
                  className="h-full bg-sky-600/70 rounded transition-all"
                  style={{ width: `${(count / maxType) * 100}%` }}
                />
              </div>
              <span className="font-mono text-xs text-slate-300 w-16 text-right shrink-0">
                {count.toLocaleString()}
              </span>
            </div>
          ))}
          {typeEntries.length === 0 && (
            <div className="text-sm text-slate-500">{t("admin.noEvents")}</div>
          )}
        </div>
      </section>

      {/* Funnel */}
      <section>
        <h2 className="text-sm font-semibold text-slate-300 mb-2">{t("admin.funnel")}</h2>
        <div className="space-y-1.5">
          {funnel.map((stage) => (
            <div key={stage.stage} className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400 w-40 truncate shrink-0">{stage.stage}</span>
              <div className="flex-1 h-4 bg-slate-800 rounded overflow-hidden">
                <div
                  className="h-full bg-emerald-600/70 rounded transition-all"
                  style={{ width: `${(stage.count / maxFunnel) * 100}%` }}
                />
              </div>
              <span className="font-mono text-xs text-slate-300 w-16 text-right shrink-0">
                {stage.count.toLocaleString()}
              </span>
            </div>
          ))}
          {funnel.length === 0 && (
            <div className="text-sm text-slate-500">{t("admin.noFunnel")}</div>
          )}
        </div>
      </section>
    </div>
  );
}
