import { createRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { Route as RootRoute } from "./__root";

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/screener",
  component: ScreenerPage,
});

const LIFECYCLE_COLORS: Record<string, string> = {
  red: "text-red-400 bg-red-950/30 border-red-800/50",
  yellow: "text-amber-300 bg-amber-950/30 border-amber-800/50",
  gray: "text-slate-400 bg-slate-900 border-slate-700",
  green: "text-emerald-400 bg-emerald-950/30 border-emerald-800/50",
  init: "text-slate-500 bg-slate-900 border-slate-700",
};

const LIFECYCLE_LABELS: Record<string, string> = {
  red: "红灯",
  yellow: "黄灯",
  gray: "灰灯",
  green: "绿灯",
  init: "初始化",
};

function ScreenerPage() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const top = 50;

  const screener = useQuery({
    queryKey: ["screener", top],
    queryFn: () => api.getScreener(top),
    retry: 0,
    staleTime: 1000 * 60 * 5,
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">{t("routes.screener") || "每日猎物榜单"}</h1>
        <p className="text-slate-400 text-sm mt-1">
          基于期权异常 / 做空水位 / 量价背离 / 内部交易四维共振评分排序
        </p>
      </header>

      {screener.isLoading && (
        <div className="text-slate-500 text-sm py-8 text-center">加载中…</div>
      )}

      {screener.isError && (
        <div className="text-slate-500 text-sm py-8 text-center">
          Screener 数据尚未就绪
        </div>
      )}

      {screener.data && (
        <>
          <div className="text-xs text-slate-500">
            交易日 {screener.data.trade_date} · 今日扫描 {screener.data.total_scanned} 只标的
          </div>

          {screener.data.rows.length === 0 ? (
            <div className="text-slate-500 text-sm py-8 text-center">
              暂无数据，可能需要先查询一些股票触发数据采集
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 text-left border-b border-slate-800">
                    <th className="py-2 px-2 w-10">#</th>
                    <th className="py-2 px-2">代码</th>
                    <th className="py-2 px-2 hidden md:table-cell">名称</th>
                    <th className="py-2 px-2">评分</th>
                    <th className="py-2 px-2">信号</th>
                    <th className="py-2 px-2 hidden sm:table-cell">活跃模块</th>
                    <th className="py-2 px-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {screener.data.rows.map((r) => {
                    const lcColor = LIFECYCLE_COLORS[r.signal_lifecycle] || LIFECYCLE_COLORS.init;
                    const lcLabel = LIFECYCLE_LABELS[r.signal_lifecycle] || r.signal_lifecycle;
                    const modules = r.modules_active?.join(" / ") || "";

                    return (
                      <tr
                        key={r.symbol}
                        className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer"
                        onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } })}
                      >
                        <td className="py-2.5 px-2 text-slate-500 text-xs">{r.rank}</td>
                        <td className="py-2.5 px-2 font-mono font-bold">{r.symbol}</td>
                        <td className="py-2.5 px-2 text-slate-400 text-xs hidden md:table-cell truncate max-w-[200px]">
                          {r.name || "—"}
                        </td>
                        <td className="py-2.5 px-2">
                          <span className={`font-mono text-lg font-bold ${
                            r.threat_score >= 70 ? "text-red-400" :
                            r.threat_score >= 50 ? "text-amber-300" :
                            r.threat_score >= 30 ? "text-slate-300" :
                            "text-emerald-400"
                          }`}>
                            {r.threat_score.toFixed(0)}
                          </span>
                        </td>
                        <td className="py-2.5 px-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded border ${lcColor}`}>
                            {lcLabel}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-xs text-slate-500 hidden sm:table-cell">
                          {modules}
                        </td>
                        <td className="py-2.5 px-2">
                          <span className="text-slate-600 text-xs hover:text-slate-400"
                            onClick={(e) => {
                              e.stopPropagation();
                              nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } });
                            }}
                          >
                            →
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="text-xs text-slate-600 pt-2">
            评分基于 FINRA / SEC EDGAR / Yahoo Finance 公开数据的统计异常，仅供参考。
          </div>
        </>
      )}
    </div>
  );
}
