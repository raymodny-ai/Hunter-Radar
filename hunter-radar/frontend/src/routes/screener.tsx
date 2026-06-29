import { createRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useMemo, useState, useCallback, useRef, useEffect, type CSSProperties, type ReactElement } from "react";
import { List } from "react-window";
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

// FE-128: 排序列定义
type SortColumn = "threat_score" | "rank" | "symbol";
type SortDir = "asc" | "desc";

type ScreenerRow = {
  rank: number;
  symbol: string;
  name: string;
  symbol_type: string;
  threat_score: number;
  signal_lifecycle: string;
  modules_active: string[];
  nl_summary: string | null;
};

// FE-127: Row component for react-window v2
type ScreenerRowProps = {
  rows: ScreenerRow[];
  nav: ReturnType<typeof useNavigate>;
};

function ScreenerRowComponent({
  ariaAttributes,
  index,
  style,
  rows,
  nav,
}: {
  ariaAttributes: { "aria-posinset": number; "aria-setsize": number; role: "listitem" };
  index: number;
  style: CSSProperties;
  rows: ScreenerRow[];
  nav: ReturnType<typeof useNavigate>;
}): ReactElement | null {
  const r = rows[index];
  if (!r) return null;
  const lcColor = LIFECYCLE_COLORS[r.signal_lifecycle] || LIFECYCLE_COLORS.init;
  const lcLabel = LIFECYCLE_LABELS[r.signal_lifecycle] || r.signal_lifecycle;
  const modules = r.modules_active?.join(" / ") || "";
  const isEtf = r.symbol_type === "etf";

  return (
    <div
      {...ariaAttributes}
      style={style}
      className="flex items-center border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer px-2 text-sm"
      onClick={() => nav({ to: "/symbol/$ticker", params: { ticker: r.symbol } })}
    >
      <div className="w-10 text-slate-500 text-xs flex-shrink-0">{r.rank}</div>
      <div className="w-20 font-mono font-bold flex-shrink-0">
        {r.symbol}
        {isEtf && (
          <span className="ml-1 text-[9px] text-slate-600 bg-slate-800 px-1 rounded">ETF</span>
        )}
      </div>
      <div className="w-32 text-slate-400 text-xs truncate hidden md:block flex-shrink-0">
        {r.name || "—"}
      </div>
      <div className="w-16 flex-shrink-0">
        <span
          className={`font-mono text-lg font-bold ${
            r.threat_score >= 70
              ? "text-red-400"
              : r.threat_score >= 50
                ? "text-amber-300"
                : r.threat_score >= 30
                  ? "text-slate-300"
                  : "text-emerald-400"
          }`}
        >
          {r.threat_score.toFixed(0)}
        </span>
      </div>
      <div className="w-16 flex-shrink-0">
        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${lcColor}`}>
          {lcLabel}
        </span>
      </div>
      <div className="flex-1 text-xs text-slate-500 truncate hidden sm:block">
        {modules}
      </div>
      <div className="w-16 hidden lg:flex items-center justify-center flex-shrink-0">
        {r.modules_active?.includes("options_high") ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded border text-red-400 bg-red-950/30 border-red-800/50">
            HIGH
          </span>
        ) : (
          <span className="text-xs text-slate-600">—</span>
        )}
      </div>
      {/* FE-128: ETF 标的自动隐藏内部人列 */}
      {!isEtf && (
        <div className="w-12 text-center flex-shrink-0 hidden lg:block">
          <span className="text-slate-600 text-xs">—</span>
        </div>
      )}
      <div className="w-8 text-center flex-shrink-0">
        <span className="text-slate-600 text-xs hover:text-slate-400">→</span>
      </div>
    </div>
  );
}

function ScreenerPage() {
  const { t } = useTranslation();
  const nav = useNavigate();

  // FE-129: 对接 top100
  const top = 100;

  const screener = useQuery({
    queryKey: ["screener", top],
    queryFn: () => api.getScreener(top),
    retry: 0,
    staleTime: 1000 * 60 * 60,
  });

  // FE-128: 排序状态
  const [sortCol, setSortCol] = useState<SortColumn>("threat_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // 排序后的数据
  const sortedRows = useMemo(() => {
    if (!screener.data?.rows) return [];
    const rows = [...screener.data.rows];
    rows.sort((a, b) => {
      let cmp = 0;
      switch (sortCol) {
        case "threat_score":
          cmp = a.threat_score - b.threat_score;
          break;
        case "rank":
          cmp = a.rank - b.rank;
          break;
        case "symbol":
          cmp = a.symbol.localeCompare(b.symbol);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [screener.data, sortCol, sortDir]);

  const toggleSort = useCallback(
    (col: SortColumn) => {
      if (sortCol === col) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      else {
        setSortCol(col);
        setSortDir("desc");
      }
    },
    [sortCol],
  );

  // FE-127: 容器高度自适应
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerHeight, setContainerHeight] = useState(500);

  useEffect(() => {
    const updateHeight = () => {
      if (containerRef.current) {
        const h = window.innerHeight - containerRef.current.getBoundingClientRect().top - 80;
        setContainerHeight(Math.max(300, h));
      }
    };
    updateHeight();
    window.addEventListener("resize", updateHeight);
    return () => window.removeEventListener("resize", updateHeight);
  }, []);

  const ROW_HEIGHT = 44;

  const SortIcon = ({ col }: { col: SortColumn }) => (
    <span className="text-[10px] ml-0.5 opacity-50">
      {sortCol === col ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
    </span>
  );

  return (
    <div className="space-y-3" ref={containerRef}>
      <header>
        <h1 className="text-2xl font-bold">{t("routes.screener")}</h1>
        <p className="text-slate-400 text-sm mt-1">
          {t("screener.subtitle")}
        </p>
      </header>

      {screener.isLoading && (
        <div className="text-slate-500 text-sm py-8 text-center">{t("common.loading")}</div>
      )}

      {screener.isError && (
        <div className="text-slate-500 text-sm py-8 text-center">
          {t("screener.noData")}
        </div>
      )}

      {screener.data && (
        <>
          <div className="text-xs text-slate-500">
            {t("screener.tradeDate")} {screener.data.trade_date} · {t("screener.scanned")} {screener.data.total_scanned}
          </div>

          {sortedRows.length === 0 ? (
            <div className="text-slate-500 text-sm py-8 text-center">
              {t("screener.emptyData")}
            </div>
          ) : (
            <div className="border border-slate-800 rounded-md overflow-hidden" style={{ height: containerHeight + 40 }}>
              {/* 表头 */}
              <div className="flex items-center bg-slate-900 border-b border-slate-800 text-xs text-slate-400 px-2 py-2">
                <div
                  className="w-10 cursor-pointer select-none flex-shrink-0"
                  onClick={() => toggleSort("rank")}
                >
                  # <SortIcon col="rank" />
                </div>
                <div
                  className="w-20 cursor-pointer select-none flex-shrink-0"
                  onClick={() => toggleSort("symbol")}
                >
                  {t("screener.symbol")} <SortIcon col="symbol" />
                </div>
                <div className="w-32 hidden md:block flex-shrink-0">{t("screener.name")}</div>
                <div
                  className="w-16 cursor-pointer select-none flex-shrink-0"
                  onClick={() => toggleSort("threat_score")}
                >
                  {t("screener.score")} <SortIcon col="threat_score" />
                </div>
                <div className="w-16 flex-shrink-0">{t("screener.signal")}</div>
                <div className="flex-1 hidden sm:block flex-shrink-0">{t("screener.modules")}</div>
                <div className="w-16 hidden lg:flex items-center justify-center flex-shrink-0">Options</div>
                <div className="w-12 hidden lg:block text-center flex-shrink-0">{t("screener.insider")}</div>
                <div className="w-8 flex-shrink-0"></div>
              </div>

              {/* FE-127: 虚拟列表(react-window v2) */}
              <List<ScreenerRowProps>
                rowComponent={ScreenerRowComponent}
                rowCount={sortedRows.length}
                rowHeight={ROW_HEIGHT}
                overscanCount={5}
                rowProps={{ rows: sortedRows, nav }}
              />
            </div>
          )}

          <div className="text-[10px] text-slate-600 pt-1">
            {t("screener.disclaimer")}
          </div>
        </>
      )}
    </div>
  );
}
