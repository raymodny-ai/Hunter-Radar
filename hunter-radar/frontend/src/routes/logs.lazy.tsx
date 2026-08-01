/**
 * FE-160: 后台日志查看页面 (rev2, 2026-07-23)
 *
 * 数据源 3 选 1:
 *   - backend app 日志 (server.log 文件)
 *   - docker 容器日志 (docker logs 透传, 7 个容器可选)
 *   - SSE 实时流 (backend app structlog)
 *
 * 路由: /logs
 * 后端端点:
 *   GET  /api/v1/logs/services            - 列出可选数据源
 *   GET  /api/v1/logs/file?tail=N&...     - 读 server.log 文件
 *   GET  /api/v1/logs/docker?container=.. - docker logs 透传
 *   GET  /api/v1/logs/stream              - SSE
 *   GET  /api/v1/logs/history?limit=N     - SSE 内存缓冲
 */
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createLazyRoute } from "@tanstack/react-router";

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  extra?: Record<string, unknown>;
  source?: "app" | "uvicorn" | "docker" | string;
  raw?: string;
  container?: string;
}

interface LogService {
  service: string;
  container: string;
  label: string;
}

type SourceMode = "auto" | "docker" | "file";

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
  docker: "bg-purple-900/40 text-purple-300 border-purple-800",
};

export const Route = createLazyRoute("/logs")({
  component: LogsPage,
});

function LogsPage() {
  // ---- 服务列表 ----
  const [services, setServices] = useState<LogService[]>([]);
  const [selectedService, setSelectedService] = useState<string>("backend");

  // ---- 数据源模式 ----
  // auto: 按 service 自动选 — backend 用 file (server.log), 其他用 docker
  // docker/file: 强制用某个数据源
  const [sourceMode, setSourceMode] = useState<SourceMode>("auto");

  // ---- 历史 ----
  const [history, setHistory] = useState<LogEntry[]>([]);
  const [historyMeta, setHistoryMeta] = useState<{
    source: string;
    sizeBytes: number;
    loading: boolean;
    error: string | null;
    returned: number;
  }>({
    source: "",
    sizeBytes: 0,
    loading: true,
    error: null,
    returned: 0,
  });

  // ---- 实时 SSE ----
  const [live, setLive] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [connected, setConnected] = useState(false);
  const liveBufferRef = useRef<LogEntry[]>([]);
  const sseRef = useRef<EventSource | null>(null);

  // ---- 过滤 ----
  const [enabledLevels, setEnabledLevels] = useState<Set<string>>(
    new Set(LEVELS),
  );
  const [keyword, setKeyword] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [tailSize, setTailSize] = useState(500);
  const [showDockerSources, setShowDockerSources] = useState(true);

  // ---- 视图 ----
  const [appendLive, setAppendLive] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // ---- 拉服务列表 ----
  useEffect(() => {
    fetch("/api/v1/logs/services")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        const list: LogService[] = data.services ?? [];
        setServices(list);
      })
      .catch((e) => {
        setHistoryMeta((m) => ({ ...m, loading: false, error: `services: ${e}` }));
      });
  }, []);

  // ---- 决定数据源 (auto 模式) ----
  // V1.4 Docker 部署中: backend 的 server.log 不在镜像里生成 → auto 模式下
  // 所有服务都走 docker (看各自容器的 stdout)。要看 structlog SSE 实时
  // 流需要手动切到 "file" 模式 (但仅本地开发部署才能看到)。
  const effectiveSource: "docker" | "file" = useMemo(() => {
    if (sourceMode !== "auto") return sourceMode;
    return "docker";
  }, [sourceMode, selectedService]);

  // ---- 决定 docker 容器名 ----
  const dockerContainer = useMemo(() => {
    const svc = services.find((s) => s.service === selectedService);
    return svc?.container ?? "";
  }, [services, selectedService]);

  // ---- 加载历史 ----
  const reloadHistory = useCallback(async () => {
    setHistoryMeta((m) => ({ ...m, loading: true, error: null }));
    try {
      let url: string;
      if (effectiveSource === "file") {
        url = `/api/v1/logs/file?tail=${tailSize}`;
      } else {
        url = `/api/v1/logs/docker?container=${dockerContainer}&tail=${tailSize}`;
      }
      const r = await fetch(url);
      if (!r.ok) {
        const errText = await r.text();
        throw new Error(`HTTP ${r.status}: ${errText.slice(0, 100)}`);
      }
      const data = await r.json();
      setHistory(data.entries ?? []);
      setHistoryMeta({
        source: data.source ?? dockerContainer,
        sizeBytes: data.size_bytes ?? 0,
        loading: false,
        error: null,
        returned: data.returned ?? (data.entries?.length ?? 0),
      });
    } catch (e) {
      setHistoryMeta((m) => ({
        ...m,
        loading: false,
        error: e instanceof Error ? e.message : String(e),
      }));
    }
  }, [effectiveSource, dockerContainer, tailSize]);

  useEffect(() => {
    void reloadHistory();
  }, [reloadHistory]);

  // ---- SSE 实时流 (只有 effectiveSource=file 时才有意义, docker 不推流) ----
  useEffect(() => {
    if (paused || effectiveSource !== "file") {
      // 清掉旧 sse
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      setConnected(false);
      return;
    }
    const es = new EventSource("/api/v1/logs/stream");
    sseRef.current = es;
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const entry: LogEntry = JSON.parse(e.data);
        entry.source = entry.source ?? "app";
        if (pausedRef.current) return;
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
  }, [paused, effectiveSource]);

  // ---- 合并 ----
  const merged = useMemo(() => {
    if (appendLive && live.length > 0 && effectiveSource === "file") {
      const seen = new Set<string>();
      const out: LogEntry[] = [];
      for (const e of live) {
        const k = `${e.ts}|${e.raw ?? e.msg}`;
        if (seen.has(k)) continue;
        seen.add(k);
        out.push(e);
      }
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
  }, [history, live, appendLive, effectiveSource]);

  // ---- 过滤 ----
  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    return merged.filter((e) => {
      if (!enabledLevels.has(e.level)) return false;
      if (effectiveSource === "docker" && !showDockerSources) return false;
      if (kw) {
        const hay = `${e.msg} ${e.raw ?? ""} ${JSON.stringify(e.extra ?? {})}`;
        if (!hay.toLowerCase().includes(kw)) return false;
      }
      return true;
    });
  }, [merged, enabledLevels, keyword, effectiveSource, showDockerSources]);

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
      const ctr = e.container ? ` [${e.container}]` : "";
      const ex = e.extra ? " " + JSON.stringify(e.extra) : "";
      return `${ts} [${e.level}] [${src}]${ctr} ${e.msg}${ex}`;
    });
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `hunter-radar-${selectedService}-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const fileSizeText = historyMeta.sizeBytes
    ? formatBytes(historyMeta.sizeBytes)
    : "—";

  // ---- UI ----
  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] bg-slate-950 text-slate-200">
      {/* 顶栏 */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-slate-900 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-1.5 font-mono font-bold text-slate-300">
          <span>📋</span>
          <span>后台日志</span>
          <span className="text-slate-500 font-normal">
            ({shown}/{total} · {fileSizeText})
          </span>
        </div>

        <div className="w-px h-4 bg-slate-700" />

        {/* 服务下拉 */}
        <select
          value={selectedService}
          onChange={(e) => setSelectedService(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs font-mono text-slate-200 min-w-[180px]"
          title="选择日志来源服务"
        >
          {services.map((s) => (
            <option key={s.service} value={s.service}>
              {s.label}
            </option>
          ))}
        </select>

        {/* 数据源 */}
        <select
          value={sourceMode}
          onChange={(e) => setSourceMode(e.target.value as SourceMode)}
          className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-mono text-slate-200"
          title="数据源: auto=Docker 部署默认走 docker logs；file=server.log (需本地部署)"
        >
          <option value="auto">auto ({effectiveSource})</option>
          <option value="docker">docker logs</option>
          <option value="file">server.log 文件</option>
        </select>

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

        {/* 搜索 */}
        <input
          type="search"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索 msg / raw / extra…"
          className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs font-mono text-slate-200 placeholder:text-slate-500 w-56"
        />

        {/* tail 大小 */}
        <select
          value={tailSize}
          onChange={(e) => setTailSize(Number(e.target.value))}
          className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-mono text-slate-200"
          title="返回最后 N 行"
        >
          <option value={100}>100</option>
          <option value={500}>500</option>
          <option value={1000}>1k</option>
          <option value={2000}>2k</option>
        </select>

        <div className="flex-1" />

        {/* 实时追加 — 仅 file 模式有效 */}
        {effectiveSource === "file" && (
          <label className="flex items-center gap-1 cursor-pointer select-none" title="将 SSE 实时流追加到历史尾部">
            <input
              type="checkbox"
              checked={appendLive}
              onChange={() => setAppendLive((v) => !v)}
              className="accent-sky-500"
            />
            实时追加
          </label>
        )}

        {/* 暂停 — 仅 file 模式有效 */}
        {effectiveSource === "file" && (
          <button
            onClick={() => setPaused((v) => !v)}
            className={[
              "px-1.5 py-0.5 rounded font-mono border text-[10px]",
              paused
                ? "bg-amber-900/40 border-amber-700 text-amber-200"
                : "bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700",
            ].join(" ")}
            title="暂停 SSE"
          >
            {paused ? "▶ 继续" : "⏸ 暂停"}
          </button>
        )}

        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={() => setAutoScroll((v) => !v)}
            className="accent-slate-400"
          />
          滚动
        </label>

        <button
          onClick={clearLive}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="清空实时缓冲"
        >
          🗑 清实时
        </button>

        <button
          onClick={() => void reloadHistory()}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="重新读取"
        >
          ↻ 重读
        </button>

        <button
          onClick={downloadLog}
          className="px-1.5 py-0.5 rounded font-mono border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-[10px]"
          title="下载当前过滤结果"
        >
          ⤓ 下载
        </button>
      </div>

      {/* 主日志流 */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed"
        style={{ fontFamily: "JetBrains Mono, Menlo, monospace" }}
      >
        {historyMeta.loading && (
          <div className="text-slate-500 text-center py-12">
            读取 {effectiveSource === "docker" ? `docker logs ${dockerContainer}` : "server.log"}…
          </div>
        )}
        {historyMeta.error && (
          <div className="text-red-400 text-center py-12">
            ❌ 加载失败: {historyMeta.error}
            <div className="text-xs text-slate-500 mt-2">
              {effectiveSource === "file"
                ? "提示: 当前为 backend server.log 模式，但 Docker 部署未挂载日志文件。"
                : "提示: docker 透传需要 backend 容器挂载 /var/run/docker.sock。"}
              {effectiveSource === "docker" && !dockerContainer && (
                <>容器名为空 — 检查 /api/v1/logs/services 返回。</>
              )}
            </div>
          </div>
        )}
        {!historyMeta.loading && !historyMeta.error && shown === 0 && (
          <div className="text-slate-600 text-center py-12">
            无匹配日志 (历史 {history.length} 条, 实时 {live.length} 条)
          </div>
        )}
        {filtered.map((e, i) => {
          const time = e.ts?.slice(11, 23) || "    -    ";
          const date = e.ts?.slice(0, 10) || "";
          const color = LEVEL_TEXT[e.level] || "text-slate-300";
          const bg = LEVEL_BG[e.level] || "";
          const src = e.source || "app";
          const srcCls = SOURCE_BADGE[src] || SOURCE_BADGE.app;
          const ctr = e.container ? `·${e.container.replace("hunter_", "")}` : "";
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
              {ctr && (
                <span className="text-purple-400 shrink-0 text-[10px] font-bold" title={e.container}>
                  {ctr}
                </span>
              )}
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

      {/* 底部状态栏 */}
      <div className="flex items-center gap-3 px-3 py-1 bg-slate-900 border-t border-slate-800 text-[10px] font-mono text-slate-500">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            paused
              ? "bg-amber-500"
              : connected
                ? "bg-emerald-500 animate-pulse"
                : effectiveSource === "file"
                  ? "bg-slate-500"
                  : "bg-slate-600"
          }`}
        />
        <span>
          {effectiveSource === "docker"
            ? `docker logs (静态, 容器 ${dockerContainer})`
            : paused
              ? "paused"
              : connected
                ? "live"
                : "file (offline)"}
        </span>
        <span>·</span>
        <span>
          source: {effectiveSource === "docker" ? `docker/${dockerContainer}` : historyMeta.source || "—"}
        </span>
        <span>·</span>
        <span>shown {shown}</span>
        <span>·</span>
        <span>history {history.length} · live {live.length}</span>
        {effectiveSource === "docker" && (
          <>
            <span>·</span>
            <span>returned {historyMeta.returned}</span>
          </>
        )}
        <div className="flex-1" />
        <span className="text-slate-600">FE-160 rev2 · /logs</span>
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