import { createRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/",
  component: HomePage,
});

// ─── Local blacklist (per-browser, no backend) ───────────────────
// "屏蔽" 的标的存 localStorage,刷新后仍生效
const BLACKLIST_KEY = "hunter:home:top10:blacklist";

function loadBlacklist(): Set<string> {
  try {
    const raw = localStorage.getItem(BLACKLIST_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function saveBlacklist(set: Set<string>) {
  try {
    localStorage.setItem(BLACKLIST_KEY, JSON.stringify([...set]));
  } catch {
    /* quota / private mode — ignore */
  }
}

function HomePage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const qc = useQueryClient();

  // Blacklist state — 触发重渲染 + 同步到 localStorage
  const [blacklist, setBlacklist] = useState<Set<string>>(() => loadBlacklist());
  useEffect(() => { saveBlacklist(blacklist); }, [blacklist]);

  const removeFromBlacklist = (symbol: string) => {
    setBlacklist((prev) => {
      const next = new Set(prev);
      next.delete(symbol);
      return next;
    });
  };

  const screener = useQuery({
    queryKey: ["screener", "preview"],
    queryFn: () => api.getScreener(10),
    retry: 0,
  });

  const onSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = q.trim().toUpperCase();
    if (!trimmed) return;
    // 简化:直接路由,无 lookup
    if (trimmed.length <= 6 && /^[A-Z\^\d]+$/.test(trimmed)) {
      nav({ to: "/symbol/$ticker", params: { ticker: trimmed } });
    }
  };

  // Filter out blacklisted symbols
  const filteredRows = screener.data?.rows.filter((r) => !blacklist.has(r.symbol)) ?? [];

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">{t("app.tagline")}</h1>
        <p className="text-slate-400 mt-2 text-sm">
          输入美股代码或 ETF 代码,系统会基于期权异常分布 / 全监管做空 / 量价背离 / SEC 内部行为四个维度做共振分析。
        </p>
        <form onSubmit={onSearch} className="mt-6 flex gap-2 max-w-lg">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="例如:AAPL / QQQ / TSLA"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-4 py-2 focus:outline-none focus:border-slate-400"
            maxLength={10}
          />
          <button
            type="submit"
            className="px-6 py-2 bg-slate-100 text-slate-900 rounded-md font-medium hover:bg-white"
          >
            分析
          </button>
        </form>
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{t("home.top10Title")}</h2>
          {blacklist.size > 0 && (
            <span className="text-xs text-slate-500">
              {t("home.blacklistCount", { count: blacklist.size })}
            </span>
          )}
        </div>
        {screener.isError ? (
          <div className="text-slate-500 text-sm">
            {t("home.screenerNotReady")}
          </div>
        ) : filteredRows.length > 0 ? (
          <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredRows.map((r) => (
              <li
                key={r.symbol}
                className="relative bg-slate-900 border border-slate-800 rounded-md p-3 hover:border-slate-600 cursor-pointer group"
              >
                {/* Remove button (always visible) */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(t("home.confirmBlacklist", { symbol: r.symbol }))) {
                      setBlacklist((prev) => new Set(prev).add(r.symbol));
                      // Trigger re-render of any consumer keyed on screener
                      qc.invalidateQueries({ queryKey: ["screener", "preview"] });
                    }
                  }}
                  className="absolute top-1.5 right-1.5 w-5 h-5 flex items-center justify-center rounded text-xs text-slate-500 hover:text-red-400 hover:bg-slate-800 transition-colors"
                  aria-label={t("home.blacklistSymbol", { symbol: r.symbol })}
                  title={t("home.blacklistSymbol", { symbol: r.symbol })}
                >
                  ×
                </button>
                <div onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } })}>
                  <div className="flex items-center justify-between pr-6">
                    <span className="font-mono font-bold">{r.symbol}</span>
                    <span className="text-2xl font-mono">{r.threat_score.toFixed(0)}</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">{r.name}</div>
                </div>
              </li>
            ))}
          </ul>
        ) : screener.data && screener.data.rows.length > 0 && blacklist.size > 0 ? (
          // All rows blacklisted — show recover hint
          <div className="text-slate-500 text-sm space-y-2">
            <div>{t("home.allBlacklisted")}</div>
            {blacklist.size > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {[...blacklist].map((sym) => (
                  <button
                    key={sym}
                    onClick={() => removeFromBlacklist(sym)}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-800 text-xs text-slate-300 hover:text-slate-100 hover:bg-slate-700"
                    title={t("home.unblacklistSymbol")}
                  >
                    {sym}
                    <span className="text-slate-500">↺</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-slate-500 text-sm">
            {t("home.screenerNoData")}
          </div>
        )}
      </section>
    </div>
  );
}