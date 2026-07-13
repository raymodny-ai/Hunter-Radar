/**
 * FE-133: 自选篮子雷达页 — CSS Grid 卡片阵列重构
 *
 * - 列表视图:CSS Grid 平铺式卡片阵列
 * - 详情视图:成员卡片含 Spark-Radar + Threat Score + EMA 箭头 + 减持红点
 * - 集成 BasketHistogram + BasketDangerCluster
 * - i18n 全覆盖,无硬编码中文
 */
import { useEffect, useState, useMemo, useCallback } from "react";
import { createRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Route as RootRoute } from "./__root";
import {
  api,
  ApiError,
  type BasketDTO,
  type BasketDistributionDTO,
} from "../lib/api";
import { SparkRadar } from "@/components/charts/SparkRadar";
import { BasketHistogram } from "@/components/charts/BasketHistogram";
import { BasketDangerCluster } from "@/components/radar/BasketDangerCluster";
import { SkeletonCard } from "@/components/common/Skeleton";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/basket",
  component: BasketPage,
});

type View = { kind: "list" } | { kind: "create" } | { kind: "detail"; basketId: number };

// ─── Threat Score per member (batch fetch) ──────────────────────

interface MemberThreat {
  total: number;
  module_options: number;
  module_short: number;
  module_divergence: number;
  module_insider: number;
  signal_lifecycle: string;
}

function useMemberThreats(tickers: string[]) {
  return useQuery({
    queryKey: ["basket-members-threat", tickers],
    queryFn: async () => {
      const results: Record<string, MemberThreat> = {};
      await Promise.all(
        tickers.map(async (t) => {
          try {
            const d = await api.getThreatScore(t);
            results[t] = {
              total: d.total,
              module_options: d.module_options,
              module_short: d.module_short,
              module_divergence: d.module_divergence,
              module_insider: d.module_insider,
              signal_lifecycle: d.signal_lifecycle,
            };
          } catch {
            // skip failed
          }
        }),
      );
      return results;
    },
    enabled: tickers.length > 0,
    staleTime: 30 * 60 * 1000,
  });
}

// ─── Main Page ───────────────────────────────────────────────────

function BasketPage() {
  const { t } = useTranslation();
  const [view, setView] = useState<View>({ kind: "list" });

  if (view.kind === "list") {
    return <BasketListView onCreate={() => setView({ kind: "create" })} onDetail={(id) => setView({ kind: "detail", basketId: id })} />;
  }
  if (view.kind === "create") {
    return (
      <CreateBasketView
        onCancel={() => setView({ kind: "list" })}
        onCreated={(b) => setView({ kind: "detail", basketId: b.id })}
      />
    );
  }
  return (
    <BasketDetailView
      basketId={view.basketId}
      onBack={() => setView({ kind: "list" })}
    />
  );
}

// ─── List View ───────────────────────────────────────────────────

function BasketListView({ onCreate, onDetail }: { onCreate: () => void; onDetail: (id: number) => void }) {
  const { t } = useTranslation();
  const [baskets, setBaskets] = useState<BasketDTO[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listBaskets();
      setBaskets(data);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("basket.title")}</h1>
        <button
          onClick={onCreate}
          className="px-3 py-1 rounded bg-hunter-red text-white text-sm hover:opacity-80"
        >
          + {t("basket.create")}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm">{t("common.error")}: {error}</div>}
      {loading && <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>}

      {!loading && baskets.length === 0 && (
        <div className="text-slate-400 text-sm">{t("basket.empty")}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {baskets.map((b) => (
          <div
            key={b.id}
            className="relative bg-slate-800/80 rounded-lg p-4 pr-9 cursor-pointer hover:bg-slate-700/80 transition-colors border border-slate-700/50 group"
          >
            <div onClick={() => onDetail(b.id)}>
              <div className="font-semibold text-base">{b.name}</div>
              {b.description && (
                <div className="text-xs text-slate-400 mt-1 line-clamp-2">{b.description}</div>
              )}
              <div className="text-xs text-slate-500 mt-3">
                {b.member_count} {t("basket.members")} · {t("basket.updated")} {b.updated_at}
              </div>
            </div>
            {/* Delete basket (always visible) */}
            <button
              onClick={async (e) => {
                e.stopPropagation();
                if (!confirm(t("basket.confirmDelete"))) return;
                try {
                  await api.deleteBasket(b.id);
                  refresh();
                } catch (err) {
                  alert(t("common.error") + ': ' + (err instanceof ApiError ? `API ${err.status}` : String(err)));
                }
              }}
              className="absolute top-1.5 right-1.5 w-6 h-6 flex items-center justify-center rounded text-sm text-slate-500 hover:text-red-400 hover:bg-slate-900/60 transition-colors"
              aria-label={t("basket.deleteBasket")}
              title={t("basket.deleteBasket")}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}

// ─── Create View ─────────────────────────────────────────────────

function CreateBasketView({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (b: BasketDTO) => void;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) {
      setError(t("basket.nameRequired"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const b = await api.createBasket({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      onCreated(b);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3 max-w-md">
      <h1 className="text-2xl font-bold">{t("basket.createTitle")}</h1>
      <label className="block">
        <span className="text-sm text-slate-300">{t("basket.name")} ({t("basket.required")})</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={80}
          className="mt-1 w-full px-2 py-1 bg-slate-800 rounded text-slate-100"
          placeholder={t("basket.namePlaceholder")}
        />
      </label>
      <label className="block">
        <span className="text-sm text-slate-300">{t("basket.description")} ({t("basket.optional")})</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          className="mt-1 w-full px-2 py-1 bg-slate-800 rounded text-slate-100"
          rows={3}
        />
      </label>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <div className="flex gap-2">
        <button onClick={submit} disabled={submitting} className="px-3 py-1 rounded bg-hunter-red text-white text-sm disabled:opacity-50">
          {submitting ? t("common.loading") : t("basket.create")}
        </button>
        <button onClick={onCancel} className="px-3 py-1 rounded bg-slate-700 text-slate-100 text-sm">
          {t("basket.cancel")}
        </button>
      </div>
    </div>
  );
}

// ─── Detail View ─────────────────────────────────────────────────

function BasketDetailView({
  basketId,
  onBack,
}: {
  basketId: number;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const [newTickers, setNewTickers] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fetch basket + members + distribution
  const { data, isLoading } = useQuery({
    queryKey: ["basket-detail", basketId],
    queryFn: async () => {
      const [basket, members, distribution] = await Promise.all([
        api.getBasket(basketId),
        api.listBasketMembers(basketId),
        api.getBasketDistribution(basketId, 30).catch(() => null),
      ]);
      return { basket, members, distribution };
    },
  });

  // Fetch threat scores for all members
  const tickers = useMemo(
    () => (data?.members ?? []).map((m) => m.ticker),
    [data?.members],
  );
  const { data: threats, isLoading: threatsLoading } = useMemberThreats(tickers);

  const addMembers = async () => {
    const tk = newTickers
      .split(/[\s,]+/)
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0);
    if (tk.length === 0) return;
    setError(null);
    try {
      const r = await api.addBasketMembers(basketId, tk);
      setNewTickers("");
      if (r.inserted < tk.length) {
        if (r.inserted === 0) setError(t("basket.alreadyExists"));
        else setError(t("basket.partialAdd", { inserted: r.inserted, skipped: r.submitted - r.inserted }));
      }
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  const removeMember = async (ticker: string) => {
    try {
      await api.removeBasketMember(basketId, ticker);
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  const deleteBasket = async () => {
    if (!confirm(t("basket.confirmDelete"))) return;
    try {
      await api.deleteBasket(basketId);
      onBack();
    } catch (e) {
      setError(e instanceof ApiError ? `API ${e.status}` : String(e));
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  if (!data?.basket) {
    return <div className="text-red-400 text-sm">{t("basket.notFound")}</div>;
  }

  const { basket, members, distribution } = data;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={onBack} className="text-sm text-slate-400 hover:text-slate-200">
            ← {t("basket.backToList")}
          </button>
          <h1 className="text-2xl font-bold mt-1">{basket.name}</h1>
          {basket.description && (
            <div className="text-sm text-slate-400 mt-1">{basket.description}</div>
          )}
        </div>
        <button onClick={deleteBasket} className="px-3 py-1.5 text-sm rounded bg-red-900/40 text-red-300 border border-red-800/50 hover:bg-red-900/60 hover:text-red-200 transition-colors">
          🗑 {t("basket.deleteBasket")}
        </button>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      {/* FE-136: Danger Cluster Alert */}
      <BasketDangerCluster distribution={distribution} />

      {/* Add member input */}
      <section>
        <h2 className="text-lg font-semibold mb-2">{t("basket.membersTitle", { count: members.length })}</h2>
        <div className="flex gap-2 mb-3">
          <input
            value={newTickers}
            onChange={(e) => setNewTickers(e.target.value)}
            placeholder="AAPL, TSLA, MSFT"
            className="flex-1 px-2 py-1 bg-slate-800 rounded text-slate-100 text-sm"
          />
          <button onClick={addMembers} className="px-3 py-1 rounded bg-hunter-red text-white text-sm">
            + {t("basket.add")}
          </button>
        </div>

        {members.length === 0 ? (
          <div className="text-slate-400 text-sm">{t("basket.noMembers")}</div>
        ) : (
          /* FE-133: CSS Grid card array */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {members.map((m) => {
              const th = threats?.[m.ticker];
              return (
                <MemberCard
                  key={m.ticker}
                  ticker={m.ticker}
                  threat={th}
                  loading={threatsLoading}
                  onRemove={() => removeMember(m.ticker)}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* FE-135: Histogram */}
      <section>
        <h2 className="text-lg font-semibold mb-2">{t("basket.histogram.title")}</h2>
        <BasketHistogram distribution={distribution} isLoading={isLoading} className="h-[220px]" />
      </section>

      {/* Distribution stats */}
      {distribution && (
        <section>
          <h2 className="text-lg font-semibold mb-2">{t("basket.stats.title")}</h2>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2 text-sm">
            <StatCard label={t("basket.stats.mean")} v={distribution.mean} />
            <StatCard label="p25" v={distribution.p25} />
            <StatCard label="p50" v={distribution.p50} />
            <StatCard label="p75" v={distribution.p75} />
            <StatCard label="p90" v={distribution.p90} />
            <StatCard label="p99" v={distribution.p99} />
            <StatCard label={t("basket.stats.min")} v={distribution.min_score} />
            <StatCard label={t("basket.stats.max")} v={distribution.max_score} />
            <StatCard label={t("basket.stats.tickers")} v={distribution.ticker_count} />
            <StatCard label={t("basket.stats.days")} v={distribution.day_count} />
          </div>
        </section>
      )}

      <div className="text-xs text-slate-500">{t("common.disclaimer")}</div>
    </div>
  );
}

// ─── Member Card (with SparkRadar) ──────────────────────────────

function MemberCard({
  ticker,
  threat,
  loading,
  onRemove,
}: {
  ticker: string;
  threat: MemberThreat | undefined;
  loading: boolean;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const score = threat?.total;
  const lifecycle = threat?.signal_lifecycle;

  // Lifecycle color
  const lcColor =
    lifecycle === "red" ? "text-hunter-red" :
    lifecycle === "yellow" ? "text-hunter-yellow" :
    lifecycle === "green" ? "text-hunter-green" :
    "text-slate-400";

  // EMA arrow (score direction hint)
  const arrow = score !== undefined ? (score >= 70 ? "▲" : score >= 40 ? "◆" : "▼") : "";
  const arrowColor = score !== undefined ? (score >= 70 ? "text-red-400" : score >= 40 ? "text-yellow-400" : "text-green-400") : "";

  return (
    <div className="bg-slate-800/80 rounded-lg p-3 border border-slate-700/50 flex flex-col gap-2 relative group hover:border-slate-600/80 transition-colors">
      {/* Remove button (always visible) */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (confirm(t("basket.confirmRemoveMember", { ticker }))) onRemove();
        }}
        className="absolute top-1.5 right-1.5 w-5 h-5 flex items-center justify-center rounded text-xs text-slate-500 hover:text-red-400 hover:bg-slate-700/60 transition-colors"
        aria-label={t("basket.removeMember")}
        title={t("basket.removeMember")}
      >
        ×
      </button>

      <div className="flex items-center gap-2">
        {/* SparkRadar */}
        <SparkRadar
          moduleOptions={threat?.module_options}
          moduleShort={threat?.module_short}
          moduleDivergence={threat?.module_divergence}
          moduleInsider={threat?.module_insider}
          size={64}
        />

        <div className="flex-1 min-w-0">
          {/* Ticker */}
          <div className="flex items-center gap-1.5">
            <span className="font-mono font-bold text-base">{ticker}</span>
            {/* Insider red dot (C-level sell indicator) */}
            {threat?.module_insider !== undefined && threat.module_insider >= 60 && (
              <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" title={t("basket.insiderAlert")} />
            )}
          </div>

          {/* Threat Score */}
          {score !== undefined && score !== null ? (
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="font-mono text-lg font-bold" style={{
                color: score >= 80 ? "#FF5252" : score >= 60 ? "#f59e0b" : score >= 40 ? "#fb923c" : "#10b981"
              }}>
                {score.toFixed(0)}
              </span>
              <span className={`text-xs ${arrowColor}`}>{arrow}</span>
              <span className={`text-xs ${lcColor}`}>{lifecycle}</span>
            </div>
          ) : loading ? (
            <div className="text-xs text-slate-500">{t("common.loading")}</div>
          ) : (
            <div className="text-xs text-slate-500">{t("basket.noScore")}</div>
          )}
        </div>
      </div>

      {/* Module mini bars */}
      {threat && (
        <div className="grid grid-cols-4 gap-1 text-[10px]">
          <ModuleBar label={t("modules.options")} value={threat.module_options} color="#f97316" />
          <ModuleBar label={t("modules.short")} value={threat.module_short} color="#ef4444" />
          <ModuleBar label={t("modules.divergence")} value={threat.module_divergence} color="#a855f7" />
          <ModuleBar label={t("modules.insider")} value={threat.module_insider} color="#06b6d4" />
        </div>
      )}
    </div>
  );
}

// ─── Module Mini Bar ─────────────────────────────────────────────

function ModuleBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="w-full h-1 rounded-full bg-slate-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(100, value)}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-slate-500 truncate w-full text-center">{label.slice(0, 2)}</span>
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────────────

function StatCard({ label, v }: { label: string; v: number }) {
  return (
    <div className="bg-slate-800 rounded px-2 py-1">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="font-mono text-slate-100">
        {typeof v === "number" ? v.toFixed(2) : v}
      </div>
    </div>
  );
}
