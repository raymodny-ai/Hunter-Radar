/**
 * P2-01 / P2-02: Screener 重写 (PRD §3.3)
 *
 * - Filter Panel (left, collapsible): score range slider, module toggles, lifecycle multi-select
 * - Results Table: sortable, paginated (25/50/100), row click → detail
 * - Bulk actions: Add to Basket, Export CSV
 * - States: skeleton / "No matches" / quota exceeded → upgrade CTA
 */
import { createLazyRoute, useNavigate, Link } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useMemo, useState, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import { SkeletonTable } from "@/components/common/Skeleton";
import { Sparkline } from "@/components/common/Sparkline";
import { toast } from "@/components/common/Toast";
import { threatScoreColor, MODULE_COLORS, MODULE_KEYS, type ModuleKey } from "@/lib/design-tokens";

export const Route = createLazyRoute("/screener")({
  component: ScreenerPage,
});

// ── Types ──────────────────────────────────────────────
type SortColumn = "threat_score" | "rank" | "symbol";
type SortDir = "asc" | "desc";
type PageSize = 25 | 50 | 100;

const LIFECYCLE_OPTIONS = ["red", "yellow", "gray", "green", "init"] as const;
type Lifecycle = (typeof LIFECYCLE_OPTIONS)[number];

const LIFECYCLE_BADGE: Record<string, string> = {
  red: "text-red-400 bg-red-950/30 border-red-800/50",
  yellow: "text-amber-300 bg-amber-950/30 border-amber-800/50",
  gray: "text-slate-400 bg-slate-900 border-slate-700",
  green: "text-emerald-400 bg-emerald-950/30 border-emerald-800/50",
  init: "text-slate-500 bg-slate-900 border-slate-700",
};

// ── CSV 导出工具 ───────────────────────────────────────
function exportCsv(rows: Array<{ symbol: string; name: string; threat_score: number; signal_lifecycle: string; modules_active: string[] }>) {
  const header = "Symbol,Name,ThreatScore,Lifecycle,Modules";
  const lines = rows.map(
    (r) =>
      `${r.symbol},"${(r.name || "").replace(/"/g, '""')}",${r.threat_score.toFixed(1)},${r.signal_lifecycle},"${r.modules_active.join("/")}"`,
  );
  const blob = new Blob([`${header}\n${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `hunter-screener-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── 主页面 ─────────────────────────────────────────────
function ScreenerPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const queryClient = useQueryClient();

  // ── 数据 ─────────────────────────────────────────────
  const screener = useQuery({
    queryKey: ["screener", 100],
    queryFn: () => api.getScreener(100),
    retry: 1,
    staleTime: 1000 * 60 * 60,
  });

  const quotaExceeded = screener.isError && screener.error instanceof ApiError && screener.error.status === 429;

  // ── 筛选状态 (P2-01) ─────────────────────────────────
  const [filterOpen, setFilterOpen] = useState(true);
  const [scoreMin, setScoreMin] = useState(0);
  const [scoreMax, setScoreMax] = useState(100);
  const [moduleToggles, setModuleToggles] = useState<Set<ModuleKey>>(new Set());
  const [lifecycleSel, setLifecycleSel] = useState<Set<Lifecycle>>(new Set());

  // ── 排序 + 分页状态 (P2-02) ──────────────────────────
  const [sortCol, setSortCol] = useState<SortColumn>("threat_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [pageSize, setPageSize] = useState<PageSize>(50);
  const [page, setPage] = useState(0);

  // ── 批量选择 (P2-02) ─────────────────────────────────
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // ── Add to Basket mutation ───────────────────────────
  const baskets = useQuery({
    queryKey: ["baskets"],
    queryFn: () => api.listBaskets(),
    staleTime: 1000 * 60 * 5,
  });
  const [basketTarget, setBasketTarget] = useState<number | null>(null);
  const bulkAdd = useMutation({
    mutationFn: ({ basketId, tickers }: { basketId: number; tickers: string[] }) =>
      api.addBasketMembers(basketId, tickers),
    onSuccess: (data) => {
      toast.success(t("screener.bulkAdded", { count: data.inserted }));
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["baskets"] });
    },
    onError: () => toast.error(t("common.error")),
  });

  // ── 筛选 + 排序 pipeline ─────────────────────────────
  const filteredRows = useMemo(() => {
    if (!screener.data?.rows) return [];
    let rows = screener.data.rows.filter(
      (r) => r.threat_score >= scoreMin && r.threat_score <= scoreMax,
    );
    if (moduleToggles.size > 0) {
      rows = rows.filter((r) =>
        [...moduleToggles].some((m) => r.modules_active.some((ma) => ma.startsWith(m))),
      );
    }
    if (lifecycleSel.size > 0) {
      rows = rows.filter((r) => lifecycleSel.has(r.signal_lifecycle as Lifecycle));
    }
    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "threat_score": cmp = a.threat_score - b.threat_score; break;
        case "rank": cmp = a.rank - b.rank; break;
        case "symbol": cmp = a.symbol.localeCompare(b.symbol); break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [screener.data, scoreMin, scoreMax, moduleToggles, lifecycleSel, sortCol, sortDir]);

  // 分页切片
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const pageRows = useMemo(
    () => filteredRows.slice(safePage * pageSize, (safePage + 1) * pageSize),
    [filteredRows, safePage, pageSize],
  );

  // ── 回调 ─────────────────────────────────────────────
  const toggleSort = useCallback((col: SortColumn) => {
    setSortCol((prev) => {
      if (prev === col) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      setSortDir("desc");
      return col;
    });
  }, []);

  const toggleModule = (mod: ModuleKey) => {
    setModuleToggles((prev) => {
      const next = new Set(prev);
      if (next.has(mod)) next.delete(mod);
      else next.add(mod);
      return next;
    });
    setPage(0);
  };

  const toggleLifecycle = (lc: Lifecycle) => {
    setLifecycleSel((prev) => {
      const next = new Set(prev);
      if (next.has(lc)) next.delete(lc);
      else next.add(lc);
      return next;
    });
    setPage(0);
  };

  const toggleRow = (symbol: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  const allPageSelected = pageRows.length > 0 && pageRows.every((r) => selected.has(r.symbol));
  const toggleAllPage = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) pageRows.forEach((r) => next.delete(r.symbol));
      else pageRows.forEach((r) => next.add(r.symbol));
      return next;
    });
  };

  const hasActiveFilters = scoreMin > 0 || scoreMax < 100 || moduleToggles.size > 0 || lifecycleSel.size > 0;
  const resetFilters = () => {
    setScoreMin(0);
    setScoreMax(100);
    setModuleToggles(new Set());
    setLifecycleSel(new Set());
    setPage(0);
  };

  const SortIcon = ({ col }: { col: SortColumn }) => (
    <span className="text-[10px] ml-0.5 opacity-50" aria-hidden="true">
      {sortCol === col ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
    </span>
  );

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-full min-h-0">
      {/* ═══ Filter Panel (P2-01, collapsible) ═══ */}
      <aside
        className={`shrink-0 transition-all ${filterOpen ? "w-full lg:w-64" : "w-full lg:w-10"}`}
        aria-label={t("screener.filterPanel")}
      >
        <button
          onClick={() => setFilterOpen(!filterOpen)}
          aria-expanded={filterOpen}
          className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 mb-2 focus:outline-none focus:ring-1 focus:ring-slate-400 rounded px-1 py-0.5"
        >
          <span aria-hidden="true">{filterOpen ? "◂" : "▸"}</span>
          {t("screener.filters")}
          {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-blue-400" aria-hidden="true" />}
        </button>

        {filterOpen && (
          <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-4 space-y-5">
            {/* Threat Score range */}
            <fieldset>
              <legend className="text-[11px] font-semibold text-slate-300 mb-2">
                Threat Score: <span className="font-mono">{scoreMin}–{scoreMax}</span>
              </legend>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-[10px] text-slate-500">
                  Min
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={scoreMin}
                    onChange={(e) => { setScoreMin(Number(e.target.value)); setPage(0); }}
                    className="flex-1 accent-red-500"
                    aria-label={t("screener.scoreMin")}
                  />
                </label>
                <label className="flex items-center gap-2 text-[10px] text-slate-500">
                  Max
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={scoreMax}
                    onChange={(e) => { setScoreMax(Number(e.target.value)); setPage(0); }}
                    className="flex-1 accent-red-500"
                    aria-label={t("screener.scoreMax")}
                  />
                </label>
              </div>
            </fieldset>

            {/* Module toggles */}
            <fieldset>
              <legend className="text-[11px] font-semibold text-slate-300 mb-2">
                {t("screener.moduleToggles")}
              </legend>
              <div className="grid grid-cols-2 gap-1.5">
                {MODULE_KEYS.map((mod) => {
                  const active = moduleToggles.has(mod);
                  return (
                    <button
                      key={mod}
                      onClick={() => toggleModule(mod)}
                      aria-pressed={active}
                      className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-[10px] border transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 ${
                        active
                          ? "border-slate-500 bg-slate-700/70 text-slate-100"
                          : "border-slate-700/50 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MODULE_COLORS[mod] }} aria-hidden="true" />
                      {t(`modules.${mod}`)}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {/* Lifecycle multi-select */}
            <fieldset>
              <legend className="text-[11px] font-semibold text-slate-300 mb-2">
                {t("screener.lifecycleStages")}
              </legend>
              <div className="flex flex-wrap gap-1">
                {LIFECYCLE_OPTIONS.map((lc) => {
                  const active = lifecycleSel.has(lc);
                  return (
                    <button
                      key={lc}
                      onClick={() => toggleLifecycle(lc)}
                      aria-pressed={active}
                      className={`px-2 py-0.5 rounded-full text-[10px] border transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 ${
                        active ? LIFECYCLE_BADGE[lc] : "border-slate-700/50 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      {t(`lifecycle.${lc}`)}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="w-full text-[11px] text-slate-400 hover:text-slate-200 border border-slate-700/50 rounded py-1.5 transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                {t("screener.resetFilters")}
              </button>
            )}
          </div>
        )}
      </aside>

      {/* ═══ Results ═══ */}
      <main className="flex-1 min-w-0 flex flex-col gap-3">
        <header className="flex items-baseline justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold">{t("routes.screener")}</h1>
            <p className="text-slate-400 text-sm mt-0.5">{t("screener.subtitle")}</p>
          </div>
          {screener.data && (
            <span className="text-xs text-slate-500 font-mono">
              {t("screener.tradeDate")} {screener.data.trade_date} · {t("screener.scanned")} {screener.data.total_scanned}
            </span>
          )}
        </header>

        {/* Quota exceeded → upgrade CTA (PRD §3.3) */}
        {quotaExceeded && (
          <div className="rounded-lg border border-amber-700/50 bg-amber-900/20 px-4 py-3 flex items-center gap-3">
            <span className="text-amber-300 text-sm">{t("quota.exhausted")}</span>
            <Link
              to="/subscribe"
              className="ml-auto px-3 py-1.5 rounded bg-amber-600 text-white text-xs font-medium hover:bg-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-400"
            >
              {t("marketing.upgradeCta")}
            </Link>
          </div>
        )}

        {/* Loading / Error */}
        {screener.isLoading && <SkeletonTable rows={12} cols={6} />}
        {screener.isError && !quotaExceeded && (
          <div className="text-slate-500 text-sm py-8 text-center">{t("screener.noData")}</div>
        )}

        {/* Results table */}
        {screener.data && (
          <>
            {/* Bulk action bar (P2-02) */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-500">
                {t("screener.showing", { shown: pageRows.length, total: filteredRows.length })}
              </span>
              <div className="ml-auto flex items-center gap-2">
                {selected.size > 0 && (
                  <>
                    <span className="text-[11px] text-slate-400">
                      {t("screener.selected", { count: selected.size })}
                    </span>
                    <select
                      value={basketTarget ?? ""}
                      onChange={(e) => setBasketTarget(e.target.value ? Number(e.target.value) : null)}
                      aria-label={t("screener.targetBasket")}
                      className="text-[11px] bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 focus:outline-none focus:ring-1 focus:ring-slate-400"
                    >
                      <option value="">{t("screener.targetBasket")}</option>
                      {(baskets.data ?? []).map((b) => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => {
                        if (!basketTarget) { toast.warning(t("screener.targetBasket")); return; }
                        bulkAdd.mutate({ basketId: basketTarget, tickers: [...selected] });
                      }}
                      disabled={bulkAdd.isPending}
                      className="px-3 py-1 rounded bg-slate-700 text-[11px] text-slate-100 hover:bg-slate-600 disabled:opacity-50 focus:outline-none focus:ring-1 focus:ring-slate-400"
                    >
                      {t("screener.bulkAddBasket")}
                    </button>
                  </>
                )}
                <button
                  onClick={() => exportCsv(filteredRows)}
                  className="px-3 py-1 rounded border border-slate-700 text-[11px] text-slate-300 hover:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
                >
                  {t("screener.exportCsv")}
                </button>
              </div>
            </div>

            {filteredRows.length === 0 ? (
              <div className="text-slate-500 text-sm py-12 text-center">
                {t("screener.noMatches")}
              </div>
            ) : (
              <div className="border border-slate-800 rounded-md overflow-x-auto">
                <table className="w-full text-sm" role="grid">
                  <thead>
                    <tr className="bg-slate-900 border-b border-slate-800 text-xs text-slate-400">
                      <th className="w-8 px-2 py-2">
                        <input
                          type="checkbox"
                          checked={allPageSelected}
                          onChange={toggleAllPage}
                          aria-label={t("screener.selectAll")}
                          className="accent-red-500"
                        />
                      </th>
                      <th className="w-10 px-2 py-2 text-left cursor-pointer select-none" onClick={() => toggleSort("rank")}>
                        # <SortIcon col="rank" />
                      </th>
                      <th className="px-2 py-2 text-left cursor-pointer select-none" onClick={() => toggleSort("symbol")}>
                        {t("screener.symbol")} <SortIcon col="symbol" />
                      </th>
                      <th className="px-2 py-2 text-left hidden md:table-cell">{t("screener.name")}</th>
                      <th className="w-16 px-2 py-2 text-left cursor-pointer select-none" onClick={() => toggleSort("threat_score")}>
                        {t("screener.score")} <SortIcon col="threat_score" />
                      </th>
                      <th className="w-16 px-2 py-2 text-left">{t("screener.signal")}</th>
                      <th className="px-2 py-2 text-left hidden sm:table-cell">{t("screener.modules")}</th>
                      <th className="w-20 px-2 py-2 text-left hidden lg:table-cell">7d</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40">
                    {pageRows.map((r) => (
                      <tr
                        key={r.symbol}
                        className="hover:bg-slate-800/30 cursor-pointer transition-colors"
                        onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } })}
                      >
                        <td className="px-2 py-2" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selected.has(r.symbol)}
                            onChange={() => toggleRow(r.symbol)}
                            aria-label={`${t("screener.select")} ${r.symbol}`}
                            className="accent-red-500"
                          />
                        </td>
                        <td className="px-2 py-2 text-xs text-slate-500 font-mono">{r.rank}</td>
                        <td className="px-2 py-2 font-mono font-bold text-slate-100">
                          {r.symbol}
                          {r.symbol_type === "etf" && (
                            <span className="ml-1 text-[9px] text-slate-600 bg-slate-800 px-1 rounded">ETF</span>
                          )}
                        </td>
                        <td className="px-2 py-2 text-xs text-slate-400 truncate max-w-[140px] hidden md:table-cell">
                          {r.name || "—"}
                        </td>
                        <td className="px-2 py-2">
                          <span className="font-mono text-base font-bold" style={{ color: threatScoreColor(r.threat_score) }}>
                            {r.threat_score.toFixed(0)}
                          </span>
                        </td>
                        <td className="px-2 py-2">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border ${LIFECYCLE_BADGE[r.signal_lifecycle] ?? LIFECYCLE_BADGE.init}`}>
                            {t(`lifecycle.${r.signal_lifecycle}`)}
                          </span>
                        </td>
                        <td className="px-2 py-2 hidden sm:table-cell">
                          <div className="flex gap-1">
                            {r.modules_active.slice(0, 3).map((m) => {
                              const modKey = MODULE_KEYS.find((k) => m.startsWith(k));
                              return (
                                <span
                                  key={m}
                                  className="w-2 h-2 rounded-full"
                                  title={m}
                                  style={{ backgroundColor: modKey ? MODULE_COLORS[modKey] : "#64748b" }}
                                  aria-label={m}
                                />
                              );
                            })}
                          </div>
                        </td>
                        <td className="px-2 py-2 hidden lg:table-cell">
                          <Sparkline ticker={r.symbol} width={56} height={16} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination (P2-02: 25/50/100) */}
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-1" role="group" aria-label={t("screener.pageSize")}>
                {([25, 50, 100] as PageSize[]).map((size) => (
                  <button
                    key={size}
                    onClick={() => { setPageSize(size); setPage(0); }}
                    aria-pressed={pageSize === size}
                    className={`px-2 py-1 rounded text-[11px] font-mono transition-colors focus:outline-none focus:ring-1 focus:ring-slate-400 ${
                      pageSize === size ? "bg-slate-600 text-white font-bold" : "text-slate-400 hover:text-slate-200 border border-slate-700/50"
                    }`}
                  >
                    {size}
                  </button>
                ))}
              </div>
              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={() => setPage(Math.max(0, safePage - 1))}
                  disabled={safePage === 0}
                  className="px-2.5 py-1 rounded text-[11px] border border-slate-700/50 text-slate-300 disabled:opacity-30 hover:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
                  aria-label={t("screener.prevPage")}
                >
                  ←
                </button>
                <span className="text-[11px] text-slate-400 font-mono">
                  {safePage + 1} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))}
                  disabled={safePage >= totalPages - 1}
                  className="px-2.5 py-1 rounded text-[11px] border border-slate-700/50 text-slate-300 disabled:opacity-30 hover:bg-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
                  aria-label={t("screener.nextPage")}
                >
                  →
                </button>
              </div>
            </div>

            <div className="text-[10px] text-slate-600">{t("screener.disclaimer")}</div>
          </>
        )}
      </main>
    </div>
  );
}
