/**
 * FE-102: 全局搜索框 Autocomplete 下拉
 *
 * PRD §2.1: 防抖 + 模糊匹配 + 搜索历史
 * - 300ms debounce(由 useLookup 处理)
 * - 搜索历史 localStorage 持久化,最多 10 条,支持清空
 * - 输入 `QQ` 显示 `QQQ (Invesco QQQ Trust) [ETF]`
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useLookup } from "@/features/useLookup";

const HISTORY_KEY = "hunter-search-history";
const MAX_HISTORY = 10;

function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeHistory(items: string[]): void {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, MAX_HISTORY)));
}

function addToHistory(ticker: string): void {
  const prev = readHistory().filter((t) => t !== ticker);
  writeHistory([ticker, ...prev]);
}

export function clearSearchHistory(): void {
  localStorage.removeItem(HISTORY_KEY);
}

export function SearchBox() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const lookup = useLookup();
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<string[]>(readHistory());
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const navigateTo = useCallback(
    (ticker: string) => {
      addToHistory(ticker);
      setHistory(readHistory());
      lookup.setQuery("");
      setOpen(false);
      nav({ to: "/symbol/$ticker", params: { ticker } });
    },
    [nav, lookup],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = lookup.query.trim().toUpperCase();
    if (!q) return;
    // 简单 ticker 格式匹配 → 直接跳转
    if (/^[A-Z]{1,6}$/.test(q)) {
      navigateTo(q);
      return;
    }
    // 如果有结果,跳转第一条
    if (lookup.results.length > 0) {
      navigateTo(lookup.results[0].ticker);
    }
  };

  const showDropdown = open && (lookup.hasResults || lookup.isLoading || history.length > 0);

  return (
    <div ref={containerRef} className="relative w-full max-w-xs lg:max-w-sm">
      <form onSubmit={onSubmit} className="flex items-center">
        <input
          ref={inputRef}
          value={lookup.query}
          onChange={(e) => {
            lookup.setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={t("search.placeholder") || "搜索标的代码或名称…"}
          className={[
            "w-full bg-slate-900 border border-slate-700 rounded-md",
            "px-3 py-1.5 text-sm focus:outline-none focus:border-sky-500",
            "placeholder-slate-500 font-mono",
          ].join(" ")}
          maxLength={20}
          aria-label={t("search.ariaLabel") || "全局标的搜索"}
          autoComplete="off"
        />
        {lookup.isLoading && (
          <span className="absolute right-3 text-xs text-slate-500">…</span>
        )}
      </form>

      {/* ── 下拉面板 ──────────────────────────────────── */}
      {showDropdown && (
        <div
          className={[
            "absolute top-full left-0 right-0 mt-1 z-50",
            "bg-slate-900 border border-slate-700 rounded-md shadow-xl",
            "max-h-64 overflow-y-auto",
          ].join(" ")}
          role="listbox"
        >
          {/* 搜索结果 */}
          {lookup.hasResults ? (
            lookup.results.map((r) => (
              <button
                key={r.ticker}
                onClick={() => navigateTo(r.ticker)}
                className={[
                  "w-full text-left px-3 py-2 hover:bg-slate-800",
                  "flex items-center gap-2 text-sm border-b border-slate-800/50 last:border-0",
                ].join(" ")}
                role="option"
              >
                <span className="font-mono font-bold text-slate-100">{r.ticker}</span>
                <span className="text-slate-500 truncate flex-1">{r.name}</span>
                <span
                  className={[
                    "text-xs px-1.5 py-0.5 rounded border shrink-0",
                    r.type === "ETF"
                      ? "text-sky-400 bg-sky-950/30 border-sky-800/50"
                      : "text-slate-400 bg-slate-800 border-slate-700",
                  ].join(" ")}
                >
                  {r.type}
                </span>
              </button>
            ))
          ) : lookup.query.trim().length === 0 && history.length > 0 ? (
            <>
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-800">
                <span className="text-xs text-slate-500">
                  {t("search.recent") || "最近搜索"}
                </span>
                <button
                  onClick={() => {
                    clearSearchHistory();
                    setHistory([]);
                  }}
                  className="text-xs text-slate-600 hover:text-slate-400"
                >
                  {t("search.clearHistory") || "清空"}
                </button>
              </div>
              {history.map((ticker) => (
                <button
                  key={ticker}
                  onClick={() => navigateTo(ticker)}
                  className="w-full text-left px-3 py-2 hover:bg-slate-800 text-sm font-mono text-slate-300"
                  role="option"
                >
                  {ticker}
                </button>
              ))}
            </>
          ) : lookup.query.trim().length > 0 && !lookup.isLoading ? (
            <div className="px-3 py-3 text-xs text-slate-500 text-center">
              {t("search.noResults") || "无匹配结果"}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
