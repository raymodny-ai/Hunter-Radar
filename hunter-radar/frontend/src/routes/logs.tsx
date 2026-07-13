/**
 * FE-160: 后台日志查看页面
 *
 * - 从 server.log 文件读取(进程重启后历史不丢)
 * - 实时 SSE 推送(structlog 日志流)
 * - 关键字 / 级别 / 来源过滤
 * - 暂停 / 继续 / 清空 / 下载
 *
 * 路由: /logs
 * 后端:
 *   GET  /api/v1/logs/file?tail=N&level=...&q=...&source=...
 *   GET  /api/v1/logs/stream   (SSE)
 *   GET  /api/v1/logs/history  (SSE 内存缓冲,作为实时补丁)
 */
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createRoute } from "@tanstack/react-router";
import { Route as RootRoute } from "./__root";

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  extra?: Record<string, unknown>;
  source?: "app" | "uvicorn" | string;
  raw?: string;
}

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

const LEVEL_TEXT: Record<string, string> = {
  DEBUG: "text-slate-500",
  INFO: "text-sky-300",
  WARNING: "text-amber-300",
  ERROR: "text-red-300",
  CRITICAL: "text-red-400 font-bold",
};

const LEVEL_BG: Record<string, string> = {
  DEBUG: "bg-transparent",
  INFO: "bg-transparent",
  WARNING: "bg-amber-950/20",
  ERROR: "bg-red-950/20",
  CRITICAL: "bg-red-950/40",
};

const SOURCE_BADGE: Record<string, string> = {
  app: "bg-sky-900/40 text-sky-300 border-sky-800",
  uvicorn: "bg-slate-800 text-slate-400 border-slate-700",
};

export const Route = createRoute({
  getParentRoute: () => RootRoute,
  path: "/logs",
  component: LogsPage,
});

function LogsPage() {
  // ---- 持久化历史(从 server.log 读) ----
  const [history, setHistory] = useState<LogEntry[]>([]);
  const [historyMeta, setHistoryMeta] = useState<{
    source: string;
    sizeBytes: number;
    loading: boolean;
    error: string | null;
  }>({ source: "", sizeBytes: 0, loading: true, error: null });

  // ---- 实时流(SSE)----
  const [live, setLive] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [connected, setConnected] = useState(false);
  const liveBufferRef = useRef<LogEntry[]>([]);

  // ---- 过滤 ----
  const [enabledLevels, setEnabledLevels] = useState<Set<string>>(
    new Set(LEVELS),
  );
  const [keyword, setKeyword] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | "app" | "uvicorn">(
    "all",
  );
  const [autoScroll, setAutoScroll] = useState(true);
  const [tailSize, setTailSize] = useState(500);

  // ---- 视图:追加 / 替换 ----
  const [appendLive, setAppendLive] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);

  // ---- 加载历史 ----
  const reloadHistory = useCallback(async () => {
    setHistoryMeta((m) => ({ ...m, loading: true, error: null }));
    try {
      const r = await fetch(
        `/api/v1/logs/file?tail=${tailSize}&source=${sourceFilter}`,
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setHistory(data.entries ?? []);
      setHistoryMeta({
        source: data.source ?? "",
        sizeBytes: data.size_bytes ?? 0,
        loading: false,
        error: null,
      });
    } catch (e) {
      setHistoryMeta((m) => ({
        ...m,
        loading: false,
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  }, [tailSize, sourceFilter]);

  useEffect(() => {
    void reloadHistory();
  }, [reloadHistory]);

  // ---- SSE 实时流 ----
  useEffect(() => {
    if (paused) return;
    const es = new EventSource("/api/v1/logs/stream");
    sseRef.current = es;
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const entry: LogEntry = JSON.parse(e.data);
        entry.source = entry.source ?? "app";
        if (pausedRef.current) return; // pause 时丢弃,避免下次取消 pause 一口气灌进来
        liveBufferRef.current.push(entry);
        if (liveBufferRef.current.length > 2000) {
          liveBufferRef.current = liveBufferRef.current.slice(-1000);
        }
        setLive([...liveBufferRef.current]);
      } catch {
        /* heartbeat */
      }
    };
    return () => {
      es.close();
      sseRef.current = null;
      setConnected(false);
    };
  }, [paused]);

  // 用 ref 让 onmessage 里的 paused 判断拿到最新值
  const pausedRef = useRef(paused);
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // ---- 合并:历史 + 实时 ----
  const merged = useMemo(() => {
    if (appendLive && live.length > 0) {
      // 实时可能与历史尾部重叠,按 ts+raw 去重
      const seen = new Set<string>();
      const out: LogEntry[] = [];
      for (const e of live) {
        const k = `${e.ts}|${e.raw ?? e.msg}`;
        if (seen.has(k)) continue;
        seen.add(k);
        out.push(e);
      }
      // 历史里出现在实时 ts 之前的也带上
      const liveTs = live[0]?.ts ?? "";
      for (const e of history) {
        if (e.ts && liveTs && e.ts >= liveTs) continue;
        const k = `${e.ts}|${e.raw ?? e.msg}`;
        if (seen.has(k)) continue;
        seen.add(k);
        out.push(e);
      }
      out.sort((a, b) => (a.ts || "").localeCompare(b.ts || ""));
      return out;
    }
    return history;
  }, [history, live, appendLive]);

  // ---- 过滤 ----
  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return merged.filter((e) => {
      if (!enabledLevels.has(e.level)) return false;
      if (sourceFilter !== "all" && e.source !== sourceFilter) return false;
      if (kw) {
        const hay = `${e.msg} ${e.raw ?? ""} ${JSON.stringify(e.extra ?? {})}`;
        if (!hay.toLowerCase().includes(kw)) return false;
      }
      return true;
    });
  }, [merged, enabledLevels, keyword, sourceFilter]);

  // ---- 统计 ----
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of filtered) c[e.level] = (c[e.level] || 0) + 1;
    return c;
  }, [filtered]);

  const total = filtered.length;
  const shown = filtered.length;

  // ---- 自动滚动 ----
  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [filtered, autoScroll]);

  // ---- 操作 ----
  const toggleLevel = (lv: string) => {
    setEnabledLevels((prev) => {
      const next = new Set(prev);
      if (next.has(lv)) next.delete(lv);
      else next.add(lv);
      return next;
    });
  };

  const clearLive = () => {
    liveBufferRef.current = [];
    setLive([]);
  };

  const downloadLog = () => {
    const lines = filtered.map((e) => {
      const ts = e.ts || "-";
      const src = e.source || "?";
      const ex = e.extra ? " " + JSON.stringify(e.extra) : "";
      return `${ts} [${e.level}] [${src}] ${e.msg}${ex}`;
    });
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hunter-radar-logs-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const fileSizeText = historyMeta.sizeBytes
    ? formatBytes(historyMeta.sizeBytes)
    : "—";

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] bg-slate-950 text-slate-200">
      {/* ── 顶部条 ──────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-1.5 font-mono font-bold text-slate-300">
          <span>📋</span>
          <span>后台日志</span>
          <span className="text-slate-500 font-normal">
            ({shown}/{total} filtered · {fileSizeText})
          </span>
        </div>

        <div className="w-px h-4 bg-slate-700" />

        {/* 级别多选 */}
        <div className="flex gap-1">
          {LEVELS.map((lv) => {
            const on = enabledLevels.has(lv);
            const cnt = counts[lv] || 0;
            return (
              <button
                key={lv}
                onClick={() => toggleLevel(lv)}
                className={[
                  "px-1.5 py-0.5 rounded font-mono border text-[10px]",
                  on
                    ? "border-slate-600 " + LEVEL_TEXT[lv]
                    : "border-slate-800 text-slate-600 line-through",
                ].join(" ")}
                title={on ? `隐藏 ${lv}` : `显示 ${lv}`}
              >
                {lv[0]}:{cnt}
              </button>
            );
          })}
        </div>

        <div className="w-px h-4 bg-slate-700" />

        {/* 搜索框 */}
        <input
          type="search"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索 msg / raw / extra…"
          className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs font-mono text-slate-200 placeholder:text-slate-500 w-64"
        />

        {/* 来源过滤 */}
        <select
          value={sourceFilter}
          onChange={(e) =>
            setSourceFilter(e.target.value as "all" | "app" | "uvicorn")
          }
          className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-mono text-slate-200"
        >
          <option value="all">all sources</option>
          <option value="app">app only</option>
          <option value="uvicorn">uvicorn only</option>
        </select>

        {/* tail 大小 */}
        <select
          value={tailSize}
          onChange={(e) => setTailSize(Number(e.target.value))}
          className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-mono text-slate-200"
          title="从文件加载的最后 N 行"
        >
          <option value={100}>100</option>
          <option value={500}>500</option>
          <option value={1000}>1k</option>
          <option value={2000}>2k</option>
        </select>

        <div className="flex-1" />

        {/* 追加实时流开关 */}
        <label
          className="flex items-center gap-1 cursor-pointer select-none"
          title="将 SSE 实时流追加到历史尾部"
        >
          <input
            type="checkbox"
            checked={appendLive}
            onChange={() => setAppendLive((v) => !v)}
            className="accent-sky-500"
          />
          追加实时
        </label>

        {/* 暂停 */}
        <button
          onClick={() => setPaused((v) => !v)}
          className={[
            "px-1.5 py-0.5 rounded font-mono border text-[10px]",
            paused
              ? "bg-amber-900/40 border-amber-700 text-amber-200"
              : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700",
          ].join(" ")}
          title="暂停时不再消费 SSE"
        >
          {paused ? "▶ 继续" : "⏸ 暂停"}
        </button>

        {/* 自动滚动 */}
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={() => setAutoScroll((v) => !v)}
            className="accent-slate-400"
          />
          滚动
        </label>

        {/* 清空实时 */}
        <button
          onClick={clearLive}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="清空实时缓冲(不影响历史)"
        >
          🗑 清实时
        </button>

        {/* 重读文件 */}
        <button
          onClick={() => void reloadHistory()}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="从 server.log 重新读取"
        >
          ↻ 重读
        </button>

        {/* 下载 */}
        <button
          onClick={downloadLog}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="下载当前过滤结果"
        >
          ⤓ 下载
        </button>
      </div>

      {/* ── 主日志流 ──────────────────────────────────── */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed"
        style={{ fontFamily: "JetBrains Mono, Menlo, monospace" }}
      >
        {historyMeta.loading && (
          <div className="text-slate-500 text-center py-12">
            读取 server.log…
          </div>
        )}
        {historyMeta.error && (
          <div className="text-red-400 text-center py-12">
            ❌ 加载失败: {historyMeta.error}
          </div>
        )}
        {!historyMeta.loading && !historyMeta.error && shown === 0 && (
          <div className="text-slate-600 text-center py-12">
            无匹配日志(历史 {history.length} 条,实时 {live.length} 条)
          </div>
        )}
        {filtered.map((e, i) => {
          const time = e.ts?.slice(11, 23) || "    -    ";
          const date = e.ts?.slice(0, 10) || "";
          const color = LEVEL_TEXT[e.level] || "text-slate-300";
          const bg = LEVEL_BG[e.level] || "";
          const src = e.source || "app";
          const srcCls = SOURCE_BADGE[src] || SOURCE_BADGE.app;
          return (
            <div
              key={`${i}-${e.ts}-${(e.raw ?? e.msg).slice(0, 32)}`}
              className={`flex items-start gap-2 px-3 py-0.5 border-b border-slate-900/50 hover:bg-slate-900/50 ${bg}`}
            >
              <span className="text-slate-600 shrink-0 w-[68px] tabular-nums">
                {time}
              </span>
              <span className="text-slate-700 shrink-0 w-[78px] text-[10px]">
                {date}
              </span>
              <span
                className={`shrink-0 w-[56px] text-[10px] ${color}`}
                title={e.level}
              >
                {e.level}
              </span>
              <span
                className={`shrink-0 px-1 rounded text-[9px] font-bold border ${srcCls}`}
                title={`source: ${src}`}
              >
                {src}
              </span>
              <span className={`flex-1 break-all ${color}`}>{e.msg}</span>
              {e.extra && Object.keys(e.extra).length > 0 && (
                <span className="text-slate-500 text-[10px] shrink-0 max-w-md truncate">
                  {Object.entries(e.extra)
                    .map(([k, v]) => `${k}=${shortVal(v)}`)
                    .join(" ")}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ── 底部状态栏 ──────────────────────────────────── */}
      <div className="flex items-center gap-3 px-3 py-1 bg-slate-900 border-t border-slate-800 text-[10px] font-mono text-slate-500">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            paused
              ? "bg-amber-500"
              : connected
                ? "bg-emerald-500 animate-pulse"
                : "bg-red-500"
          }`}
        />
        <span>
          SSE: {paused ? "paused" : connected ? "live" : "disconnected"}
        </span>
        <span>·</span>
        <span>file: {historyMeta.source || "—"}</span>
        <span>·</span>
        <span>shown {shown} / total {merged.length}</span>
        <span>·</span>
        <span>
          history {history.length} · live {live.length}
        </span>
        <div className="flex-1" />
        <span className="text-slate-600">
          FE-160 · /api/v1/logs/file + /api/v1/logs/stream
        </span>
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / 1024 / 1024).toFixed(1)}MB`;
}

function shortVal(v: unknown): string {
  if (v === null || v === undefined) return String(v);
  if (typeof v === "string") return v.length > 40 ? `"${v.slice(0, 38)}…"` : JSON.stringify(v);
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  const s = JSON.stringify(v);
  return s.length > 40 ? s.slice(0, 38) + "…" : s;
}
