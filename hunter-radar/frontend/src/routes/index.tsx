import { createRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/",
  component: HomePage,
});

function HomePage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const nav = useNavigate();

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
        <h2 className="text-xl font-semibold mb-4">今日 Top 10 危险标的(预览)</h2>
        {screener.isError ? (
          <div className="text-slate-500 text-sm">
            Screener 数据尚未就绪(预计 M2 末对接)。当前为占位卡片。
          </div>
        ) : screener.data && screener.data.rows.length > 0 ? (
          <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {screener.data.rows.map((r) => (
              <li
                key={r.symbol}
                className="bg-slate-900 border border-slate-800 rounded-md p-3 hover:border-slate-600 cursor-pointer"
                onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } })}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold">{r.symbol}</span>
                  <span className="text-2xl font-mono">{r.threat_score.toFixed(0)}</span>
                </div>
                <div className="text-xs text-slate-500 mt-1">{r.name}</div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500 text-sm">
            Screener 尚未产出数据(预计 M2 末对接 BD-072)。当前为占位。
          </div>
        )}
      </section>
    </div>
  );
}
